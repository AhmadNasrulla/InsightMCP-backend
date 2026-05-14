"""Initialize the warehouse: schema + indexes + app tables + dimensions.

Run:
    python scripts/init_db.py            # schema, indexes, dims, app tables
    python scripts/init_db.py --facts    # also load fact tables (slow)
    python scripts/init_db.py --facts --scale 2500000

Requires the database in .env (default `assignment3`) to exist already.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402

SQL_DIR = ROOT / "sql"


def _run_file(conn: psycopg.Connection, path: Path, params: dict[str, str] | None = None) -> None:
    sql_text = path.read_text(encoding="utf-8")
    if params:
        # naive psql-style :var substitution for our seed file
        for k, v in params.items():
            sql_text = sql_text.replace(f":{k}", str(v))
        # drop the \if blocks (we substituted defaults already)
        lines = [ln for ln in sql_text.splitlines() if not ln.strip().startswith("\\")]
        sql_text = "\n".join(lines)
    print(f"  -> {path.name}")
    started = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute(sql_text)
    conn.commit()
    print(f"     done in {time.perf_counter()-started:.1f}s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facts", action="store_true", help="Also seed fact tables.")
    parser.add_argument("--scale", type=int, default=250_000, help="Sales-line rows.")
    parser.add_argument("--inventory-products", type=int, default=200,
                        help="Number of products to snapshot daily (heavy).")
    args = parser.parse_args()

    settings = get_settings()
    print(f"Connecting to {settings.PG_DB}@{settings.PG_HOST}:{settings.PG_PORT} as {settings.PG_APP_USER}")

    with psycopg.connect(settings.app_dsn, autocommit=False) as conn:
        print("[1/4] Creating warehouse schema")
        _run_file(conn, SQL_DIR / "01_schema.sql")
        print("[2/4] Creating indexes")
        _run_file(conn, SQL_DIR / "02_indexes.sql")
        print("[3/4] Seeding dimensions")
        _run_file(conn, SQL_DIR / "03_seed_dimensions.sql")
        print("[4/4] Creating app tables + readonly role")
        _run_file(conn, SQL_DIR / "05_app_tables.sql")

        if args.facts:
            print(f"[+] Seeding facts (sales_rows={args.scale}, inventory_products={args.inventory_products})")
            _run_file(conn, SQL_DIR / "04_seed_facts.sql", {
                "sales_rows": args.scale,
                "inventory_product_limit": args.inventory_products,
            })

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
