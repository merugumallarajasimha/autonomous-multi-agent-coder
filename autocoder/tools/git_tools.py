# autocoder/tools/git_tools.py
import subprocess
from autocoder.state import AgentState

def prepare_task_branch(repo_path: str, task_id: str) -> str:
    branch_name = f"autocoder/task-{task_id}"
    subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo_path, check=True)
    return branch_name

def generate_pr_summary(state: AgentState) -> str:
    findings = state.get("review_findings", [])
    
    summary = []
    summary.append("## 🤖 Autocoder Task Resolution Summary")
    summary.append(f"**Task Request:** {state['user_request']}")
    summary.append(f"**Branch:** `{state['feature_branch']}`\n")
    summary.append("### Verification Results")
    summary.append(f"- **Static Analysis (Ruff/Mypy):** {'✅ PASS' if state['static_checks_passed'] else '❌ FAIL'}")
    summary.append(f"- **Unit Tests (Pytest):** {'✅ PASS' if state['test_passed'] else '❌ FAIL'}")
    summary.append(f"- **Security & Logic Review:** {len(findings)} findings detected\n")
    
    if findings:
        summary.append("### Resolved Code Review Findings")
        for f in findings:
            summary.append(f"- `[{f['severity']}]` **{f['file']}:{f['line']}** - {f['issue']}")
            
    return "\n".join(summary)