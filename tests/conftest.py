import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent / "app"
sys.path.append(str(project_root))
