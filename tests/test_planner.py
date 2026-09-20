import pytest
from unittest.mock import patch, MagicMock
from autocoder.agents.planner import planner_node


class TestPlannerNode:
    @patch("autocoder.agents.planner._model_router")
    def test_planner_returns_expected_keys(self, mock_router, tmp_path):
        # Create a minimal repo with one Python file
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "math_ops.py").write_text("def add(a, b):\n    return a + b\n")

        # Mock the model router to return a mock provider
        mock_provider = MagicMock()
        mock_provider.invoke.return_value = {
            "success": True,
            "data": MagicMock(
                steps=["Create multiply function", "Add tests"],
                target_files=["math_ops.py"]
            )
        }
        mock_router.get.return_value = mock_provider

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

    @patch("autocoder.agents.planner._model_router")
    def test_planner_handles_empty_repo(self, mock_router, tmp_path):
        repo = tmp_path / "empty_repo"
        repo.mkdir()

        mock_provider = MagicMock()
        mock_provider.invoke.return_value = {
            "success": True,
            "data": MagicMock(
                steps=["Create new module"],
                target_files=["new_module.py"]
            )
        }
        mock_router.get.return_value = mock_provider

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