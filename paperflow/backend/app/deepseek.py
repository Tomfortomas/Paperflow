from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import Callable, Optional

import httpx

from app.models import AgentRunMetrics, ReadingReport, ReportSection


REPORT_TEXT_BUDGET = 12000
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
    ) -> ReadingReport:
        chunks = _split_paper_text(paper_text)
        reports: list[ReadingReport] = []
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        saw_usage = False

        for index, chunk in enumerate(chunks):
            report, usage = self._generate_chunk_report(
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

    def _generate_chunk_report(
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
            "Compute / Training, Limitations. If evidence is missing, create an R2 claim "
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
        data["paper_id"] = paper_id
        self._fill_missing_sources(data, source_name)
        report = ReadingReport.model_validate(data)
        return report, response_payload.get("usage") or {}

    def _fill_missing_sources(self, data: dict, source_name: str) -> None:
        for claim in data.get("summary", []):
            self._fill_claim_sources(claim, source_name)
        for section in data.get("sections", []):
            for claim in section.get("claims", []):
                self._fill_claim_sources(claim, source_name)
        for item in data.get("related_work", []):
            for evidence in item.get("evidence", []):
                evidence.setdefault("source", source_name)

    def _fill_claim_sources(self, claim: dict, source_name: str) -> None:
        for evidence in claim.get("evidence", []):
            evidence.setdefault("source", source_name)


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
