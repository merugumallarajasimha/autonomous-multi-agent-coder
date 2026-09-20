import pytest
from autocoder.agents.verifier import verifier_node


class TestVerifierNode:
    def test_verifier_returns_expected_keys(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        # Create a simple test file that will pass
        test_file = repo / "test_sample.py"
        test_file.write_text("def test_true():\n    assert True\n")

        state = {
            "repo_path": str(repo),
            "written_files": ["test_sample.py"],
            "history": [],
        }

        result = verifier_node(state)

        # Assert structure - should not raise
        assert isinstance(result, dict)
        assert "test_passed" in result
        assert isinstance(result["test_passed"], bool)
        assert "test_logs" in result
        assert isinstance(result["test_logs"], str)
        assert "history" in result
        assert isinstance(result["history"], list)
        assert len(result["history"]) == 1
        assert result["history"][0]["agent"] == "verifier"
        assert "passed" in result["history"][0]
        assert "logs" in result["history"][0]

    def test_verifier_handles_no_test_files(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        # Only non-test files
        (repo / "module.py").write_text("def foo():\n    return 42\n")

        state = {
            "repo_path": str(repo),
            "written_files": ["module.py"],
            "history": [],
        }

        result = verifier_node(state)

        assert isinstance(result, dict)
        assert "test_passed" in result
        assert "test_logs" in result
        assert "history" in result