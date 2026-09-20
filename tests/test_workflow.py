# pyrefly: ignore [missing-import]
import pytest


class TestWorkflow:

    def test_graph_compiles(self):
        """Test that the LangGraph workflow compiles without error."""
        from main import build_graph

        app = build_graph()

        # Verify the compiled graph has expected structure
        assert app is not None
        nodes = app.nodes
        assert "planner" in nodes
        assert "coder" in nodes
        assert "fixer" in nodes
        assert "verifier" in nodes
        assert "reviewer" in nodes
        assert "git_approval" in nodes

    def test_full_agent_workflow_pipeline(self, base_state):
        """Test end-to-end execution of agent nodes across the state pipeline."""
        from autocoder.agents.coder import coder_node
        from autocoder.agents.planner import planner_node
        from autocoder.agents.reviewer import reviewer_node
        from autocoder.agents.verifier import verifier_node

        # 1. Planner Step
        plan_output = planner_node(base_state)
        assert isinstance(plan_output, dict)

        # 2. Coder Step
        state_after_planner = {**base_state, **plan_output}
        coder_output = coder_node(state_after_planner)
        assert isinstance(coder_output, dict)

        # 3. Reviewer Step
        state_after_coder = {**state_after_planner, **coder_output}
        reviewer_output = reviewer_node(state_after_coder)
        assert isinstance(reviewer_output, dict)

        # 4. Verifier Step
        state_after_reviewer = {**state_after_coder, **reviewer_output}
        verifier_output = verifier_node(state_after_reviewer)
        assert isinstance(verifier_output, dict)