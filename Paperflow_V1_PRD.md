# Paperflow V1 PRD

## 1. Product Vision

Paperflow 是一个面向 AI 研究者和工程师的论文阅读 IDE。它的目标不是替代研究者的判断，而是自动化论文搜集、结构化梳理、证据定位和 related work 扩展中重复、耗时、但可以被系统化完成的部分，帮助用户更高效、更深度地理解论文，并逐步成为一个领域的专家。

AI 研究者和工程师在今天常常是同一个角色：他们既需要读论文、理解方法、判断实验设置，也需要快速把论文中的结论转化为实现、实验设计、技术选型和研究判断。Paperflow 的核心价值是把“读论文”从一次性的聊天问答，变成一个可追溯、可缓存、可继续扩展的研究工作流。

## 2. Target Users

V1 的目标用户是 AI 研究者和 AI 工程师，尤其是需要频繁阅读论文、跟踪技术进展、复现实验或寻找研究方向的人。

典型用户包括：

- 正在进入一个新领域，需要快速建立领域地图的研究者。
- 需要读懂一篇论文并判断其方法、数据集、benchmark 和实验可信度的研究者。
- 需要从论文中提取实现细节、模型输入输出、训练资源和实验设置的工程师。
- 需要整理 related work、发现 limitation、寻找后续 idea 的研究者/工程师。

## 3. Core User Problems

目标用户通常有能力自己搜集、阅读和梳理论文，但这个过程需要消耗大量时间。很多步骤本质上是重复性的，可以通过工具自动化或半自动化完成。

核心痛点包括：

- 阅读一篇论文时，需要反复在 PDF、笔记、搜索引擎、Papers with Code、Google Scholar、arXiv 等工具之间切换。
- 论文里的任务、数据集、benchmark、metric、模型结构、训练资源和限制经常分散在不同 section、table、appendix 中，手动整理很慢。
- LLM 可以快速总结论文，但如果没有证据定位，用户很难判断回答是否忠实于原文。
- Related work 的扩展搜索很耗时：需要从 references、cited-by、benchmark、dataset、survey 等多条线索追踪。
- 用户想要的不只是“这篇论文讲了什么”，还包括“这篇论文在领域中处于什么位置”和“它对我的研究/实现有什么启发”。

## 4. V1 Product Thesis

V1 先聚焦单篇论文深度阅读：用户导入一篇 PDF 后，Paperflow 自动生成带证据定位的 R0 Reading Report，并基于该论文自动扩展一层 R1 related work context。用户可以围绕关注点追问，系统回答需要保留可靠性等级、来源和证据。

V1 的成功标准不是覆盖完整文献管理，而是让用户在读一篇论文时更快得到可信、结构化、可追溯的理解。

## 5. V1 Core Workflow

```text
导入 PDF
→ 解析论文文本、页码、section、table、references
→ 生成 R0 Reading Report
→ 每条关键 claim 绑定 evidence 和 PDF 跳转位置
→ 自动执行轻量 R1 related work 扩展
→ 用户在右侧 Agent 面板按关注点追问
→ 回答继续标注 R0/R1/R2、source、evidence、uncertainty
→ 结果缓存为本地 session 和 Markdown report
```

用户导入 PDF 后，系统默认自动执行完整 V1 流程：先解析 PDF，再生成 R0 Reading Report；R0 完成后，自动启动轻量 R1 related work 扩展。用户不需要手动点击生成报告，但需要能够随时暂停、取消、重试或只查看已经完成的 R0 结果。

## 6. V1 Scope

V1 必须支持：

- 导入或打开本地 PDF。
- 解析 PDF 的正文、页码、section、table、references。
- 生成单篇论文的 R0 Reading Report。
- 对 Reading Report 中的重要结论提供 evidence。
- 点击 evidence 后跳转到 PDF 中对应位置。
- 支持用户按关注点追问，例如 dataset、benchmark、model design、compute、limitation。
- 自动执行一层 R1 related work 搜索，至少覆盖 references 和公开搜索入口。
- 对所有回答标注 R0/R1/R2 信息可靠性等级。
- 缓存 PDF 解析结果、Reading Report、用户追问和 Agent 回答。
- 支持将阅读结果保存为 Obsidian-native Markdown note。

## 7. V1 Non-goals

V1 暂不做：

- 完整 Zotero 替代品。
- 大规模文献库管理。
- 多人协作。
- 复杂 citation graph 编辑器。
- 完整领域知识图谱。
- 自动论文复现。
- 自动实验运行。
- 投稿级 related work 写作。
- 多论文系统综述生成。

这些能力可以作为 V2/V3 的扩展方向。

## 8. Reliability Model

Paperflow 使用 R0/R1/R2 来区分信息来源和可靠性。

- R0：完全忠实于当前论文原文的信息总结与整理。R0 信息必须尽量绑定 PDF 中的 evidence，例如页码、section、paragraph、figure、table 或 appendix。
- R1：根据当前论文 references、related work、cited-by 或外部搜索得到的相关论文信息。R1 信息需要绑定 source paper、venue/year、URL 和证据位置。
- R2：基于模型理解、趋势判断、论坛讨论或研究经验得到的概念性、前瞻性信息。R2 必须显式标注为推断或建议。

每个重要输出应尽量包含：

- Claim：结论。
- Reliability Level：R0 / R1 / R2。
- Evidence：支撑该结论的证据。
- Source：来源，例如当前论文、引用论文、Google Scholar、Semantic Scholar、Papers with Code、OpenReview。
- Uncertainty：不确定性、缺失信息或需要人工确认的地方。

UI 中默认采用轻量标签展示可靠性：

- 每条 claim 旁边显示 R0/R1/R2 badge。
- R0/R1/R2 使用颜色区分，但不打断阅读。
- 点击 badge 或 evidence 入口后，展开 source、evidence、uncertainty。
- 缺少证据时显示 missing evidence。
- R2 内容需要显式标注为推断或建议。

## 9. Reading Report Schema

V1 的 R0 Reading Report 采用两级结构：顶部是 Executive Summary，下面是可展开的详细模块卡片。这样用户可以先快速理解论文，再进入 task、dataset、benchmark、method、evidence 等细节。

Executive Summary 默认包含：

- 这篇论文解决的问题。
- 论文最核心的方法想法。
- 论文使用的数据集和 benchmark。
- 论文最重要的实验结论。
- 论文最关键的限制或风险。
- 这篇论文在 related work 中的大致位置。

详细模块默认包含：

- Paper metadata：标题、作者、年份、venue/arXiv 信息。
- Task：本文解决什么任务，任务是否由本文新定义。
- Dataset：使用了哪些数据集，数据集是自建还是公开。
- Benchmark / Metric：使用了哪些 benchmark 和 metric，它们与数据集/任务的关系是什么。
- Method：模型或方法的核心设计。
- Input / Output：模型输入输出形式、模态、数据格式。
- Model Scale：参数量、模型规模、组件规模。
- Compute / Training：训练资源、训练量、训练时长、硬件设置。
- Key Results：主要实验结果和结论。
- Strengths：论文声称的方法优势。
- Limitations：论文承认的限制，以及从 R0/R1 可支持的缺点。
- Related Work Claims：论文如何总结前人工作的问题。
- Evidence Index：关键 claim 到 PDF 证据的映射。

每个详细模块都应采用卡片式结构：

- 3-5 条核心结论。
- 每条结论带 R0/R1/R2 标签。
- 每条结论带 evidence 入口。
- 找不到证据时显示 missing evidence，而不是猜测。
- 用户可以直接对该模块追问。

## 10. R1 Related Work Scope

V1 自动执行轻量 R1 related work 扩展。目标不是完整领域综述，而是帮助用户理解当前论文周围的一层上下文。

R1 扩展优先包括：

- 当前论文 references 中的高相关论文。
- 当前论文 related work 中反复出现的任务、方法、数据集和 benchmark。
- 通过公开搜索入口找到的 cited-by / follow-up papers。
- Papers with Code 中与 task、dataset、benchmark 相关的代表性方法。
- arXiv / Semantic Scholar / OpenAlex 中最近 1-2 年的相关论文。

R1 输出需要标注它与当前论文的关系，例如 foundational work、baseline、competitor、follow-up、benchmark paper、survey。

## 11. UX Direction

V1 采用轻量论文阅读 IDE，而不是纯聊天机器人。

V1 首屏采用 Library first，而不是直接进入空白聊天或空白工作区。用户第一次打开 Paperflow 时，应该先看到论文库、最近阅读论文、导入入口和已有阅读报告。选择或导入一篇论文后，再进入单篇 Paper Workspace。

Library 在长期形态上应接近 Obsidian-native vault，而不是封闭数据库。PDF、阅读报告、paper metadata、相关链接和用户笔记都应该能够以本地文件和 Markdown 的形式沉淀下来。

Library 页面应包含：

- Import PDF：导入本地论文。
- Recent Papers：最近打开或处理过的论文。
- Processing Status：正在解析、正在生成报告或失败的任务。
- Saved Reports：已经生成的 Obsidian-native Markdown reading reports。
- Search / Filter：按标题、作者、tag、任务或领域搜索本地论文。

导入论文后的默认行为：

- 自动创建 paper session。
- 自动解析 PDF。
- 自动生成 R0 Reading Report。
- R0 完成后自动启动轻量 R1 related work 扩展。
- 在 Library 和 Workspace 中都显示任务进度。
- 用户可以暂停、取消、重试或只保留 R0 结果。

Paper Workspace 推荐三栏结构：

- 左侧：项目/论文导航，包含最近论文、当前 paper session、生成的 Markdown report。
- 中间：PDF 阅读器，支持页码定位、文本选中、evidence 高亮和跳转。
- 右侧：默认优先展示结构化 Reading Report，Chat 作为围绕报告和证据的辅助追问入口，同时展示 Evidence Cards、Related Work 和任务进度。

右侧面板采用 Report first：

- 默认视图是 Reading Report，而不是空白聊天窗口。
- 每个 report section 可以展开/折叠，例如 Task、Dataset、Benchmark、Method、Compute、Limitations。
- 每条关键 claim 旁边显示 R0/R1/R2 标签和 evidence 跳转入口。
- R0/R1/R2 默认以轻量 badge 形式展示，点击后再展开证据详情。
- Chat 输入框服务于当前上下文，用户可以对某个 section、claim、PDF 选区或整篇论文追问。
- 自动流程仍然以 task progress 的形式显示，但完成后主视图回到 Reading Report。

核心 UX 原则：

- 所有结论都要尽量可追溯。
- R0/R1/R2 标签在 UI 中必须明显。
- 用户应该能从结构化结论一键跳回 PDF 原文。
- Agent 的长任务需要流式展示进度，避免用户等待时不知道系统在做什么。
- 缓存结果应该默认可复用，减少重复解析和重复提问。
- 阅读结果应该自然沉淀为 Obsidian-native note，方便用户长期维护个人研究知识库。

## 12. Agent Workflow

V1 可以借鉴 DeepSeek-TUI 的 agent loop 思路，但产品形态保持为论文阅读 IDE。

推荐模块：

- PDF Parser：解析 PDF 文本、页码、section、table、references。
- Paper Parser Agent：只负责 R0 信息抽取，严格基于当前论文。
- Evidence Verifier Agent：检查每个 claim 是否有证据位置，是否出现过度推断。
- Citation Explorer Agent：基于 references、related work 和 cited-by 做 R1 扩展。
- Benchmark Agent：围绕 task、dataset、metric、leaderboard 查找可比较工作。
- Answer Agent：根据用户关注点生成带 R0/R1/R2 标签的回答。
- Cache Manager：缓存解析结果、报告、证据映射和问答历史。

## 13. Technical Direction

V1 使用 DeepSeek API 作为模型后端。

推荐策略：

- 简单抽取、分类、chunk 级总结优先使用更快、更便宜的 DeepSeek 模型。
- 复杂综合、跨 section 对齐、R1 synthesis 再使用更强模型。
- 所有长任务通过后台 task queue 执行，并通过 SSE/WebSocket 向前端流式返回状态。
- 所有报告和中间结果本地缓存，避免重复消耗 token 和时间。

推荐工程形态：

- Frontend：React + Vite + PDF.js。
- Backend：FastAPI + DeepSeek API client + task queue。
- Storage：SQLite 存 session、claim、evidence、paper metadata；本地 vault 存 PDF、Obsidian-native Markdown report 和用户笔记。
- Later：向量数据库、GROBID、citation graph、Obsidian vault integration。

## 14. Obsidian-native Knowledge Base

V1 的阅读结果应优先沉淀为 Obsidian-native Markdown，而不是普通导出文件。

每篇论文可以对应一个 note，包含：

- YAML frontmatter：title、authors、year、venue、arxiv、doi、tags、status、reliability。
- PDF link：链接到本地 PDF。
- Executive Summary。
- R0 Reading Report。
- R1 Related Work Context。
- Evidence Index。
- User Questions。
- Follow-up Ideas。

推荐使用 Obsidian 友好的语法：

- `[[wikilinks]]` 连接论文、任务、数据集、benchmark、方法和研究方向。
- `#tags` 标注领域、任务、阅读状态和可靠性。
- Callouts 展示 warning、missing evidence、open question。
- Markdown headings 保持可折叠、可搜索、可长期维护。

Paperflow 不需要在 V1 完整复刻 Obsidian，但应该让用户生成的研究资产可以直接进入 Obsidian vault，并随着阅读积累形成个人研究知识库。

## 15. Success Metrics

V1 可以用以下指标判断是否成功：

- 用户导入一篇论文后，首次 R0 Reading Report 生成时间足够短。
- Reading Report 中主要 claim 的 evidence 覆盖率足够高。
- 用户能够点击关键结论跳回 PDF 原文。
- 用户针对 dataset、benchmark、method、compute、limitation 的追问能得到结构化回答。
- 用户认为系统显著减少了手动整理论文的时间。
- 用户愿意把生成的 Obsidian-native Markdown report 保存为长期研究笔记。

## 16. Future Versions

后续版本可以扩展：

- 更完整的 Field Map。
- Connected Papers 式领域图谱。
- 多论文对比阅读。
- Benchmark / leaderboard 自动追踪。
- Obsidian vault 双链同步。
- Zotero integration。
- 自动生成 related work 草稿。
- 从论文阅读到实验计划、复现计划和研究 idea 的完整工作流。
