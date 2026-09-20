import pytest
from autocoder.agents.coder import coder_node


class TestCoderNode:
    def test_coder_returns_expected_keys(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        # Add a simple existing file
        (repo / "existing.py").write_text("def hello():\n    return 'world'\n")

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

    def test_coder_handles_empty_plan(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()

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