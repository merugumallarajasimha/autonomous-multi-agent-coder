import pytest
from unittest.mock import patch, MagicMock
from autocoder.agents.reviewer import reviewer_node


class TestReviewerNode:
    @patch("autocoder.agents.reviewer.ChatOllama")
    def test_reviewer_returns_expected_keys(self, mock_chatollama, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        # Create a non-test Python file to review
        (repo / "module.py").write_text("def add(a, b):\n    return a + b\n")

        # Mock ChatOllama
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_llm
        mock_llm.invoke.return_value = MagicMock(
            findings=[]
        )
        mock_chatollama.return_value = mock_llm

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
        assert "findings_count" in result["history"][0]

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