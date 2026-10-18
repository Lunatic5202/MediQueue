"""Alembic baseline must match the SQLAlchemy metadata."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_alembic_upgrade_and_no_drift(tmp_path):
    env = {"MEDIQUEUE_DATABASE_URL": f"sqlite:///{tmp_path / 'm.db'}", "PATH": "/usr/bin:/bin"}
    for args in (["upgrade", "head"], ["check"]):
        r = subprocess.run(
            [sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env,
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
