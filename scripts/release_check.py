#!/usr/bin/env python3
"""Check a release tag and write its release notes.

Used by .github/workflows/release.yml, and runnable by hand before tagging:

  scripts/release_check.py v0.5.0 --notes notes.md

Fails unless the tag looks like ``vX.Y.Z`` (``-rc1`` style suffixes mark a pre-release), the version in
``custom_components/ring_keypad_gen1/manifest.json`` is the same, and CHANGELOG.md has a ``## [X.Y.Z]``
section. That section becomes the GitHub release text, which HACS shows when offering the update.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r"^v(\d+\.\d+\.\d+)(-[0-9A-Za-z.]+)?$")


def manifest_version(root: Path = ROOT) -> str:
    return json.loads((root / "custom_components" / "ring_keypad_gen1" / "manifest.json").read_text())["version"]


def changelog_section(changelog: str, version: str) -> str | None:
    """The text under ``## [version]`` up to the next ``## `` heading, or None if there is no such heading."""
    lines = changelog.splitlines()
    start = next((i for i, line in enumerate(lines) if re.match(rf"^## \[{re.escape(version)}\]", line)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start + 1:end]).strip()


def check(tag: str, root: Path = ROOT) -> tuple[str, bool, str]:
    """Return ``(version, is_prerelease, notes)`` for a valid tag, or raise ``SystemExit`` with the reason."""
    match = TAG.match(tag)
    if not match:
        raise SystemExit(f"'{tag}' is not a release tag: expected vX.Y.Z, optionally with a -suffix")
    version, suffix = match.group(1), match.group(2)
    manifest = manifest_version(root)
    if manifest != version + (suffix or ""):
        raise SystemExit(f"tag {tag} does not match manifest.json version {manifest}: bump the manifest first")
    changelog = root / "CHANGELOG.md"
    notes = changelog_section(changelog.read_text(), version) if changelog.exists() else None
    if not notes:
        raise SystemExit(f"CHANGELOG.md has no filled-in '## [{version}]' section")
    return version, bool(suffix), notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tag", help="the release tag, e.g. v0.5.0")
    ap.add_argument("--notes", type=Path, help="write the release notes here")
    args = ap.parse_args()
    version, prerelease, notes = check(args.tag)
    if args.notes:
        args.notes.write_text(notes + "\n")
    print(f"{args.tag}: manifest and changelog agree ({'pre-release' if prerelease else 'release'} {version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
