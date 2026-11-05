import sys
from pathlib import Path

# the scripts import each other as top-level modules (e.g. `from report import Report`)
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
