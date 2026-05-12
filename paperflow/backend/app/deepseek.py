from __future__ import annotations

import os
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

import httpx

from app.models import AgentRunMetrics, ReadingReport, ReportSection


REPORT_TEXT_BUDGET = 12000
BRIEFING_TEXT_BUDGET = 18000
MAX_PARALLEL_CHUNKS = 4
REPORT_READ_TIMEOUT_SECONDS = 90.0
DEEPSEEK_MODEL_OPTIONS = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-chat",
    "deepseek-reasoner",
]
_report_read_timeout_override: Optional[float] = None


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/beta",
        model: str = "deepseek-v4-flash",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    @classmethod
    def from_env(cls) -> Optional["DeepSeekClient"]:
        config = _load_deepseek_config()
        api_key = os.getenv("DEEPSEEK_API_KEY") or config.get("api_key")
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL")
            or config.get("base_url")
            or "https://api.deepseek.com/beta",
            model=os.getenv("DEEPSEEK_MODEL")
            or config.get("model")
            or "deepseek-v4-flash",
        )

    def summarize_r0(self, text: str) -> str:
        prompt = (
            "You are Paperflow's R0 paper parser. Summarize the paper's core problem "
            "in one concise sentence using only the provided text. Do not invent facts.\n\n"
            f"Paper text:\n{text[:12000]}"
        )
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "Return one evidence-grounded sentence."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def generate_reading_report(
        self,
        paper_id: str,
        source_name: str,
        paper_text: str,
        on_partial_report: Optional[Callable[[ReadingReport], None]] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> ReadingReport:
        chunks = _split_paper_text(paper_text)
        reports: list[Optional[ReadingReport]] = [None for _ in chunks]
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        saw_usage = False

        if on_progress is not None:
            on_progress(
                "DeepSeek briefing is running "
                f"(model={self.model}, input={_format_char_count(len(paper_text))} chars)"
            )
        briefing, usage = self._generate_paper_briefing(source_name=source_name, paper_text=paper_text)
        if usage:
            saw_usage = True
            prompt_tokens += usage.get("prompt_tokens") or 0
            completion_tokens += usage.get("completion_tokens") or 0
            total_tokens += usage.get("total_tokens") or 0

        completed_indices: set[int] = set()
        executor = ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_CHUNKS, max(1, len(chunks))))
        shutdown_without_wait = False
        if on_progress is not None:
            on_progress(
                "DeepSeek parallel chunk extraction is running "
                f"(model={self.model}, chunks={len(chunks)}, input={_format_char_count(len(paper_text))} chars)"
            )
        try:
            futures = {
                executor.submit(
                    self._generate_chunk_report,
                    paper_id=paper_id,
                    source_name=source_name,
                    paper_text=chunk,
                    chunk_index=index,
                    chunk_count=len(chunks),
                    briefing=briefing,
                ): index
                for index, chunk in enumerate(chunks)
            }

            for future in as_completed(futures):
                index = futures[future]
                try:
                    report, usage = future.result()
                except Exception:
                    for pending in futures:
                        pending.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    shutdown_without_wait = True
                    raise
                reports[index] = report
                completed_indices.add(index)
                completed = len(completed_indices)
                if on_progress is not None:
                    on_progress(f"DeepSeek chunk completed (chunk={completed}/{len(chunks)})")
                if usage:
                    saw_usage = True
                    prompt_tokens += usage.get("prompt_tokens") or 0
                    completion_tokens += usage.get("completion_tokens") or 0
                    total_tokens += usage.get("total_tokens") or 0
                if on_partial_report is not None:
                    partial_reports = [item for item in reports if item is not None]
                    partial = _merge_chunk_reports(paper_id, partial_reports)
                    covered_chars = sum(len(chunks[chunk_index]) for chunk_index in completed_indices)
                    total_chars = len(paper_text)
                    partial.agent_run = AgentRunMetrics(
                        model=self.model,
                        prompt_tokens=prompt_tokens if saw_usage else None,
                        completion_tokens=completion_tokens if saw_usage else None,
                        total_tokens=total_tokens if saw_usage else None,
                        covered_chars=covered_chars,
                        total_chars=total_chars,
                        coverage_percent=1.0
                        if total_chars == 0
                        else min(1.0, covered_chars / total_chars),
                        chunks_processed=completed,
                    )
                    on_partial_report(partial)
        finally:
            if not shutdown_without_wait:
                executor.shutdown(wait=True)

        extraction_reports = [report for report in reports if report is not None]
        draft = _merge_chunk_reports(paper_id, extraction_reports)
        if on_progress is not None:
            on_progress(
                "DeepSeek coordinator synthesis is running "
                f"(model={self.model}, chunks={len(extraction_reports)})"
            )
        report, usage = self._synthesize_report(
            paper_id=paper_id,
            source_name=source_name,
            briefing=briefing,
            chunk_reports=extraction_reports,
            draft=draft,
        )
        if usage:
            saw_usage = True
            prompt_tokens += usage.get("prompt_tokens") or 0
            completion_tokens += usage.get("completion_tokens") or 0
            total_tokens += usage.get("total_tokens") or 0

        covered_chars = sum(len(chunk) for chunk in chunks)
        total_chars = len(paper_text)
        report.agent_run = AgentRunMetrics(
            model=self.model,
            prompt_tokens=prompt_tokens if saw_usage else None,
            completion_tokens=completion_tokens if saw_usage else None,
            total_tokens=total_tokens if saw_usage else None,
            covered_chars=covered_chars,
            total_chars=total_chars,
            coverage_percent=1.0 if total_chars == 0 else min(1.0, covered_chars / total_chars),
            chunks_processed=len(chunks),
        )
        return report

    def _generate_paper_briefing(self, *, source_name: str, paper_text: str) -> tuple[dict, dict]:
        prompt = (
            "You are Paperflow's fast paper briefing agent. Build a compact global briefing "
            "before detailed chunk extraction. Use only the provided high-signal paper text. "
            "Return strict JSON with keys: paper_title, task, method, datasets, benchmarks, "
            "key_terms, likely_contributions, open_questions. Keep it concise; this briefing "
            "will be shared with parallel chunk agents to reduce duplicate and inconsistent claims.\n\n"
            f"source_name: {source_name}\n"
            f"high_signal_text:\n{_high_signal_text(paper_text)}"
        )
        payload, usage = self._post_json(prompt, system="Return JSON only.")
        return payload, usage

    def _generate_chunk_report(
        self,
        *,
        paper_id: str,
        source_name: str,
        paper_text: str,
        chunk_index: int,
        chunk_count: int,
        briefing: dict,
    ) -> tuple[ReadingReport, dict]:
        prompt = (
            "You are Paperflow's paper-reading AI agent. Extract an evidence-aware "
            "reading report from the provided paper text. Use R0 only for claims directly "
            "supported by the current paper text. Use R1 only for related-work context "
            "explicitly present in references/related-work text. Use R2 for any inference "
            "or uncertainty. Write all explanatory prose in Simplified Chinese, including "
            "claim.text, claim.uncertainty, and related_work.relation. Keep paper titles, "
            "model/dataset names, source names, and evidence.quote in their original language; "
            "evidence.quote must be an exact quote from the paper text, not a translation. "
            "Keep section.title values exactly as the required English labels below so the UI "
            "can map them consistently. Use the paper_briefing to avoid duplicate claims and "
            "to interpret local symbols, but do not cite the briefing as evidence. Return strict "
            "JSON matching this schema:\n"
            "{\n"
            '  "paper_id": string,\n'
            '  "paper_title": string|null,\n'
            '  "summary": [{"id": string, "text": string, "reliability": "R0|R1|R2", '
            '"evidence": [{"id": string, "source": string, "page": number|null, '
            '"section": string|null, "quote": string}], "uncertainty": string|null}],\n'
            '  "sections": [{"id": string, "title": string, "claims": [same claim schema]}],\n'
            '  "related_work": [{"id": string, "title": string, "relation": string, '
            '"source": string, "reliability": "R1|R2", "evidence": [evidence schema]}]\n'
            "}\n"
            "Required sections: Task, Dataset, Benchmark / Metric, Method, Input / Output, "
            "Compute / Training, Code / Implementation, Limitations. In Code / Implementation, "
            "answer whether the paper explicitly says code is open-sourced and what codebase, "
            "framework, repository, or implementation base is used. Use R0 only when the paper "
            "text directly states this; otherwise create an R2 uncertainty claim saying the paper "
            "does not provide enough evidence. If evidence is missing, create an R2 claim "
            "with uncertainty instead of guessing. Extract paper_title from the paper title "
            "or first-page metadata when available; use the original paper title, not the PDF "
            "filename. If the title is unclear, return null. "
            "This may be one chunk from a longer paper; extract only claims supported by "
            "this chunk and keep evidence quotes exact.\n\n"
            f"paper_id: {paper_id}\n"
            f"source_name: {source_name}\n"
            f"chunk: {chunk_index + 1}/{chunk_count}\n"
            f"paper_briefing:\n{json.dumps(briefing, ensure_ascii=False)}\n"
            f"paper_text:\n{paper_text}"
        )
        data, usage = self._post_json(
            prompt,
            system="You are a strict JSON paper-reading agent. Return JSON only.",
        )
        self._normalize_report_payload(data, paper_id=paper_id, source_name=source_name)
        report = ReadingReport.model_validate(data)
        return report, usage

    def _synthesize_report(
        self,
        *,
        paper_id: str,
        source_name: str,
        briefing: dict,
        chunk_reports: list[ReadingReport],
        draft: ReadingReport,
    ) -> tuple[ReadingReport, dict]:
        prompt = (
            "You are Paperflow's coordinator and final report synthesis agent. "
            "Merge parallel chunk reports into one non-redundant, globally consistent reading report. "
            "Deduplicate overlapping claims, preserve exact evidence quotes, keep R0/R1/R2 labels conservative, "
            "and repair gaps when a required section is missing by adding an R2 uncertainty claim rather than guessing. "
            "Required sections include Task, Dataset, Benchmark / Metric, Method, Input / Output, "
            "Compute / Training, Code / Implementation, and Limitations. The Code / Implementation section must "
            "answer whether code is open-sourced and what codebase/framework/repository is used when the paper "
            "directly states it; otherwise keep it as an R2 uncertainty claim. "
            "Return strict JSON using the same ReadingReport schema as chunk reports.\n\n"
            f"paper_id: {paper_id}\n"
            f"source_name: {source_name}\n"
            f"paper_briefing:\n{json.dumps(briefing, ensure_ascii=False)}\n"
            f"chunk_reports_compact:\n{_compact_reports_json(chunk_reports or [draft])}"
        )
        data, usage = self._post_json(
            prompt,
            system="You are a strict JSON coordinator. Return JSON only.",
        )
        self._normalize_report_payload(
            data,
            paper_id=paper_id,
            source_name=source_name,
            ensure_code_section=True,
        )
        return ReadingReport.model_validate(data), usage

    def _post_json(self, prompt: str, *, system: str) -> tuple[dict, dict]:
        response = self._post_with_retries(prompt, system=system)
        response.raise_for_status()
        response_payload = response.json()
        content = response_payload["choices"][0]["message"]["content"]
        return json.loads(content), response_payload.get("usage") or {}

    def _post_with_retries(self, prompt: str, *, system: str) -> httpx.Response:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        last_error: Optional[Exception] = None
        for _ in range(3):
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                    timeout=_report_timeout(),
                )
                status_code = getattr(response, "status_code", 200)
                if status_code not in {429, 500, 502, 503, 504}:
                    return response
                last_error = RuntimeError(f"DeepSeek transient status {status_code}")
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("DeepSeek request failed without a response")

    def _normalize_report_payload(
        self,
        data: dict,
        *,
        paper_id: str,
        source_name: str,
        ensure_code_section: bool = False,
    ) -> None:
        data["paper_id"] = paper_id
        data["summary"] = data.get("summary") or []
        data["sections"] = data.get("sections") or []
        data["related_work"] = data.get("related_work") or []
        if ensure_code_section:
            _ensure_code_section(data)
        for index, claim in enumerate(data.get("summary", []), start=1):
            claim.setdefault("id", f"summary-{index}")
            self._fill_claim_sources(claim, source_name, prefix=f"summary-{index}")
        for section_index, section in enumerate(data.get("sections", []), start=1):
            section_title = section.get("title") or f"Section {section_index}"
            section["title"] = section_title
            section.setdefault("id", _slug_id("section", section_title, section_index))
            section["claims"] = section.get("claims") or []
            for claim_index, claim in enumerate(section.get("claims", []), start=1):
                claim.setdefault("id", f"{section['id']}-claim-{claim_index}")
                self._fill_claim_sources(claim, source_name, prefix=f"{section['id']}-{claim_index}")
        for index, item in enumerate(data.get("related_work", []), start=1):
            title = item.get("title") or f"Related work {index}"
            item["title"] = title
            item.setdefault("id", _slug_id("rw", title, index))
            item["evidence"] = item.get("evidence") or []
            for evidence_index, evidence in enumerate(item.get("evidence", []), start=1):
                evidence.setdefault("id", f"{item['id']}-e{evidence_index}")
                evidence.setdefault("source", source_name)

    def _fill_claim_sources(self, claim: dict, source_name: str, *, prefix: str) -> None:
        claim["evidence"] = claim.get("evidence") or []
        for index, evidence in enumerate(claim.get("evidence", []), start=1):
            evidence.setdefault("id", f"{prefix}-e{index}")
            evidence.setdefault("source", source_name)

    def _legacy_generate_reading_report(
        self,
        paper_id: str,
        source_name: str,
        paper_text: str,
        on_partial_report: Optional[Callable[[ReadingReport], None]] = None,
    ) -> ReadingReport:
        chunks = _split_paper_text(paper_text)
        reports: list[ReadingReport] = []
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        saw_usage = False

        for index, chunk in enumerate(chunks):
            report, usage = self._legacy_generate_chunk_report(
                paper_id=paper_id,
                source_name=source_name,
                paper_text=chunk,
                chunk_index=index,
                chunk_count=len(chunks),
            )
            reports.append(report)
            if usage:
                saw_usage = True
                prompt_tokens += usage.get("prompt_tokens") or 0
                completion_tokens += usage.get("completion_tokens") or 0
                total_tokens += usage.get("total_tokens") or 0
            if on_partial_report is not None:
                partial = _merge_chunk_reports(paper_id, reports)
                covered_chars = sum(len(chunk) for chunk in chunks[: index + 1])
                total_chars = len(paper_text)
                partial.agent_run = AgentRunMetrics(
                    model=self.model,
                    prompt_tokens=prompt_tokens if saw_usage else None,
                    completion_tokens=completion_tokens if saw_usage else None,
                    total_tokens=total_tokens if saw_usage else None,
                    covered_chars=covered_chars,
                    total_chars=total_chars,
                    coverage_percent=1.0
                    if total_chars == 0
                    else min(1.0, covered_chars / total_chars),
                    chunks_processed=index + 1,
                )
                on_partial_report(partial)

        report = _merge_chunk_reports(paper_id, reports)
        covered_chars = sum(len(chunk) for chunk in chunks)
        total_chars = len(paper_text)
        report.agent_run = AgentRunMetrics(
            model=self.model,
            prompt_tokens=prompt_tokens if saw_usage else None,
            completion_tokens=completion_tokens if saw_usage else None,
            total_tokens=total_tokens if saw_usage else None,
            covered_chars=covered_chars,
            total_chars=total_chars,
            coverage_percent=1.0 if total_chars == 0 else min(1.0, covered_chars / total_chars),
            chunks_processed=len(chunks),
        )
        return report

    def _legacy_generate_chunk_report(
        self,
        *,
        paper_id: str,
        source_name: str,
        paper_text: str,
        chunk_index: int,
        chunk_count: int,
    ) -> tuple[ReadingReport, dict]:
        prompt = (
            "You are Paperflow's paper-reading AI agent. Extract an evidence-aware "
            "reading report from the provided paper text. Use R0 only for claims directly "
            "supported by the current paper text. Use R1 only for related-work context "
            "explicitly present in references/related-work text. Use R2 for any inference "
            "or uncertainty. Write all explanatory prose in Simplified Chinese, including "
            "claim.text, claim.uncertainty, and related_work.relation. Keep paper titles, "
            "model/dataset names, source names, and evidence.quote in their original language; "
            "evidence.quote must be an exact quote from the paper text, not a translation. "
            "Keep section.title values exactly as the required English labels below so the UI "
            "can map them consistently. Return strict JSON matching this schema:\n"
            "{\n"
            '  "paper_id": string,\n'
            '  "paper_title": string|null,\n'
            '  "summary": [{"id": string, "text": string, "reliability": "R0|R1|R2", '
            '"evidence": [{"id": string, "source": string, "page": number|null, '
            '"section": string|null, "quote": string}], "uncertainty": string|null}],\n'
            '  "sections": [{"id": string, "title": string, "claims": [same claim schema]}],\n'
            '  "related_work": [{"id": string, "title": string, "relation": string, '
            '"source": string, "reliability": "R1|R2", "evidence": [evidence schema]}]\n'
            "}\n"
            "Required sections: Task, Dataset, Benchmark / Metric, Method, Input / Output, "
            "Compute / Training, Code / Implementation, Limitations. In Code / Implementation, "
            "answer whether the paper explicitly says code is open-sourced and what codebase, "
            "framework, repository, or implementation base is used. Use R0 only when the paper "
            "text directly states this; otherwise create an R2 uncertainty claim saying the paper "
            "does not provide enough evidence. If evidence is missing, create an R2 claim "
            "with uncertainty instead of guessing. Extract paper_title from the paper title "
            "or first-page metadata when available; use the original paper title, not the PDF "
            "filename. If the title is unclear, return null. "
            "This may be one chunk from a longer paper; extract only claims supported by "
            "this chunk and keep evidence quotes exact.\n\n"
            f"paper_id: {paper_id}\n"
            f"source_name: {source_name}\n"
            f"chunk: {chunk_index + 1}/{chunk_count}\n"
            f"paper_text:\n{paper_text}"
        )
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a strict JSON paper-reading agent. Return JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=_report_timeout(),
        )
        response.raise_for_status()
        response_payload = response.json()
        content = response_payload["choices"][0]["message"]["content"]
        data = json.loads(content)
        self._normalize_report_payload(data, paper_id=paper_id, source_name=source_name)
        report = ReadingReport.model_validate(data)
        return report, response_payload.get("usage") or {}


def _split_paper_text(paper_text: str) -> list[str]:
    if not paper_text:
        return [""]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in re.split(r"\n{2,}", paper_text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > REPORT_TEXT_BUDGET:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            for start in range(0, len(paragraph), REPORT_TEXT_BUDGET):
                chunks.append(paragraph[start : start + REPORT_TEXT_BUDGET])
            continue
        projected = current_len + len(paragraph) + (2 if current else 0)
        if current and projected > REPORT_TEXT_BUDGET:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len = projected

    if current:
        chunks.append("\n\n".join(current))

    return chunks or [paper_text[:REPORT_TEXT_BUDGET]]


def _format_char_count(value: int) -> str:
    if value >= 1000:
        return f"{value / 1000:.1f}k"
    return str(value)


def _slug_id(prefix: str, value: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return f"{prefix}-{slug or index}"


def _ensure_code_section(data: dict) -> None:
    sections = data.get("sections") or []
    data["sections"] = sections
    if any((section.get("title") or "").strip() == "Code / Implementation" for section in sections):
        return
    sections.append(
        {
            "id": "section-code-implementation",
            "title": "Code / Implementation",
            "claims": [
                {
                    "id": "section-code-implementation-claim-1",
                    "text": "论文文本中未找到明确的代码开源状态或所用 codebase 说明。",
                    "reliability": "R2",
                    "evidence": [],
                    "uncertainty": "需要检查论文正文、附录或项目页中的代码链接后确认。",
                }
            ],
        }
    )


def _high_signal_text(paper_text: str) -> str:
    if len(paper_text) <= BRIEFING_TEXT_BUDGET:
        return paper_text

    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", paper_text) if paragraph.strip()]
    selected: list[str] = []
    keyword_pattern = re.compile(
        r"\b(abstract|introduction|method|approach|experiment|evaluation|benchmark|dataset|limitation|conclusion)\b",
        re.IGNORECASE,
    )
    for paragraph in paragraphs:
        if keyword_pattern.search(paragraph[:160]):
            selected.append(paragraph)
    if not selected:
        selected = paragraphs[:8] + paragraphs[-4:]

    text = "\n\n".join(selected)
    if len(text) <= BRIEFING_TEXT_BUDGET:
        return text
    half = BRIEFING_TEXT_BUDGET // 2
    return f"{text[:half]}\n\n...\n\n{text[-half:]}"


def _merge_chunk_reports(paper_id: str, reports: list[ReadingReport]) -> ReadingReport:
    if not reports:
        return ReadingReport(paper_id=paper_id)

    sections_by_title: dict[str, dict] = {}
    section_order: list[str] = []
    for report in reports:
        for section in report.sections:
            if section.title not in sections_by_title:
                sections_by_title[section.title] = section.model_dump()
                sections_by_title[section.title]["claims"] = []
                section_order.append(section.title)
            sections_by_title[section.title]["claims"].extend(
                claim.model_dump() for claim in section.claims
            )

    merged = ReadingReport(
        paper_id=paper_id,
        paper_title=next((report.paper_title for report in reports if report.paper_title), None),
        summary=[claim for report in reports for claim in report.summary],
        sections=[
            ReportSection.model_validate(sections_by_title[title])
            for title in section_order
        ],
        related_work=[item for report in reports for item in report.related_work],
    )
    return merged


def _compact_reports_json(reports: list[ReadingReport], *, max_chars: int = 60000) -> str:
    compact = []
    for report in reports:
        compact.append(
            {
                "paper_title": report.paper_title,
                "summary": [
                    _compact_claim(claim)
                    for claim in report.summary[:8]
                ],
                "sections": [
                    {
                        "title": section.title,
                        "claims": [_compact_claim(claim) for claim in section.claims[:5]],
                    }
                    for section in report.sections[:10]
                ],
                "related_work": [
                    {
                        "title": item.title,
                        "relation": item.relation,
                        "source": item.source,
                        "reliability": item.reliability.value,
                        "evidence": [_compact_evidence(ev) for ev in item.evidence[:2]],
                    }
                    for item in report.related_work[:8]
                ],
            }
        )
    payload = json.dumps(compact, ensure_ascii=False)
    if len(payload) <= max_chars:
        return payload
    return payload[: max_chars - 80] + "\n... [truncated for coordinator budget]"


def _compact_claim(claim) -> dict:
    return {
        "id": claim.id,
        "text": claim.text,
        "reliability": claim.reliability.value,
        "evidence": [_compact_evidence(ev) for ev in claim.evidence[:2]],
        "uncertainty": claim.uncertainty,
    }


def _compact_evidence(evidence) -> dict:
    quote = evidence.quote or ""
    return {
        "id": evidence.id,
        "source": evidence.source,
        "page": evidence.page,
        "section": evidence.section,
        "quote": quote if len(quote) <= 600 else quote[:600] + " ...",
    }


def _load_deepseek_config() -> dict:
    config_path = Path(
        os.getenv("DEEPSEEK_CONFIG_PATH")
        or Path.home() / ".deepseek" / "config.toml"
    )
    if not config_path.exists():
        return {}

    values = {}
    for line in config_path.read_text(encoding="utf-8").splitlines():
        match = re.match(r'^\s*(api_key|base_url|model|default_text_model)\s*=\s*"([^"]*)"', line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def _report_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=10.0,
        read=report_read_timeout_seconds(),
        write=10.0,
        pool=10.0,
    )


def report_read_timeout_seconds() -> float:
    if _report_read_timeout_override is not None:
        return _report_read_timeout_override
    return float(os.getenv("DEEPSEEK_REPORT_READ_TIMEOUT", REPORT_READ_TIMEOUT_SECONDS))


def set_report_read_timeout_seconds(seconds: Optional[float]) -> None:
    global _report_read_timeout_override
    _report_read_timeout_override = seconds
