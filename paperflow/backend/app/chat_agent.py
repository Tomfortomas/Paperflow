from __future__ import annotations

import json
import time
import uuid
from typing import Optional

import httpx

from app.deepseek import DeepSeekClient
from app.models import (
    Claim,
    Evidence,
    EvidenceLocationStatus,
    PaperChatMessage,
    PaperChatRequest,
    PaperChatResponse,
    PaperChatStep,
    ReadingReport,
    ReliabilityLevel,
)
from app.web_search import WebSearchResult


def generate_chat_response(
    *,
    paper_id: str,
    chat_id: str,
    question: str,
    request: PaperChatRequest,
    report: ReadingReport,
    r1_cache: Optional[dict] = None,
    client: Optional[DeepSeekClient] = None,
    web_search_client: Optional[object] = None,
    web_search_limit: int = 5,
    web_search_mode: str = "auto",
) -> PaperChatResponse:
    selected = _selected_evidence(report, request)
    may_use_model_knowledge = _may_use_model_knowledge(question)
    used_context = ["report"]
    if selected:
        used_context.append("selected_evidence")
    if r1_cache and r1_cache.get("items"):
        used_context.append("r1_cache")
    if may_use_model_knowledge:
        used_context.append("model_knowledge")

    web_results: list[WebSearchResult] = []
    web_step_status = "skipped"
    web_step_detail = "Local report / R1 context looked sufficient."
    if _should_web_search(
        question=question,
        request=request,
        report=report,
        r1_cache=r1_cache,
        selected=selected,
        mode=web_search_mode,
    ):
        if web_search_client is None:
            web_step_detail = "Web search is enabled but no search client is configured."
        else:
            try:
                search = getattr(web_search_client, "search")
                web_results = list(search(_web_search_query(question, report), limit=web_search_limit))
                web_step_status = "completed"
                web_step_detail = (
                    f"Found {len(web_results)} web result(s)."
                    if web_results
                    else "Searched the web but found no usable results."
                )
                if web_results:
                    used_context.append("web_search")
            except Exception as exc:
                web_step_status = "failed"
                web_step_detail = f"Web search failed; continued with local context: {exc}"

    steps = _base_steps(
        report,
        r1_cache,
        web_step_status=web_step_status,
        web_step_detail=web_step_detail,
    )

    if client is not None:
        try:
            answer = _ask_deepseek(
                client=client,
                question=question,
                request=request,
                report=report,
                r1_cache=r1_cache,
                selected=selected,
                web_results=web_results,
                may_use_model_knowledge=may_use_model_knowledge,
            )
        except Exception as exc:
            answer = _fallback_answer(report, request, question, web_results=web_results)
            answer.uncertainty = (
                f"DeepSeek chat failed, so Paperflow fell back to report-grounded retrieval: {exc}"
            )
    else:
        answer = _fallback_answer(report, request, question, web_results=web_results)

    turn_id = f"turn-{uuid.uuid4().hex[:10]}"
    return PaperChatResponse(
        id=chat_id,
        paper_id=paper_id,
        status="completed",
        used_context=used_context,
        steps=steps,
        messages=[
            PaperChatMessage(
                id=f"user-{uuid.uuid4().hex[:10]}",
                role="user",
                content=question,
            ),
            PaperChatMessage(
                id=f"assistant-{uuid.uuid4().hex[:10]}",
                role="assistant",
                content=answer.text,
                reliability=answer.reliability,
                evidence=answer.evidence,
                uncertainty=answer.uncertainty,
            ),
        ],
        answer=answer,
    )


def sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _base_steps(
    report: ReadingReport,
    r1_cache: Optional[dict],
    *,
    web_step_status: str = "skipped",
    web_step_detail: str = "Local report / R1 context looked sufficient.",
) -> list[PaperChatStep]:
    return [
        PaperChatStep(
            id="read-report",
            label="Read report",
            status="completed",
            detail=f"Loaded {len(report.summary)} summary claims and {len(report.sections)} sections.",
        ),
        PaperChatStep(
            id="locate-evidence",
            label="Locate evidence",
            status="completed",
            detail="Used selected claim/evidence or best matching report evidence.",
        ),
        PaperChatStep(
            id="check-r1",
            label="Check R1 context",
            status="completed",
            detail=f"Checked {len((r1_cache or {}).get('items', []))} cached R1 items.",
        ),
        PaperChatStep(
            id="web-search",
            label="Web search",
            status=web_step_status,
            detail=web_step_detail,
        ),
        PaperChatStep(
            id="compose-answer",
            label="Compose answer",
            status="completed",
            detail="Generated a reliability-labelled answer.",
        ),
        PaperChatStep(
            id="persist-transcript",
            label="Persist transcript",
            status="completed",
            detail="Saved this turn to the paper chat thread.",
        ),
    ]


def _ask_deepseek(
    *,
    client: DeepSeekClient,
    question: str,
    request: PaperChatRequest,
    report: ReadingReport,
    r1_cache: Optional[dict],
    selected: list[Evidence],
    web_results: list[WebSearchResult],
    may_use_model_knowledge: bool,
) -> Claim:
    context = {
        "question": question,
        "answer_policy": {
            "may_use_general_model_knowledge": may_use_model_knowledge,
            "general_model_knowledge_reliability": "R2",
            "paper_evidence_reliability": "R0",
            "related_work_reliability": "R1",
        },
        "selected": {
            "claim_id": request.selected_claim_id,
            "evidence_id": request.selected_evidence_id,
            "quote": request.quote,
            "page": request.page,
            "section": request.section,
        },
        "report": {
            "title": report.paper_title,
            "summary": [claim.model_dump(mode="json") for claim in report.summary[:8]],
            "sections": [
                {
                    "title": section.title,
                    "claims": [claim.model_dump(mode="json") for claim in section.claims[:4]],
                }
                for section in report.sections[:8]
            ],
        },
        "selected_evidence": [evidence.model_dump(mode="json") for evidence in selected],
        "r1_cache": (r1_cache or {}).get("items", [])[:8],
        "web_context": [
            {"title": item.title, "url": item.url, "snippet": item.snippet}
            for item in web_results[:5]
        ],
    }
    prompt = (
        "You are Paperflow's evidence-grounded paper chat agent. Answer in Simplified Chinese. "
        "Prefer current-paper evidence when the user asks about this paper, selected claims, or PDF evidence. "
        "For broad definition/background questions, if answer_policy.may_use_general_model_knowledge is true, "
        "you may use general model knowledge even when the paper context does not define the concept; do not refuse "
        "solely because the current paper is about a different topic. "
        "When using general model knowledge, label the answer R2, keep evidence empty unless web_context is cited, "
        "and set uncertainty to say the answer is general background rather than current-paper evidence. "
        "When web_context is used, label it as external web context and cite source URLs. "
        "Return strict JSON with this schema: "
        '{"answer":{"text":string,"reliability":"R0|R1|R2","evidence":[evidence],"uncertainty":string|null},'
        '"used_context":[string],"process_notes":[string]}. '
        "R0 requires current-paper evidence. R1 requires related-work cache evidence. "
        "Use R2 for interpretation, general background, or web-only evidence.\n\n"
        f"Context:\n{json.dumps(context, ensure_ascii=False)}"
    )
    response = httpx.post(
        f"{client.base_url}/chat/completions",
        headers={"Authorization": f"Bearer {client.api_key}"},
        json={
            "model": client.model,
            "messages": [
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        timeout=httpx.Timeout(connect=10.0, read=90.0, write=10.0, pool=10.0),
    )
    response.raise_for_status()
    payload = json.loads(response.json()["choices"][0]["message"]["content"])
    answer = payload.get("answer") or {}
    evidence = answer.get("evidence") or []
    return Claim(
        id=f"chat-answer-{int(time.time() * 1000)}",
        text=answer.get("text") or "Agent 没有返回可用回答。",
        reliability=ReliabilityLevel(answer.get("reliability") or "R2"),
        evidence=[Evidence.model_validate(item) for item in evidence],
        uncertainty=answer.get("uncertainty"),
    )


def _fallback_answer(
    report: ReadingReport,
    request: PaperChatRequest,
    question: str,
    *,
    web_results: Optional[list[WebSearchResult]] = None,
) -> Claim:
    if web_results and _is_broad_question(question):
        return _web_fallback_answer(question, web_results)

    selected = _find_claim(report, request.selected_claim_id)
    if selected is not None:
        return Claim(
            id="chat-answer",
            text=selected.text,
            reliability=selected.reliability,
            evidence=_selected_evidence(report, request) or selected.evidence,
            uncertainty=selected.uncertainty,
        )

    question_lower = question.lower()
    for section in report.sections:
        section_key = section.title.lower().split("/")[0].strip()
        if section.claims and section_key and section_key in question_lower:
            claim = section.claims[0]
            return Claim(
                id="chat-answer",
                text=claim.text,
                reliability=claim.reliability,
                evidence=claim.evidence,
                uncertainty=claim.uncertainty,
            )
        if section.claims and "benchmark" in question_lower and "benchmark" in section.title.lower():
            claim = section.claims[0]
            return Claim(
                id="chat-answer",
                text=claim.text,
                reliability=claim.reliability,
                evidence=claim.evidence,
                uncertainty=claim.uncertainty,
            )

    if request.quote:
        evidence = Evidence(
            id=request.selected_evidence_id or f"chat-selection-{uuid.uuid4().hex[:8]}",
            source=report.paper_title or "selected PDF text",
            page=request.page,
            section=request.section,
            quote=request.quote.strip(),
        )
        return Claim(
            id="chat-answer",
            text=f"基于你选中的证据，Agent 将问题限定在这段原文内：{request.quote.strip()[:180]}",
            reliability=ReliabilityLevel.R0,
            evidence=[evidence],
        )

    first = report.summary[0] if report.summary else None
    if first is not None:
        return Claim(
            id="chat-answer",
            text=first.text,
            reliability=first.reliability,
            evidence=first.evidence,
            uncertainty=first.uncertainty,
        )
    return Claim(
        id="chat-answer",
        text="当前报告没有足够内容回答这个问题。",
        reliability=ReliabilityLevel.R2,
        evidence=[],
        uncertainty="Reading Report is empty.",
    )


def _web_fallback_answer(question: str, web_results: list[WebSearchResult]) -> Claim:
    evidence = [_web_result_to_evidence(item, index) for index, item in enumerate(web_results[:3], start=1)]
    lead = evidence[0].quote if evidence else ""
    return Claim(
        id="chat-answer-web",
        text=(
            "本地阅读报告没有足够信息直接回答这个问题；以下基于外部网页搜索结果给出背景性回答。"
            f"{lead}"
        ),
        reliability=ReliabilityLevel.R2,
        evidence=evidence,
        uncertainty="This answer uses external web search snippets rather than direct PDF evidence.",
    )


def _web_result_to_evidence(result: WebSearchResult, index: int) -> Evidence:
    return Evidence(
        id=f"web-{index}",
        source=result.url,
        quote=f"{result.title}: {result.snippet}".strip(": "),
        location_status=EvidenceLocationStatus.QUOTE_ONLY,
    )


def _should_web_search(
    *,
    question: str,
    request: PaperChatRequest,
    report: ReadingReport,
    r1_cache: Optional[dict],
    selected: list[Evidence],
    mode: str,
) -> bool:
    if mode == "off":
        return False
    if mode == "always":
        return True
    if _is_broad_question(question):
        return True
    if request.selected_claim_id or request.selected_evidence_id or request.quote or selected:
        return False
    searchable = " ".join(
        [
            report.paper_title,
            " ".join(claim.text for claim in report.summary),
            " ".join(section.title for section in report.sections),
            " ".join(str(item.get("title", "")) for item in (r1_cache or {}).get("items", [])[:8]),
        ]
    ).lower()
    terms = [term for term in question.lower().split() if len(term) >= 4]
    if terms and not any(term in searchable for term in terms):
        return True
    return False


def _may_use_model_knowledge(question: str) -> bool:
    lowered = question.lower()
    paper_scoped_markers = [
        "这篇",
        "本文",
        "论文",
        "paper",
        "claim",
        "证据",
        "实验",
        "结果",
    ]
    if any(marker in lowered for marker in paper_scoped_markers):
        return False
    triggers = [
        "什么是",
        "是什么",
        "介绍一下",
        "背景",
        "what is",
        "define",
        "definition",
        "overview",
        "explain",
    ]
    return any(trigger in lowered for trigger in triggers)


def _is_broad_question(question: str) -> bool:
    lowered = question.lower()
    triggers = [
        "什么是",
        "介绍一下",
        "背景",
        "最新",
        "查一下",
        "联网",
        "web",
        "search",
        "what is",
        "explain",
        "overview",
        "recent",
        "latest",
    ]
    return any(trigger in lowered for trigger in triggers)


def _is_general_background_question(question: str) -> bool:
    return _may_use_model_knowledge(question)


def _web_search_query(question: str, report: ReadingReport) -> str:
    if _is_general_background_question(question):
        return question
    title = (report.paper_title or "").strip()
    if title:
        return f"{question} {title}"
    return question


def _selected_evidence(report: ReadingReport, request: PaperChatRequest) -> list[Evidence]:
    claim = _find_claim(report, request.selected_claim_id)
    if claim is None:
        return []
    if request.selected_evidence_id:
        return [evidence for evidence in claim.evidence if evidence.id == request.selected_evidence_id]
    return claim.evidence[:1]


def _find_claim(report: ReadingReport, claim_id: Optional[str]) -> Optional[Claim]:
    if not claim_id:
        return None
    for claim in report.summary:
        if claim.id == claim_id:
            return claim
    for section in report.sections:
        for claim in section.claims:
            if claim.id == claim_id:
                return claim
    return None
