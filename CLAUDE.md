# CLAUDE.md — Codebase Onboarding Agent

## What This Is
LangGraph-powered system that analyzes GitHub repos and produces:
1. Interactive onboarding docs (7-section report)
2. AI context files (CLAUDE.md, copilot-instructions.md, .clinerules, .aider.conf.yml)
3. AI-readiness score (6 dimensions, radar chart, action plan)

## Tech Stack
- **Pipeline**: LangGraph (Python) — 8-node graph with cycles, conditional edges, fan-out/fan-in
- **Backend**: FastAPI — REST + WebSocket streaming
- **Frontend**: React — interactive report viewer, D3.js/react-flow for graphs
- **LLM**: Gemini API (current). Code MUST be model-agnostic — use LiteLLM or custom wrapper
- **DB**: SQLite — cache keyed by `repo_url + commit_hash + depth`
- **AST**: tree-sitter for multi-language parsing
- **Observability**: LangSmith tracing

## Architecture (8 Nodes)
```
N1:StructureScanner(no LLM) → N2:DependencyAnalyzer(1 call) → N3:ModuleDeepDiver(1/file, CYCLIC)
→ N4:PatternDetector(1-2 calls) → N5:AIReadinessScorer(1 call+metrics)
→ N6:OutputRouter → [7a:DocGen | 7b:AgentFileGen | 7c:ReadinessReport] → N8:FinalAssembler
```

## Key Constraints
- **Language support**: Python + JS/TS initially. Java and others later.
- **File analysis cap**: 50-75 files max. Quick=15, Standard=30, Deep=50-75.
- **Private repos**: Supported via user-provided GitHub token.
- **Rate limiting**: Built into LLM wrapper — exponential backoff, token budget tracking.
- **State**: Append-only `CodebaseState` (Pydantic). Nodes never overwrite prior sections.
- **Context management**: 5-step progressive compression. Summaries replace raw content after analysis (150 tokens/file vs 2000).

## Safety & Code Guidelines
- Never expose API keys in code — all secrets via env vars.
- Never commit .env files. Use .env.example with placeholder values.
- Validate all user input (GitHub URLs, config options) at the API boundary.
- Sanitize repo paths to prevent path traversal attacks.
- Rate-limit the analyze endpoint to prevent abuse.
- Clone repos into isolated temp directories; clean up after analysis.
- No arbitrary code execution from analyzed repos — static analysis only (AST, regex, file reading).
- All LLM calls go through the wrapper — never call provider APIs directly.

## Tooling & Config

| Category | Tool | Config Location |
|---|---|---|
| Package management | uv | pyproject.toml + uv.lock |
| Project config | — | pyproject.toml (single source of truth) |
| Python version | uv python pin | .python-version |
| Virtual env | uv (implicit) | .venv/ (gitignored) |
| Linting | Ruff | [tool.ruff] in pyproject.toml |
| Formatting | Ruff format | [tool.ruff.format] in pyproject.toml |
| Type checking | mypy + Pydantic plugin | [tool.mypy] in pyproject.toml |
| Testing | pytest + asyncio + cov + mock | [tool.pytest] in pyproject.toml |
| Pre-commit hooks | pre-commit | .pre-commit-config.yaml |
| Task runner | Makefile | Makefile at root |
| Env var management | pydantic-settings | .env + Settings class |
| Logging | structlog | Configured in code |
| Pipeline observability | LangSmith | Env vars for API key |
| API docs | FastAPI auto-generated | Free from FastAPI |

### Rules
- All tool config lives in `pyproject.toml` — no separate setup.cfg, tox.ini, .flake8, etc.
- Use `uv` for all dependency operations — never pip directly.
- Ruff handles both linting AND formatting — no black, isort, or flake8.
- mypy must run with Pydantic plugin enabled for state schema validation.
- Pre-commit hooks must run ruff + ruff format + mypy before each commit.
- Makefile targets: `make lint`, `make format`, `make typecheck`, `make test`, `make all`.
- pydantic-settings `Settings` class is the single entry point for all env vars — never use `os.getenv()` directly.
- structlog for all logging — no print statements, no stdlib logging.

## Project Structure
```
src/onboarding_agent/
├── __init__.py
├── cli.py                          # CLI entry point
├── config/settings.py              # pydantic-settings (single env var entry point)
├── models/
│   ├── state.py                    # CodebaseState — central LangGraph state
│   └── types.py                    # All Pydantic domain models
├── services/
│   ├── llm.py                      # LiteLLM wrapper (model-agnostic, rate-limited)
│   ├── github.py                   # Repo cloning + URL validation
│   └── cache.py                    # SQLite analysis cache
├── parsers/
│   ├── base.py                     # Abstract parser (imports, functions, env vars, typing)
│   ├── python_parser.py            # Python AST-based parser
│   └── typescript_parser.py        # JS/TS regex parser (tree-sitter later)
├── pipeline/
│   ├── graph.py                    # LangGraph graph definition
│   └── nodes/                      # One file per node (N1-N8)
│       ├── structure_scanner.py
│       ├── dependency_analyzer.py
│       ├── module_deep_diver.py
│       ├── pattern_detector.py
│       ├── ai_readiness_scorer.py
│       ├── output_router.py
│       ├── doc_generator.py        # 7a
│       ├── agent_file_generator.py # 7b
│       ├── readiness_report.py     # 7c
│       └── final_assembler.py      # 8
├── api/
│   ├── app.py                      # FastAPI app with lifespan
│   └── routes/
│       ├── health.py
│       └── analyze.py
└── utils/logging.py                # structlog setup

tests/
├── conftest.py                     # Shared fixtures
├── unit/                           # No external deps needed
│   ├── test_models.py
│   ├── test_parsers.py
│   └── test_services.py
├── integration/                    # May need services
│   └── test_pipeline.py
└── fixtures/sample_repos/          # Python + TS sample apps for parser tests
```

## Commands
```bash
uv sync                  # install deps
uv sync --all-extras     # install deps + dev tools
make lint                # ruff check
make format              # ruff format
make typecheck           # mypy src/
make test                # pytest with coverage
make test-fast           # pytest without coverage
make all                 # lint + format-check + typecheck + test
make serve               # uvicorn dev server on :8000
make dev                 # install + pre-commit hooks
```

## Patterns
- "How to add..." guides: raw data extracted in N4, formatted in N7a.
- Agent files: common knowledge extractor → per-tool formatter (adapter pattern).
- Uncertain fields in generated files marked with `# VERIFY: [reason]`.
- Import graph is the critical shared data structure — everything downstream depends on it.
- Summary compression quality is make-or-break — test early against known repos.
- All node functions are async, accept `CodebaseState`, return `dict[str, object]`.
- Parsers inherit from `BaseParser` — add new languages by subclassing.
- Settings accessed via `get_settings()` (cached singleton) — never construct directly.

## Build Order
Sprint 1: Pipeline core (N1, N2, state schema, static preprocessing, CLI)
Sprint 2: Deep-diver cycle (N3, compression, priority ranking)
Sprint 3: Pattern detection + scoring (N4, N5)
Sprint 4: Output generation (N7a/b/c, N8, fan-out/fan-in)
Sprint 5: Frontend + integration (React, WebSocket, D3.js)
Sprint 6: Polish, evaluation, deployment
