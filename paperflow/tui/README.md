# Paperflow TUI

A Textual-based terminal client for the PaperFlow backend. Same workflow as
the React/Vite frontend — Library-first home, Report-first workspace,
evidence detail panel, focused Q&A, Obsidian save — but entirely keyboard-driven
inside your terminal.

The TUI keeps the PaperAgent on the server. It is a thin HTTP client over the
FastAPI surface in `paperflow/backend`, mirroring the `app-server` ↔ `tui`
separation in [DeepSeek-TUI](https://github.com/Hmbown/DeepSeek-TUI).

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Paperflow TUI · Evidence-first paper reading · R0 · R1 · R2                 │
│ Agent: deepseek · deepseek-v4-flash    Backend: http://127.0.0.1:8000       │
├─────────────────────────────────────────────────────────────────────────────┤
│ ID        Title                                Status         Note          │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 41003db1  arxiv-2605.08063v1                   completed      ✓             │
│ e728f8ce  2605.06388v1                         processing     —             │
└─────────────────────────────────────────────────────────────────────────────┘
[i] Import PDF  [a] Import arXiv  [o] Open  [r] Rerun  [R] Refresh  [q] Quit
```

## Install

The TUI runs on the same Python the backend already uses. From the repo root:

```bash
# 1. Activate the backend's venv (or any Python 3.9+ venv with httpx available)
cd paperflow/backend
. .venv/bin/activate

# 2. Install the TUI in editable mode
pip install -e ../tui
```

Or as a standalone install:

```bash
python -m venv .venv-tui
. .venv-tui/bin/activate
pip install -e paperflow/tui
```

## Run

The TUI assumes the backend is reachable. Start the backend first:

```bash
cd paperflow/backend
. .venv/bin/activate
uvicorn app.main:app --reload
```

Then in another terminal:

```bash
paperflow-tui
# or
paperflow-tui --base-url http://127.0.0.1:8000
# or
PAPERFLOW_BASE_URL=http://my-host:8000 paperflow-tui
```

Equivalent to:

```bash
python -m paperflow_tui
```

## Keyboard

### Library

| Key | Action |
| --- | --- |
| `i` | Import a local PDF (modal accepts an absolute or `~`-relative path) |
| `a` | Import an arXiv URL or ID (modal accepts `https://arxiv.org/...`, `2605.08063`, or `arXiv:2605.08063v1`) |
| `o` / `Enter` | Open the selected paper's Workspace |
| `r` | Re-run the PaperAgent on the selected paper |
| `R` | Manually refresh the library and agent status |
| `q` | Quit |

The library auto-polls every 3 seconds so a paper that is still `processing`
will move to `completed` without you pressing anything.

### Workspace

| Key | Action |
| --- | --- |
| `j` / `k` / `↑` / `↓` | Navigate claims in the Reading Report tree |
| `Enter` / `Space` | Expand / collapse a section or open a claim's evidence in the right panel |
| `a` | Ask a focused question (modal). The answer is logged with its R0 / R1 / R2 badge |
| `s` | Save / update the Obsidian note for this paper |
| `r` | Re-run the PaperAgent on this paper |
| `R` | Refresh report + status |
| `b` / `Esc` | Back to Library |

### Reliability colors

| Badge | Meaning |
| --- | --- |
| `[R0]` (green) | Grounded in the current paper |
| `[R1]` (cyan)  | Grounded in another paper via external search |
| `[R2]` (yellow) | Inference, trend, or research opinion |

## Tests

```bash
pip install -e '.[dev]'
pytest -q
```

`respx` mocks the FastAPI surface so tests run without a live backend.

## Configuration

The TUI reads exactly one variable:

- `PAPERFLOW_BASE_URL` (default `http://127.0.0.1:8000`) — overridden by the
  `--base-url` flag.

Agent credentials (DeepSeek key, model, etc.) belong to the **backend**, not
the TUI. The TUI surfaces the configured agent in the header but never sends
the key over the wire.

## License

Same as the rest of PaperFlow: [PolyForm Noncommercial 1.0.0](../../LICENSE).
Research and noncommercial use only.
