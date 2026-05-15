"""Dump the warehouse + app schemas to a versioned file you can commit.

Produces two artifacts in `backend/db_dump/`:

  retail_dw.dump      - PostgreSQL custom (compressed) format. Restore with
                        `pg_restore` (fastest, supports parallel restore).
  retail_dw.sql.gz    - Plain SQL, gzip-compressed. Inspectable, restorable
                        with `psql` directly. Easier for code review.

Both contain the `retail_dw` schema (warehouse) and the `app` schema
(users, audit log structure — but `--exclude-table-data app.*` is applied
so we DO NOT export user accounts or audit history).

Usage:
    python scripts/dump_db.py
"""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402

PG_DUMP_CANDIDATES = [
    r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe",
    r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
    r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
    "pg_dump",
]


def find_pg_dump() -> str:
    for c in PG_DUMP_CANDIDATES:
        if c == "pg_dump" or Path(c).exists():
            try:
                subprocess.run([c, "--version"], check=True, capture_output=True)
                return c
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
    raise RuntimeError("pg_dump not found. Install PostgreSQL client tools or edit PG_DUMP_CANDIDATES.")


def main() -> int:
    s = get_settings()
    out_dir = ROOT / "db_dump"
    out_dir.mkdir(exist_ok=True)
    custom = out_dir / "retail_dw.dump"
    plain = out_dir / "retail_dw.sql"
    plain_gz = out_dir / "retail_dw.sql.gz"

    pg_dump = find_pg_dump()
    env = os.environ.copy()
    env["PGPASSWORD"] = s.PG_APP_PASSWORD

    base_args = [
        pg_dump,
        "-h", s.PG_HOST, "-p", str(s.PG_PORT),
        "-U", s.PG_APP_USER, "-d", s.PG_DB,
        "--schema=retail_dw", "--schema=app",
        # Exclude PII/audit data — only the structure of the app schema is exported.
        "--exclude-table-data=app.users",
        "--exclude-table-data=app.audit_log",
        "--no-owner", "--no-privileges",
    ]

    print(f"[1/2] Writing custom dump  -> {custom}")
    subprocess.run(
        base_args + ["-Fc", "-Z", "9", "-f", str(custom)],
        check=True, env=env,
    )
    print(f"      size = {custom.stat().st_size / (1024*1024):.1f} MB")

    print(f"[2/2] Writing plain SQL    -> {plain_gz}")
    subprocess.run(
        base_args + ["-Fp", "-f", str(plain)],
        check=True, env=env,
    )
    with plain.open("rb") as src, gzip.open(plain_gz, "wb", compresslevel=9) as dst:
        shutil.copyfileobj(src, dst)
    plain.unlink()
    print(f"      size = {plain_gz.stat().st_size / (1024*1024):.1f} MB")

    print("\nDump complete. Commit `backend/db_dump/` to your repo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
