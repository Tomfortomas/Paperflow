# SMLThoughts / PaperFlow 当前实现状态

更新时间：2026-05-12

当前状态：

- [x] PaperFlow 已从 V1/V1.1 进入 V2 原型可用状态：Web + TUI 共用 FastAPI 后端，支持本地 PDF / arXiv / URL / Zotero 导入、R0 Reading Report、R1 外部检索、Field Map、R2 Research Insight、Obsidian 导出、多论文比较和任务队列。
- [x] 当前主界面已改成更偏“论文研读台”的 editorial UI：Library-first 首页、Report-first Workspace、持久顶部导航栏、导入状态反馈、论文处理进度、删除/打开动作、重复 arXiv 互斥提醒，以及更有层次的导入工作台面板。
- [x] 已增加统一开发启动脚本：`paperflow/run-dev.sh`，可以同时启动后端 FastAPI 和前端 Vite。
- [x] 已修复论文解析卡在 35% 的主要问题：后端 reload / restart 后会把未完成的 PaperAgent 解析标记为 failed，DeepSeek 报告请求也增加了输入长度预算和 45 秒 read timeout，不再无限挂起。
- [~] V3 第一版 Agent 对话区已实现：Workspace 右侧从 focused Q&A 升级为 transcript + process cards + composer + status 的轻量 Agent Chat；后续还需要 SSE 真流式、持久化 transcript 和真实工具调用过程。
- [x] PDF 阅读器已修复布局溢出问题：阅读器会根据 Workspace 主栏宽度自适应缩放，并保留横向滚动兜底，避免 PDF canvas 覆盖右侧证据 / Agent 对话栏。

说明：

- [x] `[x]` 表示当前 PaperFlow 已经实现，或在现有 Agent / UI / 后端链路中有明确支持。
- [~] `[~]` 表示已经有第一版实现，但还需要继续打磨准确性、交互或 Agent 能力。
- [ ] `[ ]` 表示尚未完成，或仍然只是设计方向。

我想构建一个论文阅读的辅助器。辅助器一般会有一个或多个 Agent 来进行沟通，完成针对于一篇或者多篇论文的解析功能。

##### 基本概念定义

###### 信息可靠性分级

由于信息一般是有边界的，我根据信息来源的可靠性将分为 （Reliability Level）

- [x] R0：完全忠实于原文的信息总结与整理。对数值型信息，不允许超出本文数据之外进行联想或者上网浏览其他文章的结果。对概念性信息，允许有使用你储备的知识进行理解后对原文内容进行梳理。
- [x] R1：根据本文提到的 related works 使用外部检索工具阅读相关工作的文章后，忠实于搜到的文章提取出的信息。当前已经接入 Semantic Scholar、OpenAlex fallback、Papers with Code，以及本地 references parser。
- [x] R2：根据自己的理解和网上各种论坛评论的理解所得出的概念性、前瞻性的信息。当前通过 Research Insight Agent 输出趋势、机会、方法角度、论文故事线和写作 scaffold，并在 UI / Obsidian 中显式标注 R2。

##### 特性设计

###### 关键内容提取

- [x] 能够根据我设置的、想要了解的【关注点】获取论文中关注点对应的表述和内容。本部分的信息级别已经标注在前面。
  - [x] 【R0】本文的任务是什么？本文的任务是自己新定义的还是已经定义好的？
  - [x] 【R0】本文的数据集是什么？是自己采集的还是开源的？
  - [x] 【R0, R1】本文的 benchmark 和 metric 是什么？这个 benchmark 和数据集相关还是不相关？
  - [~] 【R0】本文的模型是怎么设计的？本文模型的参数量有多大？当前 Reading Report 有 Method / Compute / Training 段落；参数量如果原文未明确报告，仍要求 Agent 不猜测。
  - [x] 【R0】模型具体功能是什么，输入输出具体是什么形式，什么模态？
  - [x] 【R0】本文的计算资源是什么？训练量有多大？
  - [x] 【R0】本文提出的方法的优势是什么？有什么缺点？当前通过 Method / Limitations / summary claims 抽取。
  - [x] 【R0, R1】本文总结的之前工作的问题主要是什么，本文有什么理论、方法论层面的关键发现。当前 R0 来自当前论文 related-work / limitation 表述，R1 来自外部 related-work search。

###### 领域内容联想

- [x] 【R1】能够根据本文所处的领域/任务联想到本领域/任务的若干关键论文和发展脉络。这部分主要帮助研究者获取对技术演变的视野。
  - [x] 有哪些 milestone papers？
    - [x] 如何识别 milestone papers？当前根据 citation count、influential citations、citation velocity、venue、category、benchmark/survey/system/theory 等信号做启发式排序。
    - [ ] Human-in-the-loop milestone 确认尚未完成。
  - [x] 领域技术如何随着时间的推移而演变？
    - [x] 当前已生成技术时间线：把 seed、milestones、follow-up、benchmark、survey 事件按年份排序。
    - [x] 已生成前后关系图：前置基础来自 references/backward lane；后续影响来自 citations/cited-by/forward/follow-up lane，不再简单按年份判断。
    - [~] 关系图仍需要进一步升级为 Agent 理解后构建，不能长期只依赖 R1 lane 规则。
  - [x] 如何梳理技术发展脉络？
    - [x] 当前 Field Map 输出：领域摘要、任务定义、数据集/benchmark、metrics、方法家族、里程碑论文、技术时间线、前后关系图、open problems、recent trends、research opportunities。
    - [~] 更细的 problem evolution / method evolution / evaluation evolution 仍可继续增强。

- [x] 【R1】能够根据本文所处的领域/任务联想到本领域/任务的重要问题。这部分主要帮助研究者获取对重要问题的视野。
  - [~] 这个领域的终极目标是什么？当前可由 R2 insight 总结，但仍需要更强 evidence grounding。
  - [x] 该领域已经达到了什么水平？当前可从 benchmark / recent trends / milestone papers 中抽取。
  - [x] 还有哪些重要的问题仍未被解决？当前从 R0 limitations 和 Field Map open problems 生成。
  - [x] 现阶段的热点话题是什么？当前从 recent R1 candidates 和 Research Insight Agent 生成。
- [x] 【R2】获取领域的视野为课题选择、方法设计、实验迭代、故事梳理、论文写作打下基础。
- [x] 【R2】能够获取和讲解该领域/任务的最新文章，整理技术的演变轨迹。

##### 当前已经实现但原始 SMLThoughts 没有单独列出的能力

- [x] 导入本地 PDF。
- [x] 从 arXiv ID / URL 导入论文。
- [x] 从 DOI / Semantic Scholar / OpenReview URL 解析元数据并下载。
- [x] 从本地 Zotero 库导入。
- [x] 使用 DeepSeek-backed PaperAgent 生成结构化 Reading Report。
- [x] 每条 claim 带 R0/R1/R2 可靠性标签。
- [x] 每条 claim 可带 evidence quote、source、page，并通过 PDF parser / EvidenceVerifier 尝试定位 bbox / location_status。
- [x] Report 持久化到本地 JSON，后端重启后可以恢复。
- [x] 导出 Obsidian-native Markdown note。
- [x] 同内容 PDF / DOI / arXiv ID 等重复导入时只保留一个记录；同一 arXiv 编号不同版本会互斥，并在前端提示疑似重复。
- [x] Library 页面展示已导入论文。
- [x] 删除论文：清理 library entry、session、PDF、report、chunks、R1 cache、Obsidian note、对应 Field Map。
- [x] 处理状态反馈：显示上传 / 下载 / metadata 解析 / Agent 解析 / 慢任务提示 / 完成 / 失败。
- [x] 解析卡死恢复：如果后端在 PaperAgent 解析期间 reload / restart，启动时会识别没有 report 的 queued / processing 论文并标记为 failed，提示用户 rerun。
- [x] DeepSeek 调用保护：Reading Report prompt 限制输入文本预算，报告生成请求使用明确 read timeout，超时后在 UI 中展示失败状态。
- [x] 持久顶部导航栏：Home 与 Workspace 均可快速跳转。
- [x] 导入区 UI 层次优化：取消“导入论文”区域中生硬的多条横线，改为浅色工作台面板和四个轻量入口块，通过留白、淡边界和 hover 建立层次。
- [x] 统一本地开发脚本：`paperflow/run-dev.sh` 同时启动后端和前端。
- [x] TUI 客户端：支持 Library / Workspace / R1 / Field Map / Obsidian 基本流程。
- [x] 多论文比较：按 Task / Dataset / Benchmark / Method / Compute / Result / Limitations / Availability 生成对比表。
- [x] Field Map Obsidian note 导出。
- [x] 持久任务队列：支持 task list / cancel / retry / restart recovery。

##### 当前仍需要推进的能力

- [x] Agent 对话区第一版：已实现类似 DeepSeek-TUI 的 transcript + composer + running/status/process cards，让用户可以边读文章边和 AI Agent 动态对话。
- [x] Agent 对话过程展示第一版：已显示读取报告、定位证据、检查 R1 上下文、生成回答等轻量 process cards。
- [x] Agent 对话输出继续保持 R0/R1/R2 和 evidence 约束，不退化成普通聊天。
- [ ] Agent 对话真流式：当前只是步骤状态的“流式感”，尚未实现 SSE / WebSocket token streaming。
- [ ] 对话历史持久化：当前 Agent Chat transcript 仍是前端会话内状态，尚未持久化到 SQLite。
- [ ] 关系图 / 脉络图需要进一步改成 Agent 理解和分析后构建；当前已经修正为按 R1 引用方向区分 predecessor / successor，但还不是完整语义理解。
- [ ] Human-in-the-loop：milestone / relationship graph / Field Map 中关键判断应支持人工确认和修正。
- [ ] 更强 PDF 交互：长文阅读、跨页高亮、多 evidence 定位、figure/table 级引用仍需增强。
- [ ] 更强综述能力：跨多篇论文自动生成系统综述、研究空白、实验路线和写作计划仍需增强。
