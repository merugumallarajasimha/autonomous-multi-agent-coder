import pytest
from unittest.mock import patch, MagicMock
from autocoder.agents.coder import coder_node


class TestCoderNode:
    @patch("autocoder.agents.coder.ChatOllama")
    def test_coder_returns_expected_keys(self, mock_chatollama, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        # Add a simple existing file
        (repo / "existing.py").write_text("def hello():\n    return 'world'\n")

        # Mock ChatOllama
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_llm
        mock_llm.invoke.return_value = MagicMock(
            files=[
                MagicMock(filepath="calculator.py", content="def add(a, b):\n    return a + b\n"),
                MagicMock(filepath="test_calculator.py", content="def test_add():\n    assert add(1, 2) == 3\n"),
            ]
        )
        mock_chatollama.return_value = mock_llm

        state = {
            "repo_path": str(repo),
            "plan": ["Create a calculator module", "Add tests"],
            "task": "Create a calculator module with add/subtract",
            "test_logs": "",
            "test_passed": True,
            "iteration_count": 0,
            "history": [],
        }

        result = coder_node(state)

        # Assert structure - should not raise
        assert isinstance(result, dict)
        assert "iteration_count" in result
        assert isinstance(result["iteration_count"], int)
        assert result["iteration_count"] == 1
        assert "written_files" in result
        assert isinstance(result["written_files"], list)
        assert "history" in result
        assert isinstance(result["history"], list)
        assert len(result["history"]) == 1
        assert result["history"][0]["agent"] == "coder"
        assert "files" in result["history"][0]

    @patch("autocoder.agents.coder.ChatOllama")
    def test_coder_handles_empty_plan(self, mock_chatollama, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_llm
        mock_llm.invoke.return_value = MagicMock(
            files=[
                MagicMock(filepath="simple.py", content="print('hello')\n"),
            ]
        )
        mock_chatollama.return_value = mock_llm

        state = {
            "repo_path": str(repo),
            "plan": [],
            "task": "Simple task",
            "test_logs": "",
            "test_passed": True,
            "iteration_count": 0,
            "history": [],
        }

        result = coder_node(state)

        assert isinstance(result, dict)
        assert "iteration_count" in result
        assert "written_files" in result
        assert "history" in result