from pathlib import Path
import json
import time

from app.deepseek import DeepSeekClient, _compact_reports_json, _split_paper_text
from app.models import Claim, Evidence, ReadingReport, ReliabilityLevel, ReportSection


def test_deepseek_client_uses_paperflow_flash_default_with_deepseek_tui_config(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'api_key = "config-key"\n'
        'base_url = "https://api.deepseek.com/beta"\n'
        'default_text_model = "deepseek-v4-pro"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_CONFIG_PATH", str(config_path))

    client = DeepSeekClient.from_env()

    assert client is not None
    assert client.api_key == "config-key"
    assert client.base_url == "https://api.deepseek.com/beta"
    assert client.model == "deepseek-v4-flash"


def test_deepseek_env_key_overrides_missing_config(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.delenv("DEEPSEEK_CONFIG_PATH", raising=False)

    client = DeepSeekClient.from_env()

    assert client is not None
    assert client.api_key == "env-key"
    assert client.model == "deepseek-v4-flash"


def test_deepseek_report_prompt_requires_chinese_explanations(monkeypatch) -> None:
    captured = {"prompts": []}
    monkeypatch.delenv("DEEPSEEK_REPORT_READ_TIMEOUT", raising=False)

    def fake_post(url, headers, json, timeout):
        prompt = json["messages"][1]["content"]
        captured["prompts"].append(prompt)
        captured["timeout"] = timeout
        if "fast paper briefing" in prompt:
            content = {
                "paper_title": "Evidence-Aware Workflows",
                "task": "paper reading",
                "method": "evidence-aware workflow",
                "datasets": [],
                "benchmarks": [],
                "key_terms": ["R0"],
                "open_questions": [],
            }
        else:
            content = _report_payload()
        return FakeResponse(
            {
                "choices": [{"message": {"content": json_dumps(content)}}],
                "usage": {"prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168},
            }
        )

    monkeypatch.setattr("app.deepseek.httpx.post", fake_post)
    client = DeepSeekClient(api_key="key")

    report = client.generate_reading_report(
        paper_id="paper-1",
        source_name="paper.pdf",
        paper_text="Abstract: We introduce an evidence-aware workflow.",
    )

    chunk_prompt = next(prompt for prompt in captured["prompts"] if "paper_text:" in prompt)
    assert "Simplified Chinese" in chunk_prompt
    assert '"paper_title": string|null' in chunk_prompt
    assert "evidence.quote must be an exact quote" in chunk_prompt
    assert "not the PDF filename" in chunk_prompt
    assert "paper_briefing:" in chunk_prompt
    assert any("coordinator" in prompt.lower() for prompt in captured["prompts"])
    assert captured["timeout"].read == 90
    assert report.paper_title == "Evidence-Aware Workflows"
    assert report.agent_run is not None
    assert report.agent_run.model == "deepseek-v4-flash"
    assert report.agent_run.total_tokens == 504
    assert report.summary[0].text == "本文提出一个带证据的论文阅读工作流。"
    assert report.summary[0].evidence[0].quote == "We introduce an evidence-aware workflow."


def test_deepseek_pipeline_uses_briefing_and_bounded_parallel_chunk_prompts(monkeypatch) -> None:
    captured = {"prompts": []}

    def fake_post(url, headers, json, timeout):
        prompt = json["messages"][1]["content"]
        captured["prompts"].append(prompt)
        if "fast paper briefing" in prompt:
            content = {"paper_title": "Long Paper", "task": "long paper", "key_terms": []}
        else:
            content = _report_payload(paper_title="Long Paper")
        return FakeResponse({"choices": [{"message": {"content": json_dumps(content)}}]})

    monkeypatch.setattr("app.deepseek.httpx.post", fake_post)
    client = DeepSeekClient(api_key="key")

    client.generate_reading_report(
        paper_id="paper-1",
        source_name="paper.pdf",
        paper_text="A" * 50000,
    )

    chunk_prompts = [prompt for prompt in captured["prompts"] if "paper_text:" in prompt]
    assert len(chunk_prompts) > 1
    assert all("paper_briefing:" in prompt for prompt in chunk_prompts)
    assert all(len(prompt) < 17000 for prompt in chunk_prompts)
    assert any("A" * 1000 in prompt for prompt in chunk_prompts)
    assert any("coordinator" in prompt.lower() for prompt in captured["prompts"])


def test_deepseek_parallel_partial_coverage_tracks_completed_chunks(monkeypatch) -> None:
    paper_text = "A" * 11000 + "\n\n" + "B" * 5000
    chunks = _split_paper_text(paper_text)
    partials = []
    client = DeepSeekClient(api_key="key")

    monkeypatch.setattr(client, "_generate_paper_briefing", lambda **_: ({}, {}))
    monkeypatch.setattr(client, "_synthesize_report", lambda **kwargs: (kwargs["draft"], {}))

    def fake_chunk_report(**kwargs):
        if kwargs["chunk_index"] == 0:
            time.sleep(0.05)
        return _small_report("paper-1", kwargs["source_name"], kwargs["chunk_index"]), {}

    monkeypatch.setattr(client, "_generate_chunk_report", fake_chunk_report)

    client.generate_reading_report(
        paper_id="paper-1",
        source_name="paper.pdf",
        paper_text=paper_text,
        on_partial_report=partials.append,
    )

    assert partials
    assert partials[0].agent_run is not None
    assert partials[0].agent_run.covered_chars == len(chunks[1])


def test_deepseek_coordinator_context_is_compacted() -> None:
    reports = []
    for index in range(40):
        report = _small_report("paper-1", "paper.pdf", index)
        report.summary[0].text = "claim " + ("x" * 2000)
        report.summary[0].evidence[0].quote = "quote " + ("y" * 2000)
        reports.append(report)

    payload = _compact_reports_json(reports, max_chars=6000)

    assert len(payload) <= 6100
    assert "truncated for coordinator budget" in payload


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _report_payload(paper_title: str = "Evidence-Aware Workflows") -> dict:
    return {
        "paper_id": "paper-1",
        "paper_title": paper_title,
        "summary": [
            {
                "id": "summary-1",
                "text": "本文提出一个带证据的论文阅读工作流。",
                "reliability": "R0",
                "evidence": [
                    {
                        "id": "e1",
                        "source": "paper.pdf",
                        "page": 1,
                        "section": "Abstract",
                        "quote": "We introduce an evidence-aware workflow.",
                    }
                ],
                "uncertainty": None,
            }
        ],
        "sections": [],
        "related_work": [
            {
                "id": "rw-1",
                "title": "Elicit",
                "relation": "可作为结构化论文抽取工具的对照。",
                "source": "Related work",
                "reliability": "R1",
                "evidence": [],
            }
        ],
    }


def _small_report(paper_id: str, source_name: str, index: int) -> ReadingReport:
    evidence = Evidence(
        id=f"e{index}",
        source=source_name,
        page=1,
        quote=f"Evidence quote {index}",
    )
    return ReadingReport(
        paper_id=paper_id,
        paper_title="Small Paper",
        summary=[
            Claim(
                id=f"summary-{index}",
                text=f"Claim {index}",
                reliability=ReliabilityLevel.R0,
                evidence=[evidence],
            )
        ],
        sections=[
            ReportSection(
                id=f"section-{index}",
                title="Task",
                claims=[
                    Claim(
                        id=f"section-claim-{index}",
                        text=f"Section claim {index}",
                        reliability=ReliabilityLevel.R0,
                        evidence=[evidence],
                    )
                ],
            )
        ],
    )
