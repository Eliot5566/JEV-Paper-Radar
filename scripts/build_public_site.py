"""Rebuild published feeds from committed decisions and include the static showcase.

No feed fetching, model creation, notifications, feedback harvesting or API calls.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from paper_radar.cli import cmd_directory
from paper_radar.config import load_config
from paper_radar.pipeline import rebuild_site
from paper_radar.store import Store


def build(root: Path) -> dict:
    root = root.resolve()
    site = root / "site"
    main = load_config(root / "radar.toml")
    main.base_dir = root
    main.output.site_dir = "site/mine"
    counts = {"mine": len(rebuild_site(main, Store(main.data_path)))}
    configs = [root / "radar.public.toml", *sorted((root / "radars").glob("*.toml"))]
    for path in configs:
        config = load_config(path)
        config.base_dir = root
        if not config.site_path.resolve().is_relative_to(site):
            raise ValueError(f"public output must stay inside site/: {path.name}")
        counts[path.name] = len(rebuild_site(config, Store(config.data_path)))
    for out, base in [(site / "public/index.html", "."), (site / "index.html", "./public")]:
        cmd_directory(argparse.Namespace(configs=[str(p) for p in configs], base_dir=str(root), out=str(out), base=base))
    shutil.copytree(root / "showcase", site / "try", dirs_exist_ok=True)
    (site / ".nojekyll").touch()
    return counts


if __name__ == "__main__":
    import json
    print(json.dumps(build(ROOT)))
