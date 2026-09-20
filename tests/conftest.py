import os
import sys
from pathlib import Path

# Ensure project root is in Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import MagicMock, patch

# 1. Enforce dummy API key during testing to prevent accidental real calls
@pytest.fixture(autouse=True)
def mock_env_setup():
    os.environ["OPENAI_API_KEY"] = "addyourkey"
    os.environ["GOOGLE_API_KEY"] = "addyourkey"


# 2. Automatically mock all LLM invocations across every test suite
@pytest.fixture(autouse=True)
def mock_llm_calls():
    """Globally mocks LLM calls so pytest runs instantly without network overhead."""
    mock_response = MagicMock()
    mock_response.content = "Mocked LLM response for testing"
    
    # Patch LangChain / OpenAI BaseChatModel or invoke methods
    with patch("langchain_core.language_models.chat_models.BaseChatModel.invoke", return_value=mock_response), \
         patch("langchain_core.language_models.chat_models.BaseChatModel.ainvoke", return_value=mock_response):
        yield mock_response


# 3. Shared state fixture for agent nodes
@pytest.fixture
def base_state(tmp_path):
    """Provides a fresh temporary repository structure and initial state for each test."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def hello():\n    return 'world'\n")
    
    return {
        "repo_path": str(repo),
        "user_request": "Refactor hello function",
        "plan": ["Update main.py"],
        "written_files": ["main.py"],
        "history": [],
    }