# Autonomous Multi-Agent AI Coding Framework - Architecture & Documentation

## Project Overview

This is a LangGraph-based autonomous multi-agent coding framework that orchestrates multiple specialized AI agents to plan, implement, test, review, and fix code automatically. The system uses a state graph to manage the workflow between agents, with each agent responsible for a specific phase of the software development lifecycle.

---

## Core Architecture

### Entry Points
- **`main.py`** - CLI entry point, builds and runs the graph directly
- **`main_api.py`** - FastAPI REST API wrapper around the graph

### State Management
- **`autocoder/state.py`** - Core AgentState TypedDict definition
- **main.py local AgentState** - Extended state with additional fields for the workflow

---

## Agent Nodes (autocoder/agents/)

Each agent is a node function that takes `state: AgentState` and returns `Dict[str, Any]` to update the state.

### 1. Planner (`planner.py`)
**Purpose**: Creates implementation plan and identifies target files
- **Input**: `user_request`, `repo_path`
- **Process**:
  1. Loads/creates repo_map (symbol index of repository)
  2. Filters relevant files using keyword matching
  3. Reads selected files for context
  4. Calls LLM (via ModelRouter) with structured output schema `Plan`
- **Output**: `plan` (list of steps), `target_files` (list of file paths), `history`
- **LLM**: qwen2.5:3b via Ollama
- **Events**: AGENT_STARTED, BUILDING_REPO_MAP, RELEVANCE_FILTERED, PLANNING, PLAN_CREATED, AGENT_FINISHED

### 2. Coder (`coder.py`)
**Purpose**: Generates code implementation and tests
- **Input**: `plan`, `target_files`, `repo_path`, `test_logs` (from previous failures)
- **Process**:
  1. Loads repo_map and filters relevant files
  2. Builds context from repository files
  3. Calls LLM with structured output `MultiFileEdit`
  4. Writes generated files to disk
  5. Falls back to hardcoded templates if LLM fails
- **Output**: `written_files`, `iteration_count`, `history`
- **LLM**: qwen2.5-coder:7b via Ollama
- **Events**: AGENT_STARTED, GENERATING_CODE, FILE_CREATED, AGENT_FINISHED

### 3. Verifier (`verifier.py`)
**Purpose**: Runs unit tests in isolated Docker sandbox
- **Input**: `repo_path`, `iteration_count`
- **Process**:
  1. Builds PYTHONPATH for module resolution
  2. Runs `python -m pytest` in Docker sandbox (or host fallback)
  3. Captures stdout/stderr and return code
- **Output**: `verification_passed`, `test_passed`, `test_logs`, `iteration_count`, `history`
- **Sandbox**: `run_in_sandbox()` with 30s timeout
- **Events**: (uses sandbox directly, no emit calls)

### 4. Reviewer (`reviewer.py`)
**Purpose**: Static analysis + LLM code review
- **Input**: `written_files`, `repo_path`
- **Process**:
  1. Runs deterministic static checks (Ruff) via `run_python_static_checks()`
  2. For each Python file, runs LLM review for logic bugs, error handling, etc.
  3. Combines and validates findings, drops invalid ones
- **Output**: `review_findings`, `is_refactored`, `history`
- **LLM**: qwen2.5-coder:7b via Ollama
- **Events**: STATIC_CHECKS_STARTED, LLM_REVIEW_STARTED, REVIEW_COMPLETED, AGENT_FINISHED

### 5. Security Reviewer (`security_reviewer.py`)
**Purpose**: Security-focused code review
- **Input**: `written_files`, `repo_path`
- **Process**:
  1. Runs deterministic security pattern checks via `run_security_checks()`
  2. Runs LLM security review for auth, injection, crypto, etc.
- **Output**: `security_findings`, `history`
- **Events**: SECURITY_STATIC_CHECKS_STARTED, LLM_SECURITY_REVIEW_STARTED, SECURITY_REVIEW_COMPLETED

### 6. Fixer (`fixer.py`)
**Purpose**: Applies surgical patches based on failures/findings
- **Input**: `bug_report` (from verifier), `review_findings`, `repo_path`
- **Process**:
  1. Builds error context from structured failure report
  2. Reads all repository files for context
  3. Calls LLM to generate fix for single target file
  4. Parses `# FILE:` header to identify target
  5. Writes patched file
- **Output**: `written_files`, `iteration_count`, `verification_passed=False`, `test_passed=False`, `history`
- **LLM**: qwen2.5-coder:7b via Ollama
- **Events**: ANALYZING_FAILURE, APPLYING_FIX, AGENT_FINISHED

### 7. Refactorer (`refactorer.py`)
**Purpose**: Applies cosmetic/refactor changes from reviewer findings
- **Input**: `review_findings` (category: refactor/cosmetic)
- **Process**: For each finding, applies minimal targeted edit
- **Output**: `refactored_files`, `iteration_count`, `history`
- **Events**: NO_REFACTOR_FINDINGS, APPLYING_REFACTOR, AGENT_FINISHED

### 8. Git Approval (`git_node.py` / inline)
**Purpose**: Placeholder for git commit/PR logic
- **Output**: `git_approval: True`

---

## Supporting Infrastructure

### Graph Construction
- **`main.py`** - Primary graph with inline conditional routing
- **`autocoder/graph_builder.py`** - Config-driven graph builder (alternative)

### Graph Flow (main.py)
```
normalize_input → planner → coder → verifier
                         ↓
              decide_after_verifier:
              pass → reviewer
              fail → fixer
              max_iter → git_approval
                         ↓
                   reviewer → decide_after_reviewer:
                   high/critical → fixer
                   pass → git_approval
                         ↓
                   fixer → verifier (re-verify loop)
```

### Routing Logic
- **`decide_after_verifier`**: Checks `test_passed`, `iteration_count` vs `max_iterations`
- **`decide_after_reviewer`**: Checks `review_findings` for high/critical severity

### Event System (`autocoder/events/`)
- **`emitter.py`** - In-memory event log with `emit()`, `get_events()`, `clear_events()`
- **`models.py`** - `AgentEvent` TypedDict and `EVENT_TYPES` frozenset
- Events track agent lifecycle, findings, errors, and workflow milestones

### Configuration (`autocoder/config/loader.py`)
- **`load_workflow()`** - Loads workflow node sequence from YAML
- **`load_models_config()`** - Loads model provider config from YAML
- **`validate_workflow()`** - Validates workflow nodes against registry

### Model Routing (`autocoder/models/router.py`)
- **`ModelRouter`** - Lazy provider instantiation with fallback chain
- **`from_config_file()`** - Loads from config/models.yaml
- **`get_default_config()`** - Hardcoded defaults (Ollama qwen2.5 models)
- Providers: Ollama, OpenRouter, Groq, Google

### Language Adapters (`autocoder/languages/`)
- **`registry.py`** - Maps language names to adapter classes
- **`base.py`** - `LanguageAdapter` abstract base class
- **`python.py`** - `PythonAdapter` with install/build/test/lint/format/clean
- Adapters provide language-agnostic interface for sandbox execution

### Sandbox (`autocoder/tools/docker_sandbox.py`)
- **`run_in_sandbox()`** - Executes commands in hardened Docker container
- **Security**:
  - `--memory=512m --cpus=1`
  - `--cap-drop=ALL --read-only --tmpfs /tmp`
  - `--network=none` by default (`allow_network=False`)
  - Command allowlist (`ALLOWED_COMMANDS`)
  - Host fallback when Docker unavailable
- **Timeout**: 45s default, 30s for verifier

### File Operations (`autocoder/tools/file_ops.py`)
- **`read_file()`** - Safe UTF-8 reading with error handling
- **`write_file()`** - Creates parent dirs, strips markdown fences
- **`list_files()`** - Lists Python files, ignores cache/hidden
- **`clean_code_markdown()`** - Strips ```python``` fences

### Git Tools (`autocoder/tools/git_tools.py`)
- **`generate_pr_summary()`** - Creates PR description from state

### Repo Indexing (`autocoder/index/`)
- **`repo_map.py`** - Builds/loads repo_map.json (files, symbols, imports, entry points)
- **`repo_indexer.py`** - File discovery and indexing
- **`symbol_index.py`** - Symbol extraction per language
- **`relevance.py`** - Keyword-based file relevance filtering
- **`dependency_graph.py`** - Import graph construction

### Analysis (`autocoder/analysis/`)
- **`static_checks.py`** - Ruff/Bandit integration, finding normalization
- **`security_checks.py`** - Pattern-based security detection (secrets, shell=True, eval, pickle, yaml, path traversal)
- **`finding.py`** - Finding TypedDict and validation
- **`failure_classifier.py`** - Deterministic failure classification

### Routing (`autocoder/routing/finding_router.py`)
- Routes findings to handlers: fixer, security_fixer, refactorer, human_approval, report_only

### Reporting (`autocoder/reporting/summary.py`)
- **`render_summary_report()`** - ASCII/UTF-8 box formatting for CLI/API output

---

## Data Flow

### State Keys (AgentState)
| Key | Producer | Consumers |
|-----|----------|-----------|
| `user_prompt` / `user_request` | Input | All agents |
| `repo_path` | Input | All agents |
| `plan` | Planner | Coder |
| `target_files` | Planner | Coder |
| `written_files` | Coder/Fixer | Reviewer, Verifier |
| `test_passed` / `verification_passed` | Verifier | Router, Reporter |
| `test_logs` | Verifier | Coder (for retry context) |
| `review_findings` | Reviewer | Router, Fixer, Reporter |
| `security_findings` | Security Reviewer | Findings Router |
| `iteration_count` | Coder/Verifier/Fixer | Router (max_iterations guard) |
| `max_iterations` | Input | Router |
| `history` | All agents | Reporter, Router |
| `git_approval` | Git Approval | Router, Reporter |

---

## Execution Modes

### CLI (main.py)
```bash
python main.py
# or with options:
python main.py --workflow default --legacy-graph
```

### API (main_api.py)
```bash
uvicorn main_api:app --reload
POST /generate {"user_prompt": "...", "repo_path": "./workspace"}
```

---

## Key Design Patterns

1. **State Graph** - LangGraph StateGraph with TypedDict state
2. **Conditional Edges** - Routing functions return node names based on state
3. **Event Sourcing** - In-memory event log for observability
3. **Lazy Provider Instantiation** - ModelRouter creates providers on-demand
4. **Fallback Chains** - LLM → structured output → hardcoded templates
5. **Sandbox Isolation** - Docker with security hardening, host fallback
6. **Iteration Guard** - `iteration_count` / `max_iterations` prevents infinite loops
7. **Config-Driven** - Workflows, models, agents loaded from YAML

---

## Dependencies

### Core
- `langgraph` - State graph orchestration
- `langchain-ollama` - Local LLM via Ollama
- `pydantic` - Structured output schemas
- `fastapi` + `uvicorn` - API server
- `pytest` - Test execution

### Infrastructure
- `docker` - Sandbox execution
- `pyyaml` - Config loading
- `GitPython` - Git operations

### Analysis
- `ruff` - Python linting/formatting
- `bandit` - Security linting

---

## Project Structure
```
├── main.py                 # CLI entry, graph definition
├── main_api.py             # FastAPI REST wrapper
├── autocoder/
│   ├── state.py            # Core AgentState
│   ├── agents/             # Agent node implementations
│   ├── tools/              # Sandbox, file ops, git
│   ├── events/             # Event system
│   ├── config/             # YAML config loading
│   ├── models/             # Model routing
│   ├── languages/          # Language adapters
│   ├── index/              # Repo indexing
│   ├── analysis/           # Static/security checks
│   ├── routing/            # Finding routing
│   ├── reporting/          # Summary rendering
│   └── graph_builder.py    # Config-driven graph builder
├── config/                 # YAML configs (workflows, models, agents)
├── tests/                  # Unit tests with mocks
├── workspace/              # Working directory for generated code
└── benchmarks/             # Test fixtures
```

---

## Security Considerations

- Docker sandbox: memory/CPU limits, capability drop, read-only rootfs, no network by default
- Command allowlist prevents arbitrary command execution
- Host fallback maintains timeout protection
- No privileged containers, runs as non-root in container

---

## Testing

- Unit tests in `tests/` with mocked LLMs
- `pytest.ini` with deprecation warning filtering
- `conftest.py` with shared fixtures and path setup
- Tests cover: planner, coder, fixer, reviewer, verifier, workflow