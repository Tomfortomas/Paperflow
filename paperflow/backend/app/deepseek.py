from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import Optional

import httpx

from app.models import ReadingReport


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
            or config.get("default_text_model")
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
    ) -> ReadingReport:
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
            "filename. If the title is unclear, return null.\n\n"
            f"paper_id: {paper_id}\n"
            f"source_name: {source_name}\n"
            f"paper_text:\n{paper_text[:18000]}"
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
            timeout=120,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        data["paper_id"] = paper_id
        self._fill_missing_sources(data, source_name)
        return ReadingReport.model_validate(data)

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
