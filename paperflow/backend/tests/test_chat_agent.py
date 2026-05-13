from __future__ import annotations

import json

import httpx

from app.chat_agent import generate_chat_response
from app.deepseek import DeepSeekClient
from app.models import Claim, Evidence, PaperChatRequest, ReadingReport, ReliabilityLevel, ReportSection
from app.web_search import WebSearchResult


class _FakeWebSearch:
    def __init__(self, results: list[WebSearchResult]) -> None:
        self.results = results
        self.queries: list[str] = []

    def search(self, query: str, limit: int = 5) -> list[WebSearchResult]:
        self.queries.append(query)
        return self.results[:limit]


def _report() -> ReadingReport:
    evidence = Evidence(id="ev-1", source="paper.pdf", page=1, quote="The paper studies R1 context.")
    return ReadingReport(
        paper_id="paper-1",
        paper_title="Paperflow",
        summary=[
            Claim(
                id="summary-1",
                text="Paperflow grounds answers in paper evidence.",
                reliability=ReliabilityLevel.R0,
                evidence=[evidence],
            )
        ],
        sections=[
            ReportSection(
                id="method",
                title="Method",
                claims=[
                    Claim(
                        id="method-1",
                        text="The method reads reports before chatting.",
                        reliability=ReliabilityLevel.R0,
                        evidence=[evidence],
                    )
                ],
            )
        ],
        related_work=[],
    )


def test_generate_chat_response_auto_uses_web_search_for_broad_questions() -> None:
    web = _FakeWebSearch(
        [
            WebSearchResult(
                title="Reinforcement learning overview",
                url="https://example.com/rl",
                snippet="Reinforcement learning studies agents that learn by rewards.",
            )
        ]
    )

    response = generate_chat_response(
        paper_id="paper-1",
        chat_id="chat-paper-1",
        question="请介绍一下什么是强化学习",
        request=PaperChatRequest(question="请介绍一下什么是强化学习"),
        report=_report(),
        web_search_client=web,
    )

    assert web.queries
    assert web.queries[0] == "请介绍一下什么是强化学习"
    assert "web_search" in response.used_context
    assert any(step.label == "Web search" and step.status == "completed" for step in response.steps)
    assert response.answer.evidence[0].source == "https://example.com/rl"
    assert response.answer.reliability == ReliabilityLevel.R2


def test_generate_chat_response_can_web_search_even_with_selected_claim_for_broad_questions() -> None:
    web = _FakeWebSearch(
        [
            WebSearchResult(
                title="Reinforcement learning overview",
                url="https://example.com/rl",
                snippet="Reinforcement learning studies agents that learn by rewards.",
            )
        ]
    )

    response = generate_chat_response(
        paper_id="paper-1",
        chat_id="chat-paper-1",
        question="请介绍一下什么是强化学习",
        request=PaperChatRequest(question="请介绍一下什么是强化学习", selected_claim_id="summary-1"),
        report=_report(),
        web_search_client=web,
    )

    assert web.queries
    assert "web_search" in response.used_context
    assert response.answer.evidence[0].source == "https://example.com/rl"


def test_generate_chat_response_skips_web_search_for_selected_claim_questions() -> None:
    web = _FakeWebSearch([])

    response = generate_chat_response(
        paper_id="paper-1",
        chat_id="chat-paper-1",
        question="解释这条 claim",
        request=PaperChatRequest(question="解释这条 claim", selected_claim_id="summary-1"),
        report=_report(),
        web_search_client=web,
    )

    assert web.queries == []
    assert "web_search" not in response.used_context
    assert any(step.label == "Web search" and step.status == "skipped" for step in response.steps)


def test_generate_chat_response_allows_model_knowledge_for_broad_questions(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "answer": {
                                        "text": "强化学习是一类通过奖励信号学习决策策略的方法。",
                                        "reliability": "R2",
                                        "evidence": [],
                                        "uncertainty": "这是通用背景知识，不是当前论文证据。",
                                    }
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("app.chat_agent.httpx.post", fake_post)

    response = generate_chat_response(
        paper_id="paper-1",
        chat_id="chat-paper-1",
        question="请你介绍一下什么是强化学习",
        request=PaperChatRequest(question="请你介绍一下什么是强化学习"),
        report=_report(),
        client=DeepSeekClient(api_key="test", base_url="https://deepseek.example"),
        web_search_client=_FakeWebSearch([]),
    )

    prompt = captured["json"]["messages"][1]["content"]
    assert "general model knowledge" in prompt
    assert "model_knowledge" in response.used_context
    assert response.answer.text == "强化学习是一类通过奖励信号学习决策策略的方法。"
    assert response.answer.reliability == ReliabilityLevel.R2
