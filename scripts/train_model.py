#!/usr/bin/env python3
"""Train and version a MediQueue baseline model.

Examples:
  # General-deterioration proxy on the synthetic corpus (default PoC path)
  python scripts/train_model.py --task deterioration --dataset synthetic --n-patients 600

  # Interpretable logistic-regression baseline
  python scripts/train_model.py --task deterioration --dataset synthetic --kind logreg

  # Labeled generic long-format CSV (see docs/datasets.md)
  python scripts/train_model.py --dataset generic --data-dir /path/to/training.csv

  # Sepsis task on PhysioNet/CinC 2019 (download separately; see docs/datasets.md)
  python scripts/train_model.py --task sepsis --dataset physionet --data-dir /path/to/training_setA
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from mediqueue.training.train import train_model  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["deterioration", "sepsis"], default="deterioration")
    parser.add_argument("--dataset", choices=["synthetic", "physionet", "generic"], default="synthetic")
    parser.add_argument(
        "--data-dir", default=None,
        help="PhysioNet directory or generic labeled long-format CSV file",
    )
    parser.add_argument("--n-patients", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--kind", choices=["lightgbm", "logreg"], default="lightgbm")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument(
        "--target-recall", type=float, default=0.80,
        help="choose the highest validation threshold reaching this recall (0 = F1-optimal)",
    )
    args = parser.parse_args()

    result = train_model(
        task=args.task,
        dataset=args.dataset,
        data_dir=args.data_dir,
        n_patients=args.n_patients,
        seed=args.seed,
        kind=args.kind,
        out_dir=args.out_dir,
        target_recall=args.target_recall or None,
    )
    print(
        json.dumps(
            {
                "version_id": result.version_id,
                "kind": result.kind,
                "task": result.task,
                "artifact_dir": str(result.artifact_dir),
                "dataset_hash": result.dataset_hash,
                "feature_schema_hash": result.feature_schema_hash,
                "metrics": result.metrics,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
