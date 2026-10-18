#!/usr/bin/env python3
"""Evaluate a versioned model artifact on an independent corpus.

Writes JSON + Markdown reports under artifacts/reports/. Reports retrospective
model performance only; not a claim of clinical effectiveness.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from mediqueue.training.evaluate import evaluate_artifact, write_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("artifact_dir", help="Path to artifacts/models/<version_id>")
    parser.add_argument("--dataset", choices=["synthetic", "physionet", "generic"], default="synthetic")
    parser.add_argument(
        "--data-dir", default=None,
        help="PhysioNet directory or generic labeled long-format CSV file",
    )
    parser.add_argument("--n-patients", type=int, default=300)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--split", choices=["train", "validation", "test", "all"], default="test")
    args = parser.parse_args()

    report = evaluate_artifact(
        args.artifact_dir,
        dataset=args.dataset,
        data_dir=args.data_dir,
        n_patients=args.n_patients,
        seed=args.seed,
        split=args.split,
    )
    out = write_report(report, ROOT / "artifacts" / "reports")
    print(json.dumps(report, indent=2))
    print(f"\nReports written under {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
