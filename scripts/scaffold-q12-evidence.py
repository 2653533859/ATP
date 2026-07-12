#!/usr/bin/env python3
"""Create Q12 external evidence drafts from the frozen templates."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _require_date(value: str, label: str) -> str:
    if not DATE_RE.fullmatch(value):
        raise ValueError(f"{label} must use YYYY-MM-DD, got {value!r}")
    return value


def _write_new_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def scaffold_evidence(
    repo_root: Path,
    start_date: str,
    end_date: str,
    android_date: str,
    *,
    force: bool = False,
) -> tuple[Path, Path, Path]:
    start_date = _require_date(start_date, "start date")
    end_date = _require_date(end_date, "end date")
    android_date = _require_date(android_date, "android date")

    docs_dir = repo_root / "docs"
    templates_dir = docs_dir / "templates"
    slo_path = docs_dir / f"slo-history-{start_date}-{end_date}.md"
    android_path = docs_dir / f"android-device-rehearsal-{android_date}.md"
    acceptance_path = docs_dir / "q12-acceptance-summary.md"

    slo = (templates_dir / "slo-history-template.md").read_text(encoding="utf-8")
    slo = slo.replace("> Window: YYYY-MM-DD to YYYY-MM-DD", f"> Window: {start_date} to {end_date}")
    slo = slo.replace("| YYYY-MM-DD |", f"| {start_date} |")

    android = (templates_dir / "android-device-rehearsal-template.md").read_text(encoding="utf-8")
    android = android.replace("> Date: YYYY-MM-DD", f"> Date: {android_date}")

    acceptance = (templates_dir / "q12-acceptance-summary-template.md").read_text(encoding="utf-8")
    acceptance = acceptance.replace("> Date: YYYY-MM-DD", f"> Date: {android_date}")
    acceptance = acceptance.replace("docs/slo-history-<start>-<end>.md", f"docs/{slo_path.name}")
    acceptance = acceptance.replace("docs/android-device-rehearsal-<date>.md", f"docs/{android_path.name}")

    _write_new_file(slo_path, slo, force)
    _write_new_file(android_path, android, force)
    _write_new_file(acceptance_path, acceptance, force)
    return slo_path, android_path, acceptance_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="SLO window start date, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="SLO window end date, YYYY-MM-DD")
    parser.add_argument("--android-date", required=True, help="Android rehearsal date, YYYY-MM-DD")
    parser.add_argument("--repo-root", default=".", type=Path, help="Repository root; defaults to current directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing generated evidence drafts")
    args = parser.parse_args(argv)

    try:
        created = scaffold_evidence(
            args.repo_root,
            args.start,
            args.end,
            args.android_date,
            force=args.force,
        )
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for path in created:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
