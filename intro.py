"""AFB desktop UI launcher. Run with: python3 intro.py"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from afb_immunefi.ui import main  # noqa: E402

if __name__ == "__main__":
    main()
