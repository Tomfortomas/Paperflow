# Paperflow V3 PRD：Agent 对话区

更新时间：2026-05-12

## 1. 背景

Paperflow V2 已经具备 Library、Reading Report、PDF Viewer、Evidence Detail、R1 Search、Field Map、R2 Insight 和 Obsidian 导出能力，但 Workspace 右侧仍然只是一个很小的“聚焦追问”输入框。它能返回一个 claim，但不像真正的 Agent 工作区：没有 transcript、没有过程卡片、没有运行状态，也不能让用户理解 Agent 是如何读报告、定位证据和生成回答的。

DeepSeek-TUI 可借鉴的核心不是“输入框”，而是由 transcript、composer、running/status card 和 process/tool cards 组成的交互结构。Paperflow V3 需要把这一思想移植到论文研读场景：用户一边看 PDF / Report，一边和 Agent 对话，并持续看到回答的证据来源与处理过程。

## 2. 目标

- 在 Workspace 右侧新增正式的 Agent 对话区，替换当前过轻的“聚焦追问”区域。
- 保留 Evidence Detail，并在其下方提供 transcript + process cards + composer。
- 后端新增结构化 chat 接口，不再只返回一个裸 `Claim`。
- 回答继续遵守 R0/R1/R2 和 evidence 约束，不能退化为普通闲聊。
- 第一版不做 token streaming，但前端要展示“步骤状态流式感”：读取报告、定位证据、必要时检索相关工作、生成回答。

## 3. 非目标

- 第一版不实现 SSE / WebSocket 真流式 token 输出。
- 第一版不实现长期跨会话持久化 transcript。
- 第一版不引入多 Agent 调度框架。
- 第一版不替换 Reading Report 主体，也不改变 Field Map 生成逻辑。

## 4. 用户故事

- 作为研究者，我希望在读某个 claim 时，可以在右侧直接追问：“这个 benchmark 是否公平？”并看到 Agent 基于当前 report/evidence 回答。
- 作为研究者，我希望知道 Agent 回答前做了哪些步骤，例如读取报告、定位证据、检查 R1 相关工作。
- 作为研究者，我希望每轮对话都保留在 transcript 里，方便回看上下文。
- 作为研究者，我希望回答带可靠性标签和证据，而不是泛泛聊天。

## 5. 前端设计

### 5.1 Workspace 右侧 Rail

右侧 rail 分为三块：

1. Agent 状态：保留现有处理状态与 rerun Agent。
2. 证据详情：保留当前选中 claim 的证据、page、section、location glyph。
3. Agent 对话：新增正式对话区。

### 5.2 Agent 对话区结构

- Header：`Agent 对话` / `Agent Chat`。
- Status card：
  - `idle`：等待提问。
  - `running`：Agent 正在处理。
  - `completed`：回答已生成。
  - `failed`：回答失败。
- Transcript：
  - 用户消息：显示问题文本。
  - Agent 回复：显示 reliability badge、回答文本和 evidence summary。
- Process cards：
  - `读取报告`
  - `定位证据`
  - `检查 R1 上下文`
  - `生成回答`
  - 每个 step 有 `pending / running / completed / failed`。
- Composer：
  - 固定在对话区底部。
  - 输入框支持继续编辑下一轮问题。
  - 第一版请求处理中允许输入，但提交按钮可等待当前轮结束后再触发。

## 6. 后端接口

### 6.1 `POST /api/papers/{paper_id}/chat`

请求：

```json
{
  "question": "这个 benchmark 是否公平？",
  "selected_claim_id": "claim-1",
  "selected_evidence_id": "e1",
  "page": 1,
  "quote": "paper reading IDE"
}
```

响应：

```json
{
  "id": "chat-paper-1-...",
  "paper_id": "paper-1",
  "status": "completed",
  "steps": [
    {"id": "read-report", "label": "Read report", "status": "completed", "detail": "Loaded Reading Report"},
    {"id": "locate-evidence", "label": "Locate evidence", "status": "completed", "detail": "Used selected evidence"},
    {"id": "check-r1", "label": "Check R1 context", "status": "completed", "detail": "Checked related work"},
    {"id": "compose-answer", "label": "Compose answer", "status": "completed", "detail": "Generated evidence-aware answer"}
  ],
  "messages": [
    {"id": "user-...", "role": "user", "content": "这个 benchmark 是否公平？"},
    {"id": "assistant-...", "role": "assistant", "content": "...", "reliability": "R0", "evidence": [...]}
  ],
  "answer": {
    "id": "chat-answer",
    "text": "...",
    "reliability": "R0",
    "evidence": [...]
  }
}
```

### 6.2 第一版回答策略

- 如果请求带 selected evidence / quote，优先围绕该证据回答，可靠性为 R0。
- 如果问题命中某个 report section，例如 benchmark / dataset / method，则返回对应 section 的第一条 claim。
- 如果没有命中，则返回 summary 的第一条 claim。
- 如果 report 不存在，返回 404。
- 如果 question 为空，返回 400。

## 7. 数据模型

- `PaperChatRequest`
- `PaperChatStep`
- `PaperChatMessage`
- `PaperChatResponse`

所有 Agent 回复消息必须允许携带：

- `reliability`
- `evidence`
- `uncertainty`

## 8. 测试要求

后端：

- chat 接口返回 transcript、steps、answer 和 evidence。
- 空 question 返回 400。
- report 不存在返回 404。

前端：

- Workspace 右侧显示 `Agent 对话`。
- 用户提交问题后， transcript 显示用户消息和 Agent 回答。
- 显示 process cards。
- 调用 `client.chatPaper`，并传入当前 selected claim/evidence/page/quote。

## 9. 后续演进

- SSE / WebSocket 真流式输出。
- transcript 持久化到 SQLite。
- process cards 与真实工具调用绑定。
- 对话上下文进入 Agent prompt，而不是单轮问答。
- 支持中断、重试、继续追问、引用 Field Map / R1 cache / PDF selection。
