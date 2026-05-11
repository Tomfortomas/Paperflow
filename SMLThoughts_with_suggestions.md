我想构建一个论文阅读的辅助器。辅助器一般会有一个或多个 Agent 来进行沟通，完成针对于一篇或者多篇论文的解析功能。

##### 基本概念定义

###### 信息可靠性分级

由于信息一般是有边界的，我根据信息来源的可靠性将分为 （Reliability Level）

- R0：完全忠实于原文的信息总结与整理。对数值型信息，不允许超出本文数据之外进行联想或者上网浏览其他文章的结果。对概念性信息，允许有使用你储备的知识进行理解后对原文内容进行梳理。
- R1：根据本文提到的 related works 使用 web search 工具阅读相关工作的文章后，忠实于搜到的文章提取出的信息。此时提取出的信息相对于搜到的相关文章而言是 R0 级别的信息。
- R2：根据自己的理解和网上各种论坛评论的理解所得出的概念性、前瞻性的信息。

###### 信息输出的证据约束

- 对于 R0 和 R1 信息，辅助器除了输出结论之外，还应该尽量输出可追溯的证据位置。
  - R0 信息需要绑定到当前论文中的 section、page、paragraph、figure、table 或 appendix。
  - R1 信息需要绑定到被检索论文的标题、作者、年份、venue、URL，以及该论文中的具体证据位置。
  - R2 信息需要显式标注为推断、经验判断或趋势判断，避免和 R0/R1 的事实性信息混在一起。

- 可以要求 Agent 对每个重要结论使用统一结构：
  - Claim：提取出的结论。
  - Reliability Level：R0 / R1 / R2。
  - Evidence：支撑该结论的原文证据。
  - Source：信息来源，例如当前论文、引用论文、Google Scholar、Semantic Scholar、Papers with Code、OpenReview 等。
  - Uncertainty：是否存在不确定性、缺失信息或需要人工确认的地方。

##### 特性设计

###### 关键内容提取

- 能够根据我设置的、想要了解的【关注点】获取论文中关注点对应的表述和内容。本部分的信息级别已经标注在前面。
  - 【R0】本文的任务是什么？本文的任务是自己新定义的还是已经定义好的？
  - 【R0】本文的数据集是什么？是自己采集的还是开源的？
  - 【R0, R1】本文的 benchmark 和 metric 是什么？这个 benchmark 和数据集相关还是不相关？
  - 【R0】本文的模型是怎么设计的？本文模型的参数量有多大？
  - 【R0】模型具体功能是什么，输入输出具体是什么形式，什么模态？
  - 【R0】本文的计算资源是什么？训练量有多大？
  - 【R0】本文提出的方法的优势是什么？有什么缺点？
  - 【R0, R1】本文总结的之前工作的问题主要是什么，本文有什么理论、方法论层面的关键发现

- 对于数值型信息需要尤其严格：
  - 如果论文没有明确报告参数量、训练资源、训练时长、数据规模、metric 数值，则不应该由 Agent 猜测。
  - 如果数值来自不同论文或不同 benchmark，需要明确说明不可直接比较的原因。
  - 如果 R1 搜到的 follow-up work 使用了不同数据集、不同设置或不同 evaluation protocol，需要标注 comparison risk。

- 对于关键内容提取，可以把最终输出组织成面向单篇论文的 Reading Report，强调忠实、可追溯、结构化。

###### 领域内容联想

- 【R1】能够根据本文所处的领域/任务联想到本领域/任务的若干关键论文和发展脉络。这部分主要帮助研究者获取对技术演变的视野。
  - 有哪些milestone papers？ 
    - 如何识别 milestoken papers？
      - 查找该领域被引用次数最多的论文并按日期对它们进行排序。
      - 寻求经验丰富的研究人员的建议。（Human-in-the-loop）
      - 也不能只按引用数判断 milestone papers，因为新论文引用数天然较低，老论文引用数天然较高。
      - 可以综合 citation count、citation velocity、venue quality、method adoption、dataset / benchmark influence、conceptual influence 和 expert confirmation。
  - 领域技术如何随着时间的推移而演变?
    - 如何查找两个技术里程碑之间的论文
      - 向前追溯：里程碑论文引用的论文、基础工作
      - 向后追溯：引用里程碑论文的论文、衍生工作
      - 可以从 Google Scholar 的 cited by / related articles、Semantic Scholar 的 references / citations、Connected Papers 的图谱关系中寻找中间论文。
      - 也可以围绕 dataset、benchmark、baseline、method keyword 在 Papers with Code、arXiv、OpenReview 中搜索代表性工作。
  - 如何梳理技术发展脉络？
    - 首先，初始化一个时间轴，将论文列到时间轴、并阅读每篇论文：了解它解决的问题、pipeline和技术见解。
    - 然后，确认哪些论文是milestone paper、哪些论文是follow-up：根据论文方法的创新性判断
    - 最后，总结这些论文：Milestone paper的技术范式、 Follow-up papers作出的改进
    - 可以进一步把领域脉络拆成 problem evolution、method evolution 和 evaluation evolution：分别观察问题定义、方法范式、数据集/benchmark/metric 如何变化。
    - 对每篇关键论文，可以记录 paper、problem、key idea、pipeline、evidence、limitation、influence、relation 等字段。

- 【R1】论文搜索可以分成几个阶段，而不是一次性搜索：
  - Seed paper extraction：从当前论文中抽取任务名、方法关键词、数据集、benchmark、baseline、related work。
  - Backward citation search：查看当前论文引用了哪些基础论文，用于寻找 foundational papers。
  - Forward citation search：查看哪些后续论文引用了当前论文，用于寻找 follow-up papers 和最新进展。
  - Benchmark search：围绕 dataset、benchmark、leaderboard 搜索代表性方法。
  - Survey search：搜索 survey、tutorial、awesome list、course note，快速获得领域地图。
  - Recent trend search：限制最近 1-2 年，搜索最新 arXiv、conference、OpenReview 论文。

- 【R1】推荐优先使用这些搜索入口：
  - Google Scholar：适合查 cited by、related articles、引用链和高引用论文。
  - Semantic Scholar：适合看 citation count、influential citations、TLDR、领域分类和相关论文。
  - Connected Papers：适合从一篇 seed paper 出发，快速观察论文图谱和相邻工作。
  - Papers with Code：适合查 task、dataset、benchmark、SOTA、leaderboard 和开源实现。
  - arXiv：适合查最新预印本，尤其是 AI、ML、CV、NLP、Robotics 等方向。
  - OpenReview：适合查 ICLR、NeurIPS、部分 ICML workshop 等论文的评审意见和作者回复。
  - DBLP：适合查作者、会议论文列表和正式发表记录。
  - ACL Anthology：适合 NLP 方向论文。
  - CVF Open Access：适合 CVPR、ICCV、ECCV 方向论文。
  - PMLR：适合 ICML、AISTATS、COLT、UAI 等机器学习会议论文。

- 【R1】能够根据本文所处的领域/任务联想到本领域/任务的重要问题。这部分主要帮助研究者获取对重要问题的视野。
  -  这个领域的终极目标是什么？
  - 该领域已经达到了什么水平？
  - 还有哪些重要的问题仍未被解决？
  - 现阶段的热点话题是什么？
  - 可以结合 survey、tutorial、benchmark paper、OpenReview 讨论和近期高引用 follow-up work 来判断这些问题。
  - 可以把最终输出组织成面向一个任务或领域的 Field Map，强调发展脉络、关键论文、benchmark、未解决问题和研究机会。
- 【R2】获取领域的视野为课题选择、方法设计、实验迭代、故事梳理、论文写作打下基础
- 【R2】能够获取和讲解该领域/任务的最新文章，整理技术的演变轨迹。

###### 推荐搜索 query 模板

- `"<task name>" survey benchmark dataset`
- `"<method keyword>" "<task name>" arxiv`
- `"<dataset name>" leaderboard papers with code`
- `"<benchmark name>" state of the art`
- `"<paper title>" cited by`
- `"<field name>" survey 2024 OR 2025`
- `"<method family>" limitations future work`
- `"<task name>" openreview`

###### Agent 工作流建议

- 可以把论文阅读辅助器拆成多个 Agent 或多个模块：
  - Paper Parser Agent：只负责 R0 信息抽取，严格基于原文。
  - Evidence Verifier Agent：检查每个 claim 是否有证据位置，是否出现过度推断。
  - Citation Explorer Agent：基于 references 和 cited-by 进行 R1 扩展搜索。
  - Benchmark Agent：围绕 task、dataset、metric、leaderboard 查找可比较工作。
  - Timeline Agent：整理 milestone papers、follow-up papers 和技术演化路线。
  - Research Insight Agent：在明确标注 R2 的前提下，总结趋势、开放问题和选题机会。
