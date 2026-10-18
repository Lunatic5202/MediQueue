#!/usr/bin/env python3
"""Audit a generic training CSV without printing patient identifiers or values."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from mediqueue.training.dataset_quality import audit_generic_csv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="generic long-format training CSV")
    parser.add_argument("--output", type=Path, help="optional JSON report destination")
    args = parser.parse_args()

    try:
        report = audit_generic_csv(args.input)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"error: unable to audit input ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        try:
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"error: unable to write report ({type(exc).__name__}): {exc}", file=sys.stderr)
            return 2
    else:
        print(rendered, end="")

    return 1 if report["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
