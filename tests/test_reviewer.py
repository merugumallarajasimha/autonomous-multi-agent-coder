import pytest
from autocoder.agents.reviewer import reviewer_node


class TestReviewerNode:
    def test_reviewer_returns_expected_keys(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        # Create a non-test Python file to review
        (repo / "module.py").write_text("def add(a, b):\n    return a + b\n")

        state = {
            "repo_path": str(repo),
            "history": [],
        }

        result = reviewer_node(state)

        # Assert structure - should not raise
        assert isinstance(result, dict)
        assert "is_refactored" in result
        assert isinstance(result["is_refactored"], bool)
        assert result["is_refactored"] is True
        assert "history" in result
        assert isinstance(result["history"], list)
        assert len(result["history"]) == 1
        assert result["history"][0]["agent"] == "reviewer"
        assert "file" in result["history"][0]

    def test_reviewer_handles_no_python_files(self, tmp_path):
        repo = tmp_path / "empty_repo"
        repo.mkdir()
        # Only test files - reviewer skips them
        (repo / "test_module.py").write_text("def test_foo():\n    assert True\n")

        state = {
            "repo_path": str(repo),
            "history": [],
        }

        result = reviewer_node(state)

        assert isinstance(result, dict)
        assert "is_refactored" in result
        assert result["is_refactored"] is True
        assert "history" in result
        assert result["history"][0]["status"] == "skipped"