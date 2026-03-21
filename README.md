# Codebase Onboarding Agent

An intelligent, LangGraph-powered pipeline that analyzes any GitHub repository and generates comprehensive onboarding documentation, AI-assistant context files, and an AI-readiness score — so new developers can ramp up in hours, not weeks.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.4-orange.svg)](https://github.com/langchain-ai/langgraph)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev)

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [What It Does](#what-it-does)
- [Architecture](#architecture)
  - [Pipeline Overview](#pipeline-overview)
  - [The 10-Node LangGraph Pipeline](#the-10-node-langgraph-pipeline)
  - [State Management](#state-management)
  - [System Communication Flow](#system-communication-flow)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables)
  - [Running the Application](#running-the-application)
- [Usage](#usage)
  - [CLI](#cli)
  - [Web Interface](#web-interface)
  - [API Endpoints](#api-endpoints)
- [Output](#output)
- [Development](#development)
  - [Code Quality](#code-quality)
  - [Testing](#testing)
  - [Makefile Commands](#makefile-commands)
- [Design Decisions](#design-decisions)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Problem Statement

Joining a new codebase is one of the most time-consuming parts of software development. Developers spend days reading scattered documentation, tracing code paths, and asking colleagues for tribal knowledge. AI coding assistants (Claude, Copilot, Cline, Aider) need manually curated context files to be effective on a new repo.

**Codebase Onboarding Agent automates all of this.** Point it at a GitHub repo and it produces everything a new developer — or an AI assistant — needs to be productive from day one.

## What It Does

Given a GitHub repository URL, the agent:

1. **Clones and scans** the repository structure, entry points, and configuration
2. **Analyzes dependencies** — builds an import graph, extracts the tech stack, identifies env vars and external APIs
3. **Deep-dives into modules** — extracts interfaces, patterns, and relationships file-by-file using AST parsing and LLM analysis
4. **Detects patterns** — identifies coding conventions, inconsistencies, dead code, and complexity hotspots
5. **Scores AI-readiness** — evaluates the codebase across 6 dimensions (type safety, consistency, modularity, discoverability, test coverage, dependency hygiene)
6. **Generates three outputs:**
   - A **12-section onboarding report** (markdown) covering everything from quick start to suggested first tasks
   - **AI context files** — `CLAUDE.md`, `copilot-instructions.md`, `.clinerules`, `.aider.conf.yml` — ready to drop into the repo
   - An **AI-readiness report** with radar chart data, a verdict, and a prioritized action plan

---

## Architecture

### Pipeline Overview

The system is built around a **stateful, multi-node LangGraph pipeline** with cyclic processing, conditional routing, and fan-out/fan-in output generation. A FastAPI backend exposes the pipeline over REST and WebSocket, and a React frontend provides an interactive report viewer with live progress streaming.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React)                               │
│   SubmitPage  ──►  ProgressPage (WebSocket)  ──►  ResultsPage          │
│                                                   ├─ ReportTab          │
│                                                   ├─ DashboardTab       │
│                                                   ├─ AgentFilesTab      │
│                                                   └─ QATab              │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ REST + WebSocket
┌──────────────────────────────▼──────────────────────────────────────────┐
│                        BACKEND (FastAPI)                                │
│   /api/analyze (POST)  ──►  Job Queue  ──►  LangGraph Pipeline         │
│   /api/progress/{id} (WS)   In-Memory       astream_events            │
│   /api/qa (POST)            Job Manager      Pipeline → state          │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
        ┌──────────────────────┼───────────────────────┐
        ▼                      ▼                       ▼
   GitHub API            Gemini API              SQLite Cache
   (clone repos)         (via LiteLLM)           (result caching)
```

### The 10-Node LangGraph Pipeline

```
N1: Structure Scanner ─► N2: Dependency Analyzer ─► N3: Module Deep-Diver ─┐
         (no LLM)              (1 LLM call)           (1 call/file)        │
                                                                     ┌─────┘
                                                                     │ loops while
                                                                     │ pending modules
                                                                     └─────┐
                                                                           ▼
N5: AI-Readiness Scorer ◄─ N4: Pattern Detector ◄─────────────────── (exit cycle)
      (1 LLM call)              (1-2 LLM calls)
         │
         ▼
N6: Output Router ──┬──► N7a: Doc Generator ──────────┐
     (no LLM)       │         (2 LLM calls)           │
                    │                                  │
                    ├──► N7b: Agent File Generator ────┤  sequential
                    │         (multiple LLM calls)     │  fan-out
                    │                                  │
                    └──► N7c: Readiness Report ────────┘
                              (structured output)      │
                                                       ▼
                                              N8: Final Assembler
                                                   (no LLM)
                                                      │
                                                      ▼
                                                    END
```

| Node | Purpose | LLM Calls | Key Output |
|------|---------|-----------|------------|
| **N1: Structure Scanner** | Clones repo, walks filesystem, finds entry points & config files | 0 | `MetadataState` |
| **N2: Dependency Analyzer** | Parses manifests, builds import graph, extracts env vars | 1 | `DependencyState`, `TechProfile` |
| **N3: Module Deep-Diver** | Analyzes each source file — interfaces, dependencies, patterns. **Cycles** while modules remain in the pending queue | 1 per file | `ModuleState` |
| **N4: Pattern Detector** | Identifies conventions, inconsistencies, dead code, complexity hotspots | 1-2 | `PatternState` |
| **N5: AI-Readiness Scorer** | Scores across 6 weighted dimensions (0-10 scale) | 1 + metrics | `ScoreState` |
| **N6: Output Router** | Routes to fan-out generators | 0 | Control flow |
| **N7a: Doc Generator** | Produces a 12-section markdown onboarding report | 2 | `report_markdown` |
| **N7b: Agent File Generator** | Generates `CLAUDE.md`, `copilot-instructions.md`, `.clinerules`, `.aider.conf.yml` | Multiple | `agent_files` |
| **N7c: Readiness Report** | Creates radar chart data, verdict, and prioritized action plan | Structured | `readiness_report` |
| **N8: Final Assembler** | Validates completeness, caches result in SQLite | 0 | Final state |

### State Management

The pipeline uses a central `CodebaseState` (Pydantic model) with an **append-only design** — nodes never overwrite data written by previous nodes. Key sections:

- **MetadataState** — repo URL, commit hash, directory tree, entry points
- **DependencyState** — tech stack, packages, import graph, env vars, external APIs
- **ModuleState** — analyzed modules, pending queue, module connections, API endpoints
- **PatternState** — conventions, inconsistencies, dead code, complexity hotspots
- **ScoreState** — dimension scores, overall score, recommendations
- **OutputState** — report markdown, agent files, readiness report (field-level merging across generators)

### System Communication Flow

```
Frontend ──REST──► FastAPI ──triggers──► LangGraph Pipeline
Frontend ◄──WS─── FastAPI ◄──astream──  LangGraph Pipeline
                                            │
                              ┌──────────────┼──────────────┐
                              ▼              ▼              ▼
                         GitHub API     Gemini API     LangSmith
                         (clone)       (via LiteLLM)   (tracing)
```

- **REST** for analysis submission and result retrieval
- **WebSocket** for real-time, node-by-node progress streaming
- **SQLite** for caching results keyed by `(repo_url, commit_hash, depth)`

---

## Tech Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.12+ | Runtime |
| **LangGraph** | 0.4.1+ | Pipeline orchestration — stateful graph with cycles, conditional edges, fan-out |
| **FastAPI** | 0.115+ | Async REST API + WebSocket server |
| **Pydantic** | 2.11+ | State schema, validation, settings management |
| **LiteLLM** | 1.60+ | Model-agnostic LLM wrapper (currently Gemini, swappable to any provider) |
| **langchain-google-genai** | 2.1+ | Gemini API integration |
| **tree-sitter** | 0.24+ | Multi-language AST parsing (Python, JavaScript, TypeScript) |
| **GitPython** | 3.1+ | Repository cloning and Git operations |
| **aiosqlite** | 0.21+ | Async SQLite for analysis caching |
| **httpx** | 0.28+ | Async HTTP client |
| **uvicorn** | 0.34+ | ASGI server |
| **structlog** | 25.1+ | Structured JSON logging |
| **LangSmith** | 0.3+ | Pipeline observability and tracing (optional) |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 19 | UI framework |
| **TypeScript** | 5.9 | Type-safe frontend development |
| **Vite** | 5.4 | Build tool and dev server |
| **React Router** | 7.13 | Client-side routing |
| **Recharts** | 3.8 | AI-readiness radar chart visualization |
| **react-syntax-highlighter** | 16.1 | Code block rendering in reports |

### Dev Tooling

| Tool | Purpose |
|------|---------|
| **uv** | Python package management (replaces pip/pipenv) |
| **Ruff** | Linting + formatting (replaces black, flake8, isort) |
| **mypy** | Static type checking with Pydantic plugin (strict mode) |
| **pytest** | Testing framework with async, coverage, and mock support |
| **pre-commit** | Git hooks for automated quality checks |
| **ESLint** | Frontend linting |

---

## Project Structure

```
codebase-onboarding-agent/
├── src/onboarding_agent/
│   ├── cli.py                          # CLI entry point
│   ├── config/
│   │   └── settings.py                 # Pydantic Settings — single env var entry point
│   ├── models/
│   │   ├── state.py                    # CodebaseState — central LangGraph state schema
│   │   └── types.py                    # Pydantic domain models
│   ├── services/
│   │   ├── llm.py                      # LiteLLM wrapper (model-agnostic, rate-limited)
│   │   ├── github.py                   # Repo cloning + URL validation
│   │   └── cache.py                    # SQLite analysis cache
│   ├── parsers/
│   │   ├── base.py                     # Abstract parser interface
│   │   ├── python_parser.py            # Python AST parser
│   │   └── typescript_parser.py        # JS/TS parser
│   ├── pipeline/
│   │   ├── graph.py                    # LangGraph graph definition
│   │   └── nodes/                      # One file per pipeline node
│   │       ├── structure_scanner.py    # N1
│   │       ├── dependency_analyzer.py  # N2
│   │       ├── module_deep_diver.py    # N3 (cyclic)
│   │       ├── pattern_detector.py     # N4
│   │       ├── ai_readiness_scorer.py  # N5
│   │       ├── output_router.py        # N6
│   │       ├── doc_generator.py        # N7a
│   │       ├── agent_file_generator.py # N7b
│   │       ├── readiness_report.py     # N7c
│   │       └── final_assembler.py      # N8
│   ├── api/
│   │   ├── app.py                      # FastAPI app with CORS, lifespan, middleware
│   │   ├── job_manager.py              # In-memory job queue with WebSocket subscriptions
│   │   └── routes/
│   │       ├── health.py               # Health check endpoint
│   │       ├── analyze.py              # Analysis submission + job status
│   │       └── qa.py                   # Follow-up Q&A endpoint
│   └── utils/
│       └── logging.py                  # structlog configuration
│
├── frontend/                           # React + TypeScript frontend
│   └── src/
│       ├── pages/                      # SubmitPage, ProgressPage, ResultsPage
│       ├── components/                 # ReportTab, DashboardTab, AgentFilesTab, QATab
│       ├── api/client.ts               # Backend HTTP + WebSocket client
│       └── types/                      # TypeScript type definitions
│
├── tests/
│   ├── conftest.py                     # Shared pytest fixtures
│   ├── unit/                           # Unit tests (no external deps)
│   ├── integration/                    # Integration tests (pipeline)
│   └── fixtures/sample_repos/          # Sample repos for parser tests
│
├── pyproject.toml                      # Single source of truth for all config
├── Makefile                            # Task runner
├── .env.example                        # Environment variable template
├── .pre-commit-config.yaml             # Git hooks (ruff, mypy, etc.)
└── .python-version                     # Python 3.12
```

---

## Getting Started

### Prerequisites

- **Python 3.12+**
- **Node.js 18+** (for the frontend)
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **A Gemini API key** — get one at [Google AI Studio](https://aistudio.google.com/apikey)
- **Git** — for repository cloning

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/codebase-onboarding-agent.git
cd codebase-onboarding-agent

# Install Python dependencies
make dev    # installs all deps + dev tools + pre-commit hooks

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### Environment Variables

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Gemini API key for LLM analysis |
| `GITHUB_TOKEN` | No | — | GitHub personal access token (required for private repos) |
| `LANGSMITH_API_KEY` | No | — | LangSmith API key for pipeline tracing |
| `LANGSMITH_PROJECT` | No | `codebase-onboarding-agent` | LangSmith project name |
| `LANGSMITH_TRACING` | No | `false` | Enable/disable LangSmith tracing |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `ANALYSIS_MAX_FILES` | No | `75` | Maximum files to analyze |
| `CLONE_DIR` | No | `/tmp/onboarding-agent-repos` | Temp directory for cloned repos |

### Running the Application

**Option 1: API Server + Frontend (full web experience)**

```bash
# Terminal 1 — Backend
make serve
# Runs on http://localhost:8000
# API docs at http://localhost:8000/docs

# Terminal 2 — Frontend
cd frontend && npm run dev
# Runs on http://localhost:5173
```

**Option 2: CLI (quick one-off analysis)**

```bash
onboarding-agent https://github.com/user/repo --depth standard --output-dir ./output
```

---

## Usage

### CLI

```bash
# Basic usage
onboarding-agent <repo_url>

# With options
onboarding-agent https://github.com/user/repo \
  --depth standard \              # quick (15 files) | standard (30) | deep (75)
  --output-dir ./results \        # where to write output files
  --agents claude copilot cline aider   # which AI context files to generate
```

**Analysis Depths:**

| Depth | Max Files | Best For |
|-------|-----------|----------|
| `quick` | 15 | Fast overview, small repos |
| `standard` | 30 | Most repos (default) |
| `deep` | 75 | Large repos, thorough analysis |

### Web Interface

1. **Submit** — Enter a GitHub repo URL, choose analysis depth and agent files
2. **Progress** — Watch the pipeline execute node-by-node with live WebSocket updates
3. **Results** — Browse the interactive report with four tabs:
   - **Report** — Full 12-section onboarding guide with syntax-highlighted code
   - **Dashboard** — AI-readiness radar chart, overall score, and action items
   - **Agent Files** — Preview and download generated context files
   - **Q&A** — Ask follow-up questions about the analyzed codebase

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/analyze` | Submit a repo for analysis (returns `job_id`) |
| `GET` | `/api/job/{job_id}` | Poll job status and results |
| `WebSocket` | `/api/progress/{job_id}` | Stream real-time progress updates |
| `POST` | `/api/qa` | Ask follow-up questions about an analysis |

Auto-generated API documentation is available at `/docs` (Swagger) and `/redoc`.

---

## Output

The pipeline produces three artifacts:

### 1. Onboarding Report (`onboarding_report.md`)

A 12-section markdown document:

1. Project Identity Card — name, language, framework, key libraries
2. Quick Start — time to running, commands
3. Directory Structure — tree with purpose annotations
4. Configuration & Secrets — env vars, config files, examples
5. Architecture Overview — module dependency graph, entry points
6. Feature Flow Maps — critical user journeys traced through code
7. External Services / APIs — consumed services, auth, rate limits
8. Testing — framework, commands, coverage info
9. Development Workflow — CI/CD, linting, formatting, commit hooks
10. Patterns & Conventions — naming, error handling, data access patterns
11. Known Issues & Gotchas — pitfalls, debugging tips
12. Suggested First Tasks — orientation paths for new developers

### 2. AI Context Files

Ready-to-use configuration files for AI coding assistants:

| File | AI Tool |
|------|---------|
| `CLAUDE.md` | Claude Code |
| `copilot-instructions.md` | GitHub Copilot |
| `.clinerules` | Cline |
| `.aider.conf.yml` | Aider |

### 3. AI-Readiness Report

A quantitative assessment across 6 weighted dimensions:

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| Type Safety | 25% | Type annotations, strict configs |
| Consistency | 25% | Naming conventions, code patterns |
| Discoverability | 15% | Documentation, file organization |
| Modularity | 15% | Separation of concerns, coupling |
| Test Coverage | 10% | Test presence, framework setup |
| Dependency Hygiene | 10% | Pinned versions, minimal unused deps |

Includes a radar chart visualization, an overall verdict, and a prioritized action plan.

---

## Development

### Code Quality

All tooling is configured in `pyproject.toml` — no separate config files:

```bash
make lint          # Ruff linting
make format        # Ruff formatting
make typecheck     # mypy with Pydantic plugin (strict mode)
make check         # lint + format-check + typecheck
```

Pre-commit hooks run automatically on every commit:
- Ruff check (with auto-fix) + format
- mypy type checking
- Trailing whitespace, YAML/TOML validation, merge conflict detection

### Testing

```bash
make test              # Full test suite with coverage
make test-unit         # Unit tests only (-m unit)
make test-integration  # Integration tests only (-m integration)
make test-fast         # Quick run without coverage
```

Tests use `pytest-asyncio` (auto mode), `pytest-mock`, and `pytest-cov` with branch coverage. Sample repos in `tests/fixtures/` provide deterministic parser test inputs.

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | Install production dependencies |
| `make dev` | Install all deps + dev tools + pre-commit hooks |
| `make lint` | Run Ruff linter |
| `make lint-fix` | Run Ruff linter with auto-fix |
| `make format` | Format code with Ruff |
| `make typecheck` | Run mypy (strict mode) |
| `make test` | Run pytest with coverage |
| `make test-fast` | Run pytest without coverage |
| `make all` | lint + format-check + typecheck + test |
| `make serve` | Start FastAPI dev server (port 8000) |
| `make clean` | Remove build artifacts and caches |

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **LangGraph over raw LangChain** | Needed cyclic processing (module deep-diver loop), conditional edges, and stateful fan-out — LangGraph's graph primitives model this naturally |
| **Append-only state** | Nodes write to their own sections of `CodebaseState` and never overwrite previous data, preventing data loss across iterations |
| **LiteLLM as LLM wrapper** | Keeps the system model-agnostic — swap Gemini for GPT-4, Claude, or any provider without changing pipeline code |
| **tree-sitter for parsing** | Language-agnostic AST parsing that scales to new languages via grammar packages, avoiding fragile regex-based approaches |
| **Pydantic everywhere** | Type-safe state schema, validated LLM outputs, settings management — one modeling library for the entire stack |
| **SQLite caching** | Zero-infrastructure caching keyed by `(repo_url, commit_hash, depth)` — avoids redundant analysis of unchanged repos |
| **WebSocket progress streaming** | Users see node-by-node pipeline progress in real time instead of waiting for a spinner |
| **Single `pyproject.toml`** | All tool configuration (Ruff, mypy, pytest, coverage) in one file — no config sprawl |

---

## Roadmap

- [ ] Additional language support (Java, Go, Rust) via new tree-sitter grammars
- [ ] Docker containerization for one-command deployment
- [ ] Parallel fan-out execution for output generators (N7a/b/c)
- [ ] Incremental re-analysis (only analyze changed files)
- [ ] GitHub App integration for automatic analysis on PR events
- [ ] Export reports to PDF / Notion

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Set up the dev environment (`make dev`)
4. Make your changes and ensure all checks pass (`make all`)
5. Commit with a descriptive message
6. Open a pull request

Please ensure your code passes all linting, formatting, type checking, and tests before submitting.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

Built by [abixdev](https://github.com/abixdev) with LangGraph, FastAPI, and React.
