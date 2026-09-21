import sys
from pathlib import Path

# Ensure workspace root is in Python path for pytest module resolution
# This allows tests to import modules from workspace/ when running on host
WORKSPACE_ROOT = Path(__file__).parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

# Also add project root for autocoder imports
PROJECT_ROOT = WORKSPACE_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))