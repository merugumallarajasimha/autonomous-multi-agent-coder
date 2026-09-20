# Autonomous Multi-Agent AI Coding Framework - Architecture Summary

## Overview
This is a LangGraph-based multi-agent system that autonomously plans, codes, verifies, fixes, reviews, and commits Python code changes. It runs as a CLI (`main.py`) where users input natural language task requests, and the agent pipeline executes until tests pass or max iterations reached.

---

## Core Architecture

### State Schema (`autocoder/state.py` + `main.py` AgentState)
The workflow state is a `TypedDict` passed between all nodes:

| Field | Type | Description |
|-------|------|-------------|
| `user_request` | str | Original natural language task |
| `repo_path` | str | Absolute path to target repository (`./target_repo`) |
| `feature_branch` | str | Git branch name (default: "main") |
| `plan` | List[str] | Implementation steps from Planner |
| `target_files` | List[str] | Files Planner identified for modification |
| `written_files` | List[str] | **NEW** - Files Coder created/modified this iteration (added by fix) |
| `test_passed` | bool | Result of last Verifier run |
| `test_logs` | str | Stdout/stderr from pytest |
| `static_checks_passed` | bool | Ruff/mypy result (placeholder) |
| `is_refactored` | bool | Whether Reviewer has run |
| `iteration_count` | int | Current fix/review cycle |
| `max_iterations` | int | Cap (default 3) |
| `approved` | bool | User git approval |
| `history` | List[Dict] | Audit trail of all agent actions |
| `bug_report` | Dict | Error details for Fixer |
| `review_findings` | List[Dict] | Reviewer findings |

---

## Agent Pipeline (LangGraph Workflow)

```
main.py → build_graph() → StateGraph(AgentState)
```

### Nodes & Edges

| Node | Function | Input State | Output State |
|------|----------|-------------|--------------|
| **planner** | `planner_node` | `user_request`, `repo_path` | `plan`, `target_files` |
| **coder** | `coder_node` | `plan`, `target_files`, `test_logs`, `repo_path` | `written_files`, `iteration_count` |
| **verifier** | `verifier_node` | `written_files`, `repo_path` | `test_passed`, `test_logs` |
| **fixer** | `fixer_node` | `bug_report` (≡ `test_logs`), `repo_path` | `iteration_count` |
| **reviewer** | `reviewer_node` | `repo_path` | `is_refactored` |
| **git_approval** | `git_approval_node` | — | `approved` |

### Routing Logic (`route_after_verifier` in main.py)
```
verifier → (test_passed & is_refactored) → git_approval
         → (test_passed & !is_refactored) → reviewer
         → (!test_passed & iter < max)    → fixer
         → (!test_passed & iter >= max)   → git_approval (give up)
reviewer → verifier (re-run tests after refactor)
fixer → verifier (re-run tests after fix)
git_approval → END
```

---

## Detailed Agent Responsibilities

### 1. Planner (`autocoder/agents/planner.py`)
- **Model**: `qwen2.5:3b` (small, fast)
- **Output**: Structured `Plan` (steps + target_files)
- **Context**: Lists all `.py` files in repo via `list_files()`
- **Fallback**: Hardcoded to `["Fix logic bug in math_ops.py"]` + `["math_ops.py"]`

### 2. Coder (`autocoder/agents/coder.py`)
- **Model**: `qwen2.5-coder:7b` with structured output (`MultiFileEdit`)
- **Input**: Plan, existing repo context (all files read via `read_file`)
- **Task**: Generates **complete** module + test files
- **Output**: Writes files via `write_file()`, returns `written_files` list
- **Fallback**: Hardcoded `banking_utils.py` + `test_banking_utils.py` if LLM fails

### 3. Verifier (`autocoder/agents/verifier.py`) — **UPDATED**
- **Execution**: Runs pytest via Docker sandbox (`run_in_sandbox`)
- **NEW**: Scopes pytest to only `written_files` that match `test_*.py` or `*_test.py`
- **Fallback**: If no test files in `written_files`, picks 5 most recent test files by mtime
- **PYTHONPATH**: Builds recursive path list for imports
- **Command**: `python -m pytest <test_files> -v` (not bare `pytest`)

### 4. Fixer (`autocoder/agents/fixer.py`)
- **Model**: `qwen2.5-coder:7b` (no structured output)
- **Input**: `bug_report` = `test_logs` from state, full repo context
- **Prompt**: Expects LLM to return `# FILE: path` header + corrected code
- **Parsing**: Extracts file path, writes corrected file
- **Fallback**: Heuristic - first file mentioned in bug_report, or first repo file

### 5. Reviewer (`autocoder/agents/reviewer.py`)
- **Model**: `qwen2.5-coder:7b` with structured output (`ReviewEdit`)
- **Target**: First non-test `.py` file in repo
- **Task**: Adds type hints + Google-style docstrings, **no logic changes**
- **Output**: Writes refactored file, sets `is_refactored: true`

### 6. Git Approval (`autocoder/agents/git_node.py`)
- **Interactive**: Prompts user `y/n` to approve commit
- **Output**: `approved` boolean

---

## Tool Layer

### File Operations (`autocoder/tools/file_ops.py`)
| Function | Signature | Purpose |
|----------|-----------|---------|
| `list_files(repo_path)` | → `List[str]` | Walks repo, returns relative `.py` paths (ignores `__pycache__`, hidden) |
| `read_file(filepath)` | → `str` | Safe read with encoding fallback |
| `write_file(repo, rel_path, content)` | → `None` | Creates dirs, strips markdown fences, writes |
| `clean_code_markdown(content)` | → `str` | Removes ````python` blocks |

### Docker Sandbox (`autocoder/tools/docker_sandbox.py`)
| Function | Purpose |
|----------|---------|
| `is_docker_available()` | Checks `docker info` |
| `run_in_sandbox(repo_path, command, timeout)` | Mounts repo at `/app`, runs in `python:3.11-slim` with 512MB RAM; falls back to host `subprocess.run` if Docker unavailable |

### Git Tools (`autocoder/tools/git_tools.py`)
| Function | Purpose |
|----------|---------|
| `prepare_task_branch(repo_path, task_id)` | Creates `autocoder/task-{id}` branch |
| `generate_pr_summary(state)` | Formats markdown summary for PR |

---

## Data Flow Example

**User Input**: "Create a BankAccount class with deposit/withdraw and tests"

1. **main.py** creates `initial_state` with `user_request`, `repo_path="./target_repo"`
2. **Planner** reads repo files → returns `plan` + `target_files: ["banking_utils.py", "test_banking_utils.py"]`
3. **Coder** reads all existing files as context → LLM generates `banking_utils.py` + `test_banking_utils.py` → writes both → returns `written_files: ["banking_utils.py", "test_banking_utils.py"]`
4. **Verifier** reads `written_files`, filters to `["test_banking_utils.py"]` → runs `python -m pytest test_banking_utils.py -v` in sandbox → returns `test_passed`, `test_logs`
5. **Router**: If passed → Reviewer; if failed → Fixer (up to 3 iterations)
6. **Reviewer** finds `banking_utils.py` (non-test) → adds type hints/docstrings → sets `is_refactored: true`
7. **Verifier** re-runs tests on same `written_files`
8. **Git Approval** prompts user → if yes, workflow ends

---

## Key Design Patterns

| Pattern | Implementation |
|---------|----------------|
| **State-passing** | Single `AgentState` dict mutated by each node |
| **Structured LLM Output** | Pydantic models (`Plan`, `MultiFileEdit`, `ReviewEdit`) via `.with_structured_output()` |
| **Fallback Strategies** | Every LLM call has hardcoded fallback for parsing/timeout failures |
| **Markdown Sanitization** | `clean_code_markdown()` strips ````python` fences before write |
| **Sandboxed Execution** | Docker preferred, host fallback; `pytest` installed at runtime |
| **Iterative Fix Loop** | `iteration_count` + `max_iterations` prevents infinite retries |
| **Human-in-the-loop** | Final git approval requires user confirmation |

---

## Repository Structure

```
.
├── main.py                      # CLI entry, graph build, state init
├── autocoder/
│   ├── state.py                 # Shared TypedDict schema
│   ├── agents/
│   │   ├── planner.py           # Planning agent
│   │   ├── coder.py             # Code generation agent
│   │   ├── fixer.py             # Bug fix agent
│   │   ├── verifier.py          # Test execution agent (scoped to written_files)
│   │   ├── reviewer.py          # Code review/refactor agent
│   │   ├── git_node.py          # User approval gate
│   │   └── git_agent.py         # Branch/commit helpers (unused in main graph)
│   └── tools/
│       ├── file_ops.py          # FS utilities
│       ├── docker_sandbox.py    # Isolated test runner
│       └── git_tools.py         # PR summary generator
├── target_repo/                 # Working directory (user code + tests)
│   ├── *.py                     # Current task files
│   └── calculator_module/       # Leftover files from previous tasks
└── runs/                        # Execution traces (JSON)
```

---

## Critical Fix Applied (This Session)

**Problem**: Verifier ran bare `pytest` across entire `target_repo/`, picking up stale tests from previous tasks (e.g., `calculator_module/test_*.py`). Fixer then patched those unrelated files.

**Solution**:
1. **coder.py**: Added `"written_files": written_files` to returned state (line 130)
2. **verifier.py**: Reads `state["written_files"]`, filters to test files, runs `python -m pytest <test_files> -v` only on those

**State Field Added**: `written_files: List[str]` — populated by Coder, consumed by Verifier. No Pydantic schema change needed (plain dict key).

---

## Configuration & Models

| Agent | Model | Temperature | Timeout | Structured Output |
|-------|-------|-------------|---------|-------------------|
| Planner | `qwen2.5:3b` | 0 | default | `Plan` |
| Coder | `qwen2.5-coder:7b` | 0 | 60s | `MultiFileEdit` |
| Fixer | `qwen2.5-coder:7b` | 0 | 60s | None (raw) |
| Verifier | N/A (pytest) | — | 30s | — |
| Reviewer | `qwen2.5-coder:7b` | 0 | 30s | `ReviewEdit` |

All models via `langchain_ollama.ChatOllama` (local Ollama server required).

---

## Execution Traces

Each run saves `runs/run_<timestamp>.json` with full final state including `history` array for debugging/audit.