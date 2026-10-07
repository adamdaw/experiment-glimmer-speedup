import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for d in ("scripts", "tools"):
    sys.path.insert(0, str(ROOT / d))
