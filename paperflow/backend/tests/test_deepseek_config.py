from pathlib import Path
import json

from app.deepseek import DeepSeekClient


def test_deepseek_client_loads_deepseek_tui_config(monkeypatch, tmp_path: Path) -> None:
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
    assert client.model == "deepseek-v4-pro"


def test_deepseek_env_key_overrides_missing_config(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.delenv("DEEPSEEK_CONFIG_PATH", raising=False)

    client = DeepSeekClient.from_env()

    assert client is not None
    assert client.api_key == "env-key"
    assert client.model == "deepseek-v4-flash"


def test_deepseek_report_prompt_requires_chinese_explanations(monkeypatch) -> None:
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["payload"] = json
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json_dumps(
                                {
                                    "paper_id": "paper-1",
                                    "paper_title": "Evidence-Aware Workflows",
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
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.deepseek.httpx.post", fake_post)
    client = DeepSeekClient(api_key="key")

    report = client.generate_reading_report(
        paper_id="paper-1",
        source_name="paper.pdf",
        paper_text="Abstract: We introduce an evidence-aware workflow.",
    )

    user_prompt = captured["payload"]["messages"][1]["content"]
    assert "Simplified Chinese" in user_prompt
    assert '"paper_title": string|null' in user_prompt
    assert "evidence.quote must be an exact quote" in user_prompt
    assert "not the PDF filename" in user_prompt
    assert report.paper_title == "Evidence-Aware Workflows"
    assert report.summary[0].text == "本文提出一个带证据的论文阅读工作流。"
    assert report.summary[0].evidence[0].quote == "We introduce an evidence-aware workflow."


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)
