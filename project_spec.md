# Codebase Onboarding Agent — Project Specification

## Table of Contents

- [Problem Statement](#problem-statement)
- [Project Overview](#project-overview)
- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [LangGraph Pipeline](#langgraph-pipeline)
  - [Node 1: Structure Scanner](#node-1-structure-scanner)
  - [Node 2: Dependency Analyzer](#node-2-dependency-analyzer)
  - [Node 3: Module Deep-Diver](#node-3-module-deep-diver)
  - [Node 4: Pattern Detector](#node-4-pattern-detector)
  - [Node 5: AI-Readiness Scorer](#node-5-ai-readiness-scorer)
  - [Node 6: Output Router](#node-6-output-router)
  - [Nodes 7a/7b/7c: Output Generators (Fan-Out)](#nodes-7a7b7c-output-generators-fan-out)
  - [Node 8: Final Assembler (Fan-In)](#node-8-final-assembler-fan-in)
- [State Schema](#state-schema)
- [Context Window Management](#context-window-management)
- [Output Specification](#output-specification)
  - [Section 1: Project Identity Card](#section-1-project-identity-card)
  - [Section 2: Environment & Setup Guide](#section-2-environment--setup-guide)
  - [Section 3: API & Endpoint Map](#section-3-api--endpoint-map)
  - [Section 4: Module Dependency Graph](#section-4-module-dependency-graph)
  - [Section 5: Feature Flow Maps](#section-5-feature-flow-maps)
  - [Section 6: Pattern & Convention Guide](#section-6-pattern--convention-guide)
  - [Section 7: Suggested First Tasks & Orientation Paths](#section-7-suggested-first-tasks--orientation-paths)
- [AI-Readiness Scoring System](#ai-readiness-scoring-system)
  - [Dimension 1: Discoverability](#dimension-1-discoverability)
  - [Dimension 2: Type Safety & Annotations](#dimension-2-type-safety--annotations)
  - [Dimension 3: Consistency & Conventions](#dimension-3-consistency--conventions)
  - [Dimension 4: Modularity & Boundaries](#dimension-4-modularity--boundaries)
  - [Dimension 5: Test Coverage & Verifiability](#dimension-5-test-coverage--verifiability)
  - [Dimension 6: Dependency Hygiene](#dimension-6-dependency-hygiene)
  - [Scoring Output Format](#scoring-output-format)
- [Agent File Generation](#agent-file-generation)
  - [CLAUDE.md (Claude Code)](#claudemd-claude-code)
  - [copilot-instructions.md (GitHub Copilot)](#copilot-instructionsmd-github-copilot)
  - [.clinerules (Cline)](#clinerules-cline)
  - [.aider.conf.yml (Aider)](#aiderconfyml-aider)
  - [Generation Architecture](#generation-architecture)
- [Frontend Specification](#frontend-specification)
  - [Screen 1: Submit](#screen-1-submit)
  - [Screen 2: Live Progress](#screen-2-live-progress)
  - [Screen 3: Interactive Report](#screen-3-interactive-report)
  - [Screen 4: Agent File Preview & Edit](#screen-4-agent-file-preview--edit)
  - [Screen 5: AI-Readiness Dashboard](#screen-5-ai-readiness-dashboard)
  - [Screen 6: Q&A Chat](#screen-6-qa-chat)
- [Additional Features](#additional-features)
- [Key Architectural Decisions](#key-architectural-decisions)
- [Build Order](#build-order)
- [Evaluation Strategy](#evaluation-strategy)

---

## Problem Statement

Every developer has joined a team and stared at a codebase they don't understand. Existing tools like GitHub Copilot help you write code, but nothing helps you understand an unfamiliar codebase systematically — what the architecture is, how modules connect, where the critical business logic lives, what the common patterns are.

The onboarding process at most companies looks like this:

- **First 10 minutes**: "What even is this?" — no high-level overview exists, or the README is outdated.
- **First hour**: "How do I run this?" — setup instructions are missing, incomplete, or wrong.
- **First day**: "Where does X happen?" — tracing a feature through the codebase is trial-and-error.
- **First week**: "What are the unwritten rules?" — conventions exist but are learned through osmosis over weeks.

Simultaneously, the rise of AI coding assistants (Claude Code, GitHub Copilot, Cline, Aider) has created a second problem: these tools perform dramatically better when they have context files describing the project's conventions, structure, and constraints. Almost nobody writes these files well, or at all.

This project solves both problems from a single automated analysis.

---

## Project Overview

The **Codebase Onboarding Agent** is a LangGraph-powered system that takes a GitHub repository URL, performs a deep automated analysis, and produces three categories of output:

1. **Human-readable onboarding documentation** — a structured, multi-section interactive report that answers every question a new developer has on day one.
2. **Machine-readable AI assistant context files** — optimized context files for Claude Code, GitHub Copilot, Cline, and Aider that make AI tools understand the codebase from the first interaction.
3. **AI-readiness diagnostic** — a scored assessment across six dimensions with a prioritized improvement roadmap.

The value proposition: *"Paste a GitHub URL. Get a complete onboarding document for humans AND optimized context files for your AI coding tools. Your team onboards faster, and your AI assistants write better code from day one."*

---

## Architecture Overview

The system consists of four major components:

### 1. React Frontend
- URL input, configuration options, live progress streaming, interactive report viewer, Q&A chat interface
- Communicates with backend via REST (for submissions) and WebSocket (for live progress streaming)

### 2. FastAPI Backend
- API server handling analysis requests and serving results
- WebSocket endpoint for streaming node-by-node progress updates to the frontend
- Job queue for managing analysis requests
- Serves cached results when the same repo+commit has already been analyzed

### 3. LangGraph Pipeline Engine
- The core analysis system — a stateful graph with 8 nodes, conditional edges, cyclic processing, and fan-out/fan-in patterns
- Streams progress events back to the backend via LangGraph's `astream_events` method
- Uses LangGraph checkpointing for state persistence across cycles

### 4. External Services
- **GitHub API**: Clone repos, fetch file contents, read metadata
- **OpenAI API**: LLM calls for semantic analysis (module summarization, pattern detection, scoring)
- **LangSmith**: Tracing and observability for every graph execution

### 5. Storage Layer
- **SQLite**: Analysis result cache keyed by `repo_url + commit_hash`, session data
- **File system**: Cloned repository storage, generated output files

### Communication Flow
```
Frontend ──REST──> FastAPI ──triggers──> LangGraph Pipeline
Frontend <──WebSocket── FastAPI <──astream_events── LangGraph Pipeline
LangGraph Pipeline ──> GitHub API (clone/fetch)
LangGraph Pipeline ──> OpenAI API (LLM analysis)
LangGraph Pipeline ──> LangSmith (tracing)
FastAPI ──> SQLite (cache results)
```

---

## Tech Stack

| Component | Technology | Justification |
|-----------|-----------|---------------|
| Pipeline orchestration | LangGraph | Cyclic, conditional, stateful workflows with checkpointing |
| Backend framework | FastAPI | Native async, WebSocket support, direct LangGraph integration (both Python) |
| LLM provider | OpenAI API | Structured outputs, reliable function calling |
| Schema enforcement | Pydantic | Typed state models, structured output validation at every node |
| AST parsing | tree-sitter | Multi-language AST parsing for static analysis |
| Database | SQLite | Simple deployment, sufficient for single-user/portfolio use |
| Frontend | React | Interactive report viewer, dependency graph visualization |
| Graph visualization | D3.js or react-flow | Interactive module dependency graph |
| Observability | LangSmith | Full trace logging for every graph execution |
| Deployment | Vercel (frontend) + Railway/Render (backend) | Free-tier friendly |

---

## LangGraph Pipeline

The pipeline consists of 8 nodes with conditional edges, one self-loop (cycle), and one fan-out/fan-in pattern.

```
START
  │
  ▼
[Node 1: Structure Scanner]
  │
  ▼
[Node 2: Dependency Analyzer]
  │
  ▼
[Node 3: Module Deep-Diver] ◄──── cycle (while pending modules exist)
  │
  ▼ (all modules done)
[Node 4: Pattern Detector]
  │
  ▼
[Node 5: AI-Readiness Scorer]
  │
  ▼
[Node 6: Output Router]
  │
  ├──────────────┬──────────────┐   (parallel fan-out)
  ▼              ▼              ▼
[7a: Doc Gen] [7b: Agent Gen] [7c: Readiness Report]
  │              │              │
  └──────────────┴──────────────┘   (fan-in)
  │
  ▼
[Node 8: Final Assembler]
  │
  ▼
END
```

---

### Node 1: Structure Scanner

**Purpose**: Build the initial structural skeleton of the repository. This is the foundation that all subsequent nodes build upon.

**Input**: Repository URL or local path.

**Processing**:
- Clone the repository (or access local path)
- Walk the directory tree (2 levels deep for the overview, full depth for analysis)
- Identify entry points: `main.py`, `index.ts`, `app.py`, `server.js`, route directories, etc.
- Identify configuration files: `package.json`, `pyproject.toml`, `tsconfig.json`, `Dockerfile`, `.env.example`, CI configs, etc.
- Identify build/test/lint scripts from package manifests and Makefiles
- Classify file types and count lines per directory

**LLM Usage**: None. This node is entirely deterministic — file system traversal and pattern matching.

**Writes to State**:
- `metadata.repo_url`
- `metadata.commit_hash`
- `metadata.directory_tree`
- `metadata.entry_points`
- `metadata.config_files`

---

### Node 2: Dependency Analyzer

**Purpose**: Build a complete picture of the project's technology profile and internal dependency structure.

**Processing**:
- Parse package manifests (`package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `go.mod`) for external dependencies with versions
- Build an import graph: for every source file, extract import/require statements and map them to either external packages or internal modules
- Scan all source files for environment variable references (`process.env.*`, `os.environ.*`, `os.getenv()`, `.env` file patterns)
- For each env var: record the variable name, which files reference it, what format it appears to expect (URL, API key, boolean, number), and whether a default value exists

**LLM Usage**: One call to synthesize the technology profile from the raw data — "Given these dependencies and configs, describe this project's tech stack in structured format."

**Writes to State**:
- `dependencies.tech_stack` — structured TechProfile (framework, language version, key libraries, deployment target)
- `dependencies.packages` — list of Package objects (name, version, category)
- `dependencies.import_graph` — directed graph of file-to-file imports
- `dependencies.env_vars` — list of EnvVar objects (name, files_used_in, expected_format, has_default)

---

### Node 3: Module Deep-Diver

**Purpose**: The core analysis engine. Iteratively analyzes individual modules/files, building understanding incrementally. This is where LangGraph's cyclic execution is essential.

**Processing (per cycle)**:
1. Check `modules.pending` list. If empty, exit the cycle (conditional edge routes to Node 4).
2. Pop the highest-priority file from `modules.pending`.
3. Read the file's full content.
4. Send to LLM with context:
   - The file's content (full text)
   - Compressed summaries of all previously analyzed modules (100-200 tokens each)
   - The directory tree skeleton
   - The import graph relevant to this file
5. LLM returns a structured `ModuleSummary`:
   - Purpose (one-line description of what this module does)
   - Public interfaces (exported functions, classes, components with signatures)
   - Internal dependencies (what other modules it imports from and why)
   - External dependencies (what libraries it uses)
   - Key patterns observed (error handling style, data access pattern, etc.)
6. If the file is an API route handler, also extract endpoint details: method, path, middleware, request/response shapes, downstream calls.
7. Compress the full file content into a summary and replace it in state (the raw content is no longer needed).
8. Update `modules.analyzed` (append) and `modules.pending` (may add newly discovered important files).
9. Route back to step 1 (cycle continues).

**Priority Ranking Logic** (determines order of analysis):
- Files with the highest hub score in the import graph (most imported by others) go first
- Entry points are analyzed early
- Config/utility files are deprioritized unless heavily imported
- Test files are skipped during deep-dive (analyzed separately for coverage metrics)

**Cycle Termination**:
- All files in `modules.pending` have been processed, OR
- A configurable maximum number of files has been analyzed (default: 50), OR
- The user-selected depth setting caps analysis ("quick" = 15 files, "standard" = 30, "deep" = 50)

**LLM Usage**: One call per file per cycle. This is the most LLM-intensive node.

**Writes to State**:
- `modules.analyzed` — appended each cycle with a new ModuleSummary
- `modules.pending` — updated each cycle (items removed, possibly new items added)
- `modules.module_connections` — updated graph of how analyzed modules connect
- `modules.api_endpoints` — appended when route handlers are found
- `modules.feature_flows` — appended when traceable feature paths are identified

**Key LangGraph Pattern**: Conditional edge after this node checks `len(state.modules.pending) > 0`. If true, routes back to Node 3 (cycle). If false, routes to Node 4.

---

### Node 4: Pattern Detector

**Purpose**: Analyze the accumulated module summaries to identify cross-cutting patterns, conventions, inconsistencies, and potential issues.

**Processing**:
- Feed all module summaries (compressed) to the LLM in one call
- Ask for identification of:
  - **Recurring conventions**: error handling pattern, data access pattern, naming conventions, file organization conventions, testing conventions, import style
  - **Inconsistencies**: places where the codebase deviates from its own conventions (potential bugs or tech debt)
  - **Dead code indicators**: exported functions/components that nothing imports, route handlers not reachable from routing config
  - **Complexity hotspots**: files or functions flagged during deep-dive as unusually complex, deeply nested, or excessively long
  - **"How to add a..." patterns**: infer the standard workflow for common tasks (add a new API endpoint, add a new database model, add a new page/route) based on detected conventions

**LLM Usage**: One comprehensive call with all summaries. Optionally a second call for the "how to add" guides.

**Writes to State**:
- `patterns.conventions` — list of Convention objects (name, description, example_files, pattern)
- `patterns.inconsistencies` — list of Issue objects (description, files_involved, severity, possible_explanation)
- `patterns.dead_code` — list of FilePath objects (file, export, reason_flagged)
- `patterns.complexity_hotspots` — list of Hotspot objects (file, function, line_count, nesting_depth, description)

---

### Node 5: AI-Readiness Scorer

**Purpose**: Evaluate the codebase across six dimensions that determine how well AI coding assistants will perform on it. Produce scores, a radar chart data structure, and a prioritized action plan.

**Processing**:
- For each of the six dimensions, compute a score (0-10) using a mix of deterministic measurement and LLM assessment:

*See the [AI-Readiness Scoring System](#ai-readiness-scoring-system) section for full dimension details.*

- Compute weighted overall score
- Generate prioritized recommendation list ordered by effort-to-impact ratio

**LLM Usage**: One call for the qualitative assessment dimensions (Consistency, Discoverability narrative). The quantitative dimensions (Type Safety, Modularity, Test Coverage, Dependency Hygiene) are computed deterministically from state data.

**Writes to State**:
- `scores.dimension_scores` — dict mapping dimension name to float score
- `scores.overall_score` — weighted average float
- `scores.recommendations` — list of Action objects (description, impact, effort, score_improvement_estimate)
- `scores.agent_file_config` — configuration data needed by the Agent File Generator

---

### Node 6: Output Router

**Purpose**: Decision node that determines which output generators to invoke based on user configuration.

**Processing**:
- Read user's original request configuration (which agent files were selected, what export formats were requested)
- Prepare Send() calls for each required output generator
- Fan out to 7a, 7b, and 7c in parallel

**LLM Usage**: None. Pure routing logic.

**LangGraph Pattern**: Uses LangGraph's `Send` API to invoke multiple nodes in parallel. Each Send includes the relevant slice of state plus the generator-specific configuration.

---

### Nodes 7a/7b/7c: Output Generators (Fan-Out)

These three nodes execute in parallel and are independent of each other.

#### Node 7a: Documentation Generator

**Purpose**: Produce the 7-section onboarding document from accumulated state.

**Processing**:
- Transform state data into the seven report sections (see [Output Specification](#output-specification))
- For each section, make one LLM call with the relevant state slice to generate human-readable prose
- Format output as structured JSON (for the interactive report) and Markdown (for export)

**LLM Usage**: 3-4 calls (some sections can be batched, others need dedicated calls for quality).

**Output**: Structured report data in both JSON and Markdown formats.

#### Node 7b: Agent File Generator

**Purpose**: Generate AI assistant context files for the user's selected tools.

**Processing**:
- Run the Common Knowledge Extractor: pull universal facts from state (stack, commands, conventions, patterns, structure)
- For each selected agent tool, run the tool-specific formatter (see [Agent File Generation](#agent-file-generation))
- Flag uncertain fields with `# VERIFY` comments

**LLM Usage**: One call per agent file (4 maximum).

**Output**: Generated file contents for each selected agent tool.

#### Node 7c: AI-Readiness Report Generator

**Purpose**: Produce the visual readiness report from scoring data.

**Processing**:
- Transform dimension scores into radar chart data structure
- Format the action plan with specific file references and improvement estimates
- Generate the one-line verdict summary

**LLM Usage**: One call for the narrative verdict and action plan descriptions.

**Output**: Structured scoring report data.

---

### Node 8: Final Assembler (Fan-In)

**Purpose**: Collect outputs from all three generators and package them into the final deliverable.

**Processing**:
- Receive outputs from 7a, 7b, and 7c
- Combine into a unified response structure
- Generate export-ready files:
  - Interactive report JSON (consumed by React frontend)
  - Markdown document (downloadable, can be pasted into repo wiki)
  - Structured JSON (for programmatic consumption)
  - Individual agent files (CLAUDE.md, copilot-instructions.md, .clinerules, .aider.conf.yml)
- Store results in SQLite cache keyed by `repo_url + commit_hash`

**LLM Usage**: None. Pure assembly and formatting.

---

## State Schema

The `CodebaseState` is the central data structure that flows through the entire graph. Every node reads from and writes to specific sections of this state. The state is **append-only** — nodes never overwrite previous sections.

```
CodebaseState:
│
├── metadata (written by: Structure Scanner)
│   ├── repo_url: str
│   ├── commit_hash: str
│   ├── directory_tree: Tree
│   ├── entry_points: list[FilePath]
│   └── config_files: list[ConfigFile]
│
├── dependencies (written by: Dependency Analyzer)
│   ├── tech_stack: TechProfile
│   ├── packages: list[Package]
│   ├── import_graph: Graph
│   └── env_vars: list[EnvVar]
│
├── modules (written by: Module Deep-Diver, appended each cycle)
│   ├── analyzed: list[ModuleSummary]
│   ├── pending: list[FilePath]
│   ├── module_connections: Graph
│   ├── api_endpoints: list[Endpoint]
│   └── feature_flows: list[FlowTrace]
│
├── patterns (written by: Pattern Detector)
│   ├── conventions: list[Convention]
│   ├── inconsistencies: list[Issue]
│   ├── dead_code: list[FilePath]
│   └── complexity_hotspots: list[Hotspot]
│
├── scores (written by: AI-Readiness Scorer)
│   ├── dimension_scores: dict[str, float]
│   ├── overall_score: float
│   ├── recommendations: list[Action]
│   └── agent_file_config: AgentConfig
│
└── outputs (written by: Output Generators + Final Assembler)
    ├── report_json: dict
    ├── report_markdown: str
    ├── agent_files: dict[str, str]
    └── readiness_report: dict
```

### Key Pydantic Models

```
ModuleSummary:
  - file_path: str
  - purpose: str (one-line description)
  - public_interfaces: list[Interface] (name, signature, description)
  - internal_deps: list[str] (file paths this module imports from)
  - external_deps: list[str] (libraries used)
  - patterns_observed: list[str]
  - compressed_summary: str (100-200 token summary for downstream use)

Endpoint:
  - method: str (GET, POST, PUT, DELETE, PATCH)
  - path: str
  - handler_file: str
  - handler_function: str
  - middleware: list[str]
  - request_shape: dict (inferred from validation/types)
  - response_shape: dict (inferred from return statements/types)
  - downstream_calls: list[str] (services/functions called)

Convention:
  - name: str
  - description: str
  - example_files: list[str] (2-3 files that demonstrate this pattern)
  - pattern_type: str (error_handling, data_access, naming, file_org, testing, imports)

TechProfile:
  - primary_language: str
  - language_version: str
  - framework: str
  - framework_version: str
  - key_libraries: list[str]
  - deployment_target: str (inferred from configs)
  - build_tool: str
  - test_framework: str
  - linter: str | None
  - formatter: str | None

Action:
  - description: str
  - impact: str (high, medium, low)
  - effort: str (high, medium, low)
  - affected_dimension: str
  - score_improvement_estimate: str (e.g., "Type Safety: 5 → 7.5")
  - specific_files: list[str] (files to modify)
```

---

## Context Window Management

Large codebases won't fit in a single LLM context. This is the most important engineering challenge in the project.

### Strategy: 5-Step Progressive Compression

**Step 1: Static Pre-processing (Zero LLM tokens)**

Most structural analysis doesn't need an LLM at all. These operations are purely deterministic:
- Parse AST using `tree-sitter` (multi-language support)
- Extract import/require/include statements via AST or regex
- Map the directory tree via `os.walk`
- Identify file types by extension and content
- Count lines per file/directory
- Parse package manifests for dependencies
- Extract environment variable references via regex

This eliminates the majority of context window pressure before any LLM call is made.

**Step 2: Priority Ranking (1 LLM call)**

Not all files need deep analysis. Rank files by:
- **Hub score**: files imported by the most other files (from the import graph). High-hub files are architectural anchors.
- **Entry point proximity**: files that are direct entry points or one import away from entry points.
- **File size**: very large files are likely important but need careful handling.
- **File type relevance**: source code > configuration > documentation > test files > generated files.

One LLM call to review the ranked list and adjust priorities based on file names and directory context ("this looks like the main business logic directory").

Top N files (based on user-selected depth) go into `modules.pending`.

**Step 3: File-by-File Deep Dive (1 LLM call per file)**

Each cycle of the Module Deep-Diver sends the LLM:
- **Full content** of the current file (the one being analyzed)
- **Compressed summaries** of all previously analyzed files (100-200 tokens each)
- **Directory tree skeleton** (truncated, just top 2 levels)
- **Relevant import graph slice** (what this file imports, what imports this file)

This means the LLM always has maximum context for the file under analysis, plus enough surrounding knowledge to understand connections.

**Step 4: Summary Compression (after each cycle)**

After analyzing a file, its full content is replaced in state with a compressed summary (100-200 tokens). This summary includes:
- One-line purpose
- Public interface signatures
- Key dependencies
- Patterns observed

This keeps the cumulative state within budget even for large repos. After analyzing 50 files, the summaries consume roughly 50 × 150 = 7,500 tokens — well within limits.

**Step 5: Cross-Module Reasoning (uses summaries only)**

The Pattern Detector and AI-Readiness Scorer operate on compressed summaries, never on raw file contents. This is sufficient for identifying patterns, inconsistencies, and computing scores — the fine-grained detail was already captured during the deep-dive phase.

### Context Budget Estimates

| Operation | Tokens consumed |
|-----------|----------------|
| Directory tree skeleton | ~500 |
| Import graph for current file | ~200 |
| Current file content (average) | ~2,000 |
| 30 compressed summaries | ~4,500 |
| System prompt + instructions | ~1,000 |
| **Total per deep-dive cycle** | **~8,200** |
| Response (structured ModuleSummary) | ~500 |

With GPT-4o's 128K context window, this leaves massive headroom. Even at 50 analyzed files, the cumulative summaries only consume ~7,500 tokens.

---

## Output Specification

The onboarding document is NOT a single monolithic file. It is a structured, multi-section interactive report — something between a wiki and a dashboard.

### Section 1: Project Identity Card

A single-screen summary — the "README that should have existed."

**Contents**:
- Project name and one-line description (inferred from package.json, README, or top-level comments)
- Tech stack with exact versions (not just "React" but "React 18.2 with Next.js 14 App Router")
- Repository structure as a visual tree — 2 levels deep, with annotations on what each top-level directory contains
- Entry points clearly marked (where does the app start? where do API requests enter? where's the main config?)
- External service dependencies (databases, APIs, auth providers, queues) inferred from env vars, configs, and imports

**Format**: Visual card layout — scannable, not scrollable.

### Section 2: Environment & Setup Guide

Generated by analyzing the project, not guessing.

**Contents**:
- Complete list of required environment variables with:
  - Variable name
  - Where it's used (which files reference it)
  - What it appears to expect (URL format? API key? boolean?)
  - Whether a default exists
- Step-by-step setup commands, inferred from package managers, Dockerfiles, Makefiles, and scripts
  - Not generic "run npm install" but the actual sequence specific to this project
  - Both Docker and local development paths if both exist
- Common pitfalls and prerequisites (Node version requirements, database setup, seed scripts)

**Format**: Numbered step list with copy-paste commands. Each step has a "why" annotation.

### Section 3: API & Endpoint Map

Complete inventory of all route definitions.

**Contents per endpoint**:
- HTTP method and path
- Handler function name and file location
- Middleware/auth guards applied
- Request shape (inferred from validation schemas, TypeScript types, or parameter usage)
- Response shape (inferred from return statements and types)
- Database queries or external service calls it makes

**Format**: Interactive table — sortable by path, filterable by method, clickable to expand details. Essentially a locally-generated Swagger doc that also shows implementation paths.

### Section 4: Module Dependency Graph

Architectural visualization of how modules connect.

**Contents**:
- Which modules import from which other modules
- High-connectivity hubs identified (the files everything depends on)
- Circular dependencies flagged
- Distinction between internal module imports and external library usage
- Files grouped into logical clusters (even if directory structure doesn't reflect this cleanly)

**Format**: Interactive graph visualization (D3.js or react-flow). Nodes = modules/files, edges = import relationships. Click a node to see its summary, public exports, and dependents. Color-coded by directory or logical function.

### Section 5: Feature Flow Maps

"Where does X happen?" traces for each major feature.

**Contents per feature flow**:
- Starting point (user action or entry point)
- Each step in the flow: file, function, what it does
- External service calls at each step
- Database interactions at each step

**Example**: "User Checkout Flow — starts at `/pages/checkout.tsx`, calls `useCart()` hook from `/hooks/useCart.ts`, which reads from CartContext, on submit calls `/api/checkout` which invokes `processOrder()` in `/lib/orders.ts`, which calls Stripe via `/lib/stripe.ts` and writes to DB via Prisma model `Order`."

**Format**: Vertical flow diagram per feature — simplified sequence diagram. Each step shows file, function, and action. Clickable to jump to code context.

### Section 6: Pattern & Convention Guide

The "unwritten rules" section.

**Contents**:
- Detected coding patterns with code examples:
  - Error handling pattern
  - Data access pattern
  - Component structure pattern
  - Testing convention
  - Import style convention
  - Naming convention
- Inconsistencies flagged with file references:
  - Where conventions are violated (potential bugs or intentional exceptions)
- "How to add a..." guides:
  - Step-by-step instructions for common tasks, following the codebase's own conventions
  - "How to add a new API endpoint"
  - "How to add a new database model"
  - "How to add a new page/route"
- Complexity hotspots:
  - Files/functions with unusually high complexity, with summaries
- Dead code:
  - Exported functions nothing imports
  - Route handlers not reachable from routing config

**Format**: Structured list with code examples from the repo. Each pattern has "where to see it" references.

### Section 7: Suggested First Tasks & Orientation Paths

"What should I look at first?" guide.

**Contents**:
- Ordered reading list of 5-7 key files with brief annotations explaining why each is important and what to focus on
- Priority-ranked by architectural importance
- Areas of concern flagged (tech debt, disorganized directories, deprecated modules)

**Format**: Numbered reading list with file paths and one-line annotations.

---

## AI-Readiness Scoring System

A framework for measuring how well AI coding assistants will perform on a codebase. Scored across six dimensions, each independently, with a weighted overall score.

### Dimension 1: Discoverability
**Weight**: 15%

**What it measures**: Can the AI tool understand what the project is and how it's structured without guessing?

**Scoring criteria**:
- README exists and is substantive (not a template with placeholder text)
- AI context files exist (CLAUDE.md, copilot-instructions, .clinerules)
- Directory structure is self-documenting (clear names, logical grouping)
- Entry points are identifiable (obvious main files, clear routing structure)

**Measurement**: Check for presence and substantiveness of each artifact. Empty/template README = 0. README with setup, architecture, and contribution guidelines = high score.

### Dimension 2: Type Safety & Annotations
**Weight**: 25%

**What it measures**: Can the AI infer types when generating code?

**Scoring criteria**:
- Percentage of functions with explicit return types
- Percentage of function parameters that are typed
- TypeScript strict mode enabled (or Python type hints, or equivalent)
- API boundaries have schema definitions (Zod, Pydantic, JSON Schema)
- Database models are explicitly defined (Prisma, SQLAlchemy, TypeORM)

**Measurement**: Deterministic — parse AST, count typed vs untyped functions, check tsconfig strict settings.

### Dimension 3: Consistency & Conventions
**Weight**: 25%

**What it measures**: Are patterns consistent enough for AI to learn from them?

**Scoring criteria**:
- Naming conventions are uniform (no camelCase/snake_case mixing)
- Error handling pattern is consistent across the codebase
- File organization follows a detectable convention
- Import styles are consistent (relative vs absolute, barrel exports vs direct)
- Linter/formatter config exists and is enforced

**Measurement**: Pattern analysis from Node 4's output — ratio of consistent to inconsistent pattern applications.

### Dimension 4: Modularity & Boundaries
**Weight**: 15%

**What it measures**: Is the code modular with clear interfaces?

**Scoring criteria**:
- Number of circular dependency chains
- Modules have clear public interfaces (index files, barrel exports, explicit __init__.py)
- File size distribution (flag files over 500 lines)
- Function complexity distribution (flag functions over 50 lines or deeply nested)

**Measurement**: Deterministic — import graph analysis for circular deps, line counts from scanner, AST analysis for nesting depth.

### Dimension 5: Test Coverage & Verifiability
**Weight**: 10%

**What it measures**: Can AI-generated code be verified?

**Scoring criteria**:
- Test suite exists and is runnable
- Approximate coverage (test file count relative to source files, or from coverage config)
- CI pipeline runs tests automatically
- Test commands are documented and discoverable

**Measurement**: File counting, CI config detection, test command extraction from scripts.

### Dimension 6: Dependency Hygiene
**Weight**: 10%

**What it measures**: Will AI tools suggest sensible imports?

**Scoring criteria**:
- Number of unused dependencies
- Duplicate libraries serving the same purpose (both axios and got, both moment and dayjs)
- Dependencies with known vulnerabilities (audit results)
- Dependency versions pinned vs loose ranges

**Measurement**: Deterministic — dependency analysis from Node 2, plus audit command execution.

### Scoring Output Format

The report has three layers:

**Layer 1 — Dashboard view**: Radar chart across six dimensions + overall score + one-line verdict.

**Layer 2 — Detailed breakdown**: Per-dimension score, what was measured, specific findings with file references, comparison to "fully optimized" baseline.

**Layer 3 — Action plan**: Prioritized improvements ordered by effort-to-impact ratio. Each item includes:
- Specific description ("Add return types to the 23 untyped functions in /lib/")
- Estimated effort ("~1 hour")
- Score improvement ("Type Safety: 5 → 7.5")
- Files to modify

---

## Agent File Generation

### CLAUDE.md (Claude Code)

**Location**: Repository root (`CLAUDE.md`)

**Purpose**: Automatically read by Claude Code when entering the project. Dense briefing document.

**Contents**:
- Project overview: what it is, what it does, who it's for
- Exact build/test/lint commands (extracted from package.json scripts, Makefile targets, CI configs — not guessed)
- Code style conventions actually followed (inferred from analysis): "use named exports, not default exports", "error handling uses Result types, not try-catch"
- Architecture summary: where things live and why
- Key constraints: "never import from /internal directly, always go through barrel exports in /lib"
- Common gotchas: circular dependency risks, similar-looking files that serve different purposes, deprecated modules

**Style**: Dense, precise, actionable. Bullet points and commands, not prose. Instructions to a capable developer who's never seen the repo.

### copilot-instructions.md (GitHub Copilot)

**Location**: `.github/copilot-instructions.md`

**Purpose**: Workspace-level instruction file influencing code completions and chat in VS Code.

**Contents**:
- Coding conventions and style rules (influences completions)
- Preferred libraries: "use dayjs not moment, use zod for validation, use custom fetcher in /lib/api.ts instead of raw fetch"
- Patterns for common tasks: "new API routes should follow the pattern in /api/users/index.ts"
- Things to avoid: "don't suggest any types, don't use var, don't import from node_modules paths directly"

**Style**: Short, directive. Rules not explanations. Optimized for influencing autocomplete behavior.

### .clinerules (Cline)

**Location**: Repository root (`.clinerules`)

**Purpose**: Project-specific rules guiding Cline's autonomous coding behavior.

**Contents**:
- Project structure overview (where to create new files)
- Testing requirements: "every new function in /lib must have a corresponding test"
- Deployment constraints: "deploys to Vercel, no server-side file system access"
- Approval gates: "changes to /lib/auth or /lib/billing should be flagged for review"
- Architecture boundaries: "/client should never import from /server directly"

**Style**: Constraint-oriented. What not to do, what requires caution. Guardrails for autonomous operation.

### .aider.conf.yml (Aider)

**Location**: Repository root (`.aider.conf.yml` + optional convention files)

**Contents**:
- Repo map configuration (which files to always include in context, which to exclude)
- Convention notes guiding code generation
- Test command (so Aider can verify its changes)
- Lint command (same reason)
- File patterns to ignore (build artifacts, generated files, vendor directories)

**Style**: YAML structured. Explicit file include/exclude patterns. Configuration-oriented.

### Generation Architecture

The generation flow is:

```
Accumulated CodebaseState
        │
        ▼
Common Knowledge Extractor
(stack, commands, conventions, patterns, structure)
        │
        ├──> Claude Formatter ──> CLAUDE.md
        ├──> Copilot Formatter ──> copilot-instructions.md
        ├──> Cline Formatter ──> .clinerules
        └──> Aider Formatter ──> .aider.conf.yml
        │
        ▼
Human Review & Edit (preview in UI, tweak, then export)
        │
        ▼
Export (download files or auto-commit via GitHub API)
```

**Design principle**: One extraction, four formatters. When a tool changes its instruction format, only one formatter is updated — nothing else in the pipeline changes.

**Uncertain fields**: Any extracted data the system isn't confident about is marked with `# VERIFY: [reason for uncertainty]` comments in the generated files.

**User selection**: Users choose which agent tools they use via multi-select in the UI. Only selected formatters run. Don't generate files for tools the user doesn't use.

---

## Frontend Specification

### Screen 1: Submit
- Text input for GitHub URL
- Multi-select checkboxes for agent files to generate (Claude, Copilot, Cline, Aider)
- Analysis depth selector: Quick (15 files), Standard (30 files), Deep (50 files)
- Submit button triggers `POST /api/analyze`

### Screen 2: Live Progress
- WebSocket connection receives node-by-node updates
- Visual progress indicator showing:
  - Which node is currently executing
  - What it's currently analyzing ("Deep-diving into /lib/auth.ts...")
  - Completed nodes with brief result summaries
  - Estimated time remaining

### Screen 3: Interactive Report
- Tabbed interface with 7 tabs corresponding to the 7 output sections
- Section 4 (Dependency Graph) renders as an interactive D3.js/react-flow visualization
- Section 3 (API Map) renders as a sortable/filterable table
- All sections are searchable
- Export button: download as Markdown or JSON

### Screen 4: Agent File Preview & Edit
- Side-by-side editor showing generated content for each selected agent file
- Syntax-highlighted Markdown/YAML editing
- `# VERIFY` comments highlighted in yellow for easy identification
- Save/export button per file
- "Copy to clipboard" functionality

### Screen 5: AI-Readiness Dashboard
- Radar chart visualization (6 axes, one per dimension)
- Overall score prominently displayed
- One-line verdict
- Expandable detail cards per dimension
- Action plan as a prioritized list with effort/impact tags

### Screen 6: Q&A Chat
- Chat interface for follow-up questions about the analyzed codebase
- Uses the cached `CodebaseState` — no re-analysis needed
- Questions like "How does authentication work?" or "What happens when a user creates a project?" are answered by referencing accumulated knowledge in state
- Responses grounded in actual codebase analysis, not generic knowledge

---

## Additional Features

### Interactive Q&A Mode
After generating the initial report, the user can ask follow-up questions about the codebase. The LangGraph state from the analysis is persisted (checkpointed), so the Q&A agent has full context without re-analyzing. This is where LangGraph's state persistence adds clear value.

### Diff-Aware Updates
If the user runs the agent again after the codebase has changed:
- Compare current commit hash to cached analysis
- Only re-analyze modified files (git diff)
- Update affected sections of the report
- Recalculate AI-readiness scores only for changed dimensions
- Previous run's state serves as baseline (LangGraph checkpointing)

### "How Do I Add a...?" Guides
Based on detected patterns, generate step-by-step guides for common tasks:
- "How to add a new API endpoint" — following the codebase's own conventions
- "How to add a new database model"
- "How to add a new page/route"
- "How to add a new test"

Each guide follows the patterns the agent detected in the existing codebase, not generic advice.

### Complexity Hotspot Identification
Flag files or functions with unusually high cyclomatic complexity, deep nesting, or excessive length. Framed as orientation, not linting: "This file is the most complex in the codebase — here's a summary of what it does so you don't have to parse 800 lines yourself."

### Dead Code Detection
Identify:
- Exported functions or components that nothing imports
- Route handlers not reachable from the app's routing config
- Useful for onboarding: "ignore these, they're probably deprecated"

---

## Key Architectural Decisions

### Why FastAPI, Not Express
LangGraph is Python-native. The graph definition, state schema (Pydantic models), and node functions are all Python. FastAPI provides native async support for WebSocket streaming and direct integration with LangGraph's `astream_events`. No cross-language bridging needed.

### Why SQLite, Not Postgres or Supabase
This is a single-user tool for portfolio purposes. SQLite stores analysis results keyed by `repo_url + commit_hash`. Re-running on the same repo at the same commit returns cached results instantly. Swapping to Postgres later is a config change, not an architectural one. SQLite keeps deployment simple — one process, one file.

### Why Static Pre-processing Exists
The temptation is to send everything to the LLM. But AST parsing, import extraction, line counting, file type detection, and directory traversal are deterministic operations that Python libraries handle perfectly (`tree-sitter`, `ast` module, regex, `os.walk`). By doing this before any LLM call, the majority of context window pressure is eliminated and the pipeline is significantly cheaper to run.

### Why File-by-File Analysis, Not Batch
Each deep-dive cycle sends the LLM one file's content plus compressed summaries of everything analyzed so far. This maximizes context for the current file while maintaining enough surrounding knowledge for cross-module reasoning. Batching multiple files would reduce per-file context and make structured output harder to enforce.

### Why the Output Router Fans Out in Parallel
The three generators (docs, agent files, readiness report) are independent — they read from the same completed state but don't depend on each other. LangGraph's `Send` API runs them simultaneously, cutting final generation latency to the slowest generator instead of the sum of all three.

### Why the Agent File Formatters Are Separate from the Extractor
When Copilot changes its instruction format (and it will — these formats are all evolving), only one formatter needs updating. The Common Knowledge Extractor and all other formatters remain unchanged. This separation of concerns is the standard adapter pattern.

### Why Summaries Replace Raw Content in State
After analyzing a file, its full content (~2,000 tokens average) is replaced with a compressed summary (~150 tokens). For a 50-file analysis, this is the difference between 100,000 tokens of raw content and 7,500 tokens of summaries in state. The fine-grained detail was already captured in the structured ModuleSummary during the deep-dive; downstream nodes only need the compressed version for cross-module reasoning.

---

## Build Order

### Sprint 1: Pipeline Core
- Structure Scanner node (deterministic, no LLM)
- Dependency Analyzer node (one LLM call)
- Static pre-processing layer (tree-sitter AST parsing, import mapping)
- State schema (Pydantic models)
- Basic CLI interface for testing
- **Milestone**: Feed a repo, get structural skeleton + tech profile

### Sprint 2: The Deep-Diver Cycle
- Module Deep-Diver node with cyclic execution
- Summary compression strategy
- Priority ranking logic
- Cycle termination conditions
- Conditional edge implementation
- **Milestone**: Feed a repo, get module-by-module analysis with summaries
- **Test on**: 3-4 real repos of varying sizes (small, medium, large)

### Sprint 3: Pattern Detection & Scoring
- Pattern Detector node
- AI-Readiness Scorer node (6 dimensions)
- Deterministic metric computation
- Scoring calibration against known repos
- **Milestone**: Full analysis pipeline produces patterns, scores, and recommendations

### Sprint 4: Output Generation
- Documentation Generator (7 sections)
- Agent File Generator (4 formatters)
- AI-Readiness Report Generator
- Fan-out/fan-in pattern implementation
- Final Assembler with export formats (Markdown, JSON, agent files)
- **Milestone**: Complete pipeline produces all three output categories

### Sprint 5: Frontend & Integration
- React app setup
- Submit screen with configuration options
- WebSocket streaming for live progress
- Tabbed report viewer
- Interactive dependency graph visualization (D3.js/react-flow)
- Agent file preview and edit interface
- AI-readiness dashboard with radar chart
- Q&A chat interface
- **Milestone**: Full end-to-end user experience

### Sprint 6: Polish & Evaluation
- Run against 10-15 diverse repos
- Document accuracy, edge cases, and failure modes
- Add diff-aware update support
- LangSmith integration for observability
- Write comprehensive README (technical blog post style)
- Deploy to free tier (Vercel + Railway/Render)
- Record demo video
- **Milestone**: Portfolio-ready project with evaluation metrics

---

## Evaluation Strategy

The project's resume value depends on demonstrable quality. Evaluation should cover:

### Accuracy Metrics
- Run against 10-15 repos of varying stacks and sizes
- Manually verify:
  - Are extracted endpoints correct? (precision/recall)
  - Are detected patterns real? (spot-check against manual review)
  - Are setup instructions accurate? (actually follow them and see if the project runs)
  - Are environment variables complete? (compare against actual .env.example)

### AI-Readiness Score Validation
- Score 5 repos manually using the 6-dimension rubric
- Compare manual scores to automated scores
- Report correlation and deviation

### Agent File Quality
- Generate CLAUDE.md for 5 repos
- Use Claude Code with the generated CLAUDE.md on actual tasks
- Compare quality of Claude Code's output with vs without the generated file

### Performance Metrics
- Analysis time by repo size (files, lines of code)
- Token usage per analysis
- Cost per analysis (OpenAI API spend)

### What to Include in the README
- Problem statement and value proposition
- Architecture diagram
- Design decisions with tradeoffs (why LangGraph, why file-by-file, why static pre-processing)
- Evaluation methodology and concrete metrics
- LangSmith trace screenshot showing a full analysis run
- Demo video or GIF
- Known limitations and future improvements

---

*This specification represents the complete architectural plan for the Codebase Onboarding Agent. Each section maps directly to implementation work. The build order provides an incremental path where each sprint produces a testable milestone.*