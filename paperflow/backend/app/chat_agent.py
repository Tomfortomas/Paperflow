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
    PaperChatMessage,
    PaperChatRequest,
    PaperChatResponse,
    PaperChatStep,
    ReadingReport,
    ReliabilityLevel,
)


def generate_chat_response(
    *,
    paper_id: str,
    chat_id: str,
    question: str,
    request: PaperChatRequest,
    report: ReadingReport,
    r1_cache: Optional[dict] = None,
    client: Optional[DeepSeekClient] = None,
) -> PaperChatResponse:
    steps = _base_steps(report, r1_cache)
    selected = _selected_evidence(report, request)
    used_context = ["report"]
    if selected:
        used_context.append("selected_evidence")
    if r1_cache and r1_cache.get("items"):
        used_context.append("r1_cache")

    if client is not None:
        try:
            answer = _ask_deepseek(
                client=client,
                question=question,
                request=request,
                report=report,
                r1_cache=r1_cache,
                selected=selected,
            )
        except Exception as exc:
            answer = _fallback_answer(report, request, question)
            answer.uncertainty = (
                f"DeepSeek chat failed, so Paperflow fell back to report-grounded retrieval: {exc}"
            )
    else:
        answer = _fallback_answer(report, request, question)

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


def _base_steps(report: ReadingReport, r1_cache: Optional[dict]) -> list[PaperChatStep]:
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
) -> Claim:
    context = {
        "question": question,
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
    }
    prompt = (
        "You are Paperflow's evidence-grounded paper chat agent. Answer in Simplified Chinese. "
        "Use only the JSON context. Return strict JSON with this schema: "
        '{"answer":{"text":string,"reliability":"R0|R1|R2","evidence":[evidence],"uncertainty":string|null},'
        '"used_context":[string],"process_notes":[string]}. '
        "R0 requires current-paper evidence. R1 requires related-work cache evidence. "
        "Use R2 for interpretation or when evidence is weak.\n\n"
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


def _fallback_answer(report: ReadingReport, request: PaperChatRequest, question: str) -> Claim:
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
