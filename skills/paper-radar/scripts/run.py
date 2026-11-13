"""Run the bundled Paper Radar CLI without pip or network installation."""

from pathlib import Path
import sys

skill_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(skill_root / "vendor"))

from paper_radar.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
