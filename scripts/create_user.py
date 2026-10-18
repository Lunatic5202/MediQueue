"""Create a user (use in production, where demo seed users are off).

  python scripts/create_user.py NAME ROLE   # password read from prompt
"""
import getpass
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from mediqueue.db import clinicians, get_engine, init_db, utcnow  # noqa: E402
from mediqueue.security import VALID_ROLES, hash_password  # noqa: E402

name, role = sys.argv[1], sys.argv[2]
if role not in VALID_ROLES:
    sys.exit(f"role must be one of {sorted(VALID_ROLES)}")
pw = getpass.getpass("Password: ")
if len(pw) < 12:
    sys.exit("password must be at least 12 characters")
init_db(get_engine())
salt = secrets.token_hex(16)
with get_engine().begin() as c:
    c.execute(clinicians.insert().values(
        username=name, role=role, salt=salt,
        password_hash=hash_password(pw, salt), created_at=utcnow()))
print("created", name, role)
