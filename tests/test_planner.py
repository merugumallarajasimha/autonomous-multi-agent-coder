import pytest
from autocoder.agents.planner import planner_node


class TestPlannerNode:
    def test_planner_returns_expected_keys(self, tmp_path):
        # Create a minimal repo with one Python file
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "math_ops.py").write_text("def add(a, b):\n    return a + b\n")

        state = {
            "repo_path": str(repo),
            "user_request": "Add a multiply function",
            "history": [],
        }

        result = planner_node(state)

        # Assert structure
        assert isinstance(result, dict)
        assert "plan" in result
        assert isinstance(result["plan"], list)
        assert "target_files" in result
        assert isinstance(result["target_files"], list)
        assert "history" in result
        assert isinstance(result["history"], list)
        assert len(result["history"]) == 1
        assert result["history"][0]["agent"] == "planner"
        assert "steps" in result["history"][0]

    def test_planner_handles_empty_repo(self, tmp_path):
        repo = tmp_path / "empty_repo"
        repo.mkdir()

        state = {
            "repo_path": str(repo),
            "user_request": "Create a new module",
            "history": [],
        }

        result = planner_node(state)

        assert isinstance(result, dict)
        assert "plan" in result
        assert "target_files" in result
        assert "history" in result