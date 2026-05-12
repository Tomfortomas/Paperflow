from __future__ import annotations

from typing import Callable, Optional, Protocol

from app.deepseek import DeepSeekClient
from app.models import Claim, Evidence, ReadingReport, RelatedWorkItem, ReliabilityLevel, ReportSection


class PaperAgent(Protocol):
    def generate_reading_report(
        self,
        paper_id: str,
        source_name: str,
        paper_text: str,
        on_partial_report: Optional[Callable[["ReadingReport"], None]] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> ReadingReport:
        ...


class DeepSeekPaperAgent:
    def __init__(self, client: DeepSeekClient) -> None:
        self.client = client

    def generate_reading_report(
        self,
        paper_id: str,
        source_name: str,
        paper_text: str,
        on_partial_report: Optional[Callable[[ReadingReport], None]] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> ReadingReport:
        return self.client.generate_reading_report(
            paper_id=paper_id,
            source_name=source_name,
            paper_text=paper_text,
            on_partial_report=on_partial_report,
            on_progress=on_progress,
        )


class DevelopmentFallbackAgent:
    """Development-only fallback used when no DeepSeek API key is configured."""

    def generate_reading_report(
        self,
        paper_id: str,
        source_name: str,
        paper_text: str,
    ) -> ReadingReport:
        first_line = self._first_meaningful_line(paper_text)
        evidence = Evidence(
            id="fallback-evidence",
            source=source_name,
            page=1,
            section="Parsed text",
            quote=first_line,
        )
        return ReadingReport(
            paper_id=paper_id,
            paper_title=None,
            summary=[
                Claim(
                    id="fallback-summary",
                    text=(
                        "当前没有配置 DeepSeek Agent。请设置 DEEPSEEK_API_KEY，"
                        "让 AI Agent 提取论文 claim。"
                    ),
                    reliability=ReliabilityLevel.R2,
                    evidence=[evidence],
                    uncertainty="这不是 AI Agent 解析结果。",
                )
            ],
            sections=[
                ReportSection(
                    id="fallback-agent-required",
                    title="Agent Required",
                    claims=[
                        Claim(
                            id="fallback-agent-required-claim",
                            text="Paperflow 需要 DeepSeek API 配置，才能生成 R0/R1 论文阅读报告。",
                            reliability=ReliabilityLevel.R2,
                            evidence=[evidence],
                            uncertainty="当前没有可用的 DEEPSEEK_API_KEY。",
                        )
                    ],
                )
            ],
            related_work=[
                RelatedWorkItem(
                    id="fallback-related-work",
                    title="Agent 相关工作检索未运行",
                    relation="未运行",
                    source="Development fallback",
                    reliability=ReliabilityLevel.R2,
                    evidence=[evidence],
                )
            ],
        )

    def _first_meaningful_line(self, paper_text: str) -> str:
        for line in paper_text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
        return "没有提取到可用的论文文本。"


class AgentNotConfigured:
    def generate_reading_report(
        self,
        paper_id: str,
        source_name: str,
        paper_text: str,
    ) -> ReadingReport:
        raise RuntimeError("Agent not configured. Set DEEPSEEK_API_KEY or ~/.deepseek/config.toml.")


def default_agent() -> PaperAgent:
    client = DeepSeekClient.from_env()
    if client is not None:
        return DeepSeekPaperAgent(client)
    return AgentNotConfigured()
