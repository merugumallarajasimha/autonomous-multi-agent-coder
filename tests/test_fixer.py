import pytest
from autocoder.agents.fixer import fixer_node


class TestFixerNode:
    def test_fixer_returns_expected_keys(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        # Create a file with a bug
        (repo / "buggy.py").write_text("def add(a, b):\n    return a - b\n")  # intentional bug

        state = {
            "repo_path": str(repo),
            "bug_report": "Test failed: expected 3, got -1",
            "iteration_count": 0,
            "history": [],
        }

        result = fixer_node(state)

        # Assert structure - should not raise
        assert isinstance(result, dict)
        assert "iteration_count" in result
        assert isinstance(result["iteration_count"], int)
        assert result["iteration_count"] == 1
        assert "history" in result
        assert isinstance(result["history"], list)
        assert len(result["history"]) == 1
        assert result["history"][0]["agent"] == "fixer"
        assert "status" in result["history"][0]

    def test_fixer_handles_empty_repo(self, tmp_path):
        repo = tmp_path / "empty_repo"
        repo.mkdir()

        state = {
            "repo_path": str(repo),
            "bug_report": "Some error",
            "iteration_count": 0,
            "history": [],
        }

        result = fixer_node(state)

        assert isinstance(result, dict)
        assert "iteration_count" in result
        assert "history" in result
        assert result["history"][0]["status"] == "no_files"