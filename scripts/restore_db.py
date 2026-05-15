"""Restore a previously-dumped warehouse into the target database.

Usage:
    python scripts/restore_db.py                       # auto-pick .dump if present
    python scripts/restore_db.py --file db_dump/retail_dw.dump
    python scripts/restore_db.py --file db_dump/retail_dw.sql.gz

The target DB (from .env, default `assignment3`) must already exist.
This DROPs and recreates the `retail_dw` and `app` schemas, so existing
data in those schemas will be replaced.
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402

PG_BIN_CANDIDATES = [
    r"C:\Program Files\PostgreSQL\18\bin",
    r"C:\Program Files\PostgreSQL\17\bin",
    r"C:\Program Files\PostgreSQL\16\bin",
    "",
]


def find_tool(name: str) -> str:
    for base in PG_BIN_CANDIDATES:
        exe = str(Path(base) / f"{name}.exe") if base else name
        try:
            subprocess.run([exe, "--version"], check=True, capture_output=True)
            return exe
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    raise RuntimeError(f"{name} not found.")


def pick_default_dump(dump_dir: Path) -> Path:
    for name in ("retail_dw.dump", "retail_dw.sql.gz", "retail_dw.sql"):
        cand = dump_dir / name
        if cand.exists():
            return cand
    raise FileNotFoundError(f"No dump file found in {dump_dir}.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Path to .dump / .sql / .sql.gz file.")
    args = parser.parse_args()

    s = get_settings()
    dump_dir = ROOT / "db_dump"
    path = Path(args.file) if args.file else pick_default_dump(dump_dir)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["PGPASSWORD"] = s.PG_APP_PASSWORD

    psql = find_tool("psql")
    print(f"Restoring into {s.PG_DB}@{s.PG_HOST}:{s.PG_PORT} from {path.name}")

    # Drop existing schemas first.
    subprocess.run(
        [psql, "-h", s.PG_HOST, "-p", str(s.PG_PORT),
         "-U", s.PG_APP_USER, "-d", s.PG_DB,
         "-v", "ON_ERROR_STOP=1",
         "-c", "DROP SCHEMA IF EXISTS retail_dw CASCADE; DROP SCHEMA IF EXISTS app CASCADE;"],
        check=True, env=env,
    )

    if path.suffix == ".dump":
        pg_restore = find_tool("pg_restore")
        subprocess.run(
            [pg_restore, "-h", s.PG_HOST, "-p", str(s.PG_PORT),
             "-U", s.PG_APP_USER, "-d", s.PG_DB,
             "--no-owner", "--no-privileges",
             "-j", "4", str(path)],
            check=True, env=env,
        )
    else:
        if path.suffix == ".gz":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as tmp:
                tmp_path = Path(tmp.name)
            with gzip.open(path, "rb") as src, tmp_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            sql_file = tmp_path
        else:
            sql_file = path
        try:
            subprocess.run(
                [psql, "-h", s.PG_HOST, "-p", str(s.PG_PORT),
                 "-U", s.PG_APP_USER, "-d", s.PG_DB,
                 "-v", "ON_ERROR_STOP=1", "-f", str(sql_file)],
                check=True, env=env,
            )
        finally:
            if path.suffix == ".gz":
                sql_file.unlink(missing_ok=True)

    # Ensure app schema and read-only role exist (they're in the dump, but the
    # role is cluster-level and may not have been included).
    app_tables_sql = ROOT / "sql" / "05_app_tables.sql"
    subprocess.run(
        [psql, "-h", s.PG_HOST, "-p", str(s.PG_PORT),
         "-U", s.PG_APP_USER, "-d", s.PG_DB,
         "-v", "ON_ERROR_STOP=1", "-f", str(app_tables_sql)],
        check=True, env=env,
    )

    print("Restore complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
