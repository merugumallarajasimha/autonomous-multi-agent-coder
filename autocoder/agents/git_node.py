# autocoder/agents/git_node.py
from typing import Dict, Any

def git_approval_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handles git approval state and final execution summary logging.
    """
    print("\n📦 Git Approval Node: Preparing changes for commit/PR...")
    
    user_approval = input("\nDo you approve committing these changes? (y/n): ").strip().lower()
    
    if user_approval in ["y", "yes"]:
        print("✅ Changes approved and staged.")
        return {"approved": True}
    else:
        print("❌ Changes rejected by user.")
        return {"approved": False}