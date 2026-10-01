#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import pathlib
import re
import tomllib

try:
    import yaml
except ImportError:
    yaml = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".toml", ".yml", ".yaml", ".txt",
    ".sh", ".ps1", ".cmd", ".ini", ".cfg",
}
CONFLICT_RE = re.compile(r"(?m)^(<<<<<<<|=======|>>>>>>>)")


def fail(path: pathlib.Path, message: str) -> None:
    ERRORS.append(str(path.relative_to(ROOT)) + ": " + message)


def text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", ".venv", "venv", "dist", "build", "__pycache__"} for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"LICENSE"}:
            yield path


tracked = list(text_files())
for path in tracked:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail(path, "invalid UTF-8: " + str(exc))
        continue

    controls = sorted({byte for byte in raw if byte < 9 or 13 < byte < 32})
    if controls:
        fail(path, "unexpected control bytes: " + repr(controls))

    match = CONFLICT_RE.search(text)
    if match:
        fail(path, "unresolved merge-conflict marker " + match.group(1))

    try:
        if path.suffix == ".py":
            ast.parse(text, filename=str(path))
        elif path.suffix == ".json":
            json.loads(text)
        elif path.suffix == ".toml":
            tomllib.loads(text)
        elif path.suffix in {".yml", ".yaml"} and yaml is not None:
            yaml.safe_load(text)
    except Exception as exc:
        fail(path, "parse failure: " + str(exc))

link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
for path in (item for item in tracked if item.suffix == ".md"):
    text = path.read_text(encoding="utf-8")
    for target in link_pattern.findall(text):
        target = target.strip()
        if (
            not target
            or target.startswith("#")
            or "://" in target
            or target.startswith("mailto:")
        ):
            continue
        relative = target.split("#", 1)[0]
        if relative and not (path.parent / relative).resolve().exists():
            fail(path, "broken local Markdown link: " + target)

pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
package_version = str(pyproject["project"]["version"])
version_text = (ROOT / "src/jervis/version.py").read_text(encoding="utf-8")
bootstrap_text = (ROOT / "bootstrap.py").read_text(encoding="utf-8")
version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', version_text)
if not version_match:
    ERRORS.append("source version could not be parsed")
else:
    versions = {package_version, version_match.group(1)}
    if len(versions) != 1:
        ERRORS.append("version mismatch: " + repr(sorted(versions)))

if "def source_version(" not in bootstrap_text:
    ERRORS.append("bootstrap must derive its patch version from packaged source")

wiki_dir = ROOT / "docs" / "wiki"
if wiki_dir.exists():
    wiki_pages = list(wiki_dir.glob("*.md"))
    if len(wiki_pages) < 350:
        ERRORS.append("docs/wiki contains only " + str(len(wiki_pages)) + " pages")

if ERRORS:
    print("\n".join(ERRORS))
    raise SystemExit(1)

print("repository verification PASS: " + str(len(tracked)) + " text files")
