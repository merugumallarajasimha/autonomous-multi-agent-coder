import pytest


class TestWorkflow:
    def test_graph_compiles(self):
        """Test that the LangGraph workflow compiles without error."""
        from main import build_graph

        app = build_graph()

        # Verify the compiled graph has expected structure
        assert app is not None
        # Check nodes exist
        nodes = app.nodes
        assert "planner" in nodes
        assert "coder" in nodes
        assert "fixer" in nodes
        assert "verifier" in nodes
        assert "reviewer" in nodes
        assert "git_approval" in nodes

        # Check entry point
        assert app.get_graph().get_entry_point() == "planner"