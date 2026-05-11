# Paperflow V1

Paperflow V1 is a local-first paper reading IDE for AI researchers and engineers.

It implements the first PRD loop:

```text
Import PDF
→ create a paper session
→ generate an evidence-aware R0 Reading Report
→ add lightweight R1 related-work context
→ open a Report-first workspace
→ ask focused questions
→ save an Obsidian-native Markdown note
```

## Backend

```bash
cd paperflow/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

# Optional: enable DeepSeek API through env
export DEEPSEEK_API_KEY="your-key"
export DEEPSEEK_MODEL="deepseek-v4-flash"

uvicorn app.main:app --reload
```

Paperflow also reads the DeepSeek-TUI config at `~/.deepseek/config.toml` or the path in `DEEPSEEK_CONFIG_PATH`, so keys saved by `deepseek auth set --provider deepseek` are reused automatically.

Without a DeepSeek key, the backend uses a clearly marked development fallback. That fallback is only for local UI testing; real R0/R1 extraction is performed by the DeepSeek-backed paper agent.

Run tests:

```bash
cd paperflow/backend
. .venv/bin/activate
pytest -q
```

## Frontend

```bash
cd paperflow/frontend
npm install
npm run dev
```

Run tests:

```bash
cd paperflow/frontend
npm test
```

## V1 Status

Implemented:

- Library-first home.
- PDF import endpoint.
- Paper session creation.
- SQLite-backed local paper library.
- R0/R1 report schema.
- Evidence-aware report cards.
- R0/R1/R2 reliability badges.
- Report-first workspace.
- Focused question endpoint.
- Obsidian-native Markdown note generation.
- DeepSeek-backed paper agent integration with local development fallback.

Not yet implemented:

- Full PDF page rendering and exact coordinate-level jump.
- Robust section/table/reference parsing with GROBID.
- Real cited-by search from Semantic Scholar/OpenAlex.
- Persistent report reload after backend restart.
- Field map / citation graph.
