"""Build a reproducible, self-contained Claude skill ZIP using only the stdlib."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "paper-radar"


def build(output: Path, source_commit: str = "working-tree") -> dict:
    files = {}
    for path in sorted(SKILL.rglob("*")):
        relative = path.relative_to(SKILL)
        if "vendor" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.is_file() and path.suffix in {".md", ".py", ".json"}:
            files[relative.as_posix()] = path.read_bytes()
    # Validate the same normalized text that is stored in the archive. Windows
    # CRLF otherwise becomes part of the captured name before normalization.
    text = files["SKILL.md"].decode("utf-8").replace("\r\n", "\n")
    name = re.search(r"^name: (.+)$", text, re.M).group(1)
    description = re.search(r"^description: (.+)$", text, re.M).group(1)
    if name != "paper-radar" or not 1 <= len(description) <= 200:
        raise ValueError("skill name/description does not meet Claude upload requirements")
    runtime = ROOT / "paper_radar"
    for path in sorted(runtime.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix in {".py", ".toml", ".xml"}:
            files["vendor/paper_radar/" + path.relative_to(runtime).as_posix()] = path.read_bytes()
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    files["references/claude-starter.toml"] = (ROOT / "profiles/claude-starter.toml").read_bytes()
    for required in ("scripts/run.py", "scripts/chat_report.py", "scripts/retrieve.py", "examples/papers.json",
                     "vendor/paper_radar/cli.py", "vendor/paper_radar/demo/arxiv_demo.xml"):
        if required not in files:
            raise ValueError(f"missing bundled file: {required}")
    # Text normalization makes the archive identical on Windows and Linux.
    files = {name: data.replace(b"\r\n", b"\n") for name, data in files.items()}
    version = re.search(r'__version__\s*=\s*"([^"]+)"', files["vendor/paper_radar/__init__.py"].decode()).group(1)
    manifest = {"skill": name, "skill_bundle_version": "0.2.0", "paper_radar_version": version,
                "source_commit": source_commit, "description_characters": len(description),
                "python": ">=3.11", "external_runtime_dependencies": [],
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files["bundle-manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo("paper-radar/" + name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=9)
    return {"archive": str(output.resolve()), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "files": len(files), "bytes": output.stat().st_size,
            "description_characters": len(description), "source_commit": source_commit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/paper-radar-claude.zip")
    parser.add_argument("--source-commit", default="working-tree")
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.source_commit)))


if __name__ == "__main__":
    main()
