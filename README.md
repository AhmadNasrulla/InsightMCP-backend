# MCP Retail SQL Analyst

An industry-style conversational data analyst over a Kimball-style PostgreSQL retail data warehouse, built end-to-end to the full assignment specification.

- **Backend** — FastAPI + PostgreSQL, JWT email/password auth, semantic-layer-driven text-to-SQL (Gemini), read-only SQL validator, audit log, and a standalone MCP server.
- **Frontend** — Next.js 16 (App Router) + Tailwind v4, with login/register, ask flow, schema browser, and audit history.

Project spec lives in [`project.md`](./project.md).

---

## Architecture at a glance

```
 Next.js (port 3000)
        │  JWT (Bearer)
        ▼
 FastAPI (port 8000)
        │
        ├── /api/auth/{register,login,me}        (bcrypt + JWT)
        ├── /api/schema  /api/semantic           (introspection)
        ├── /api/analyst/ask  /api/analyst/execute
        └── /api/history
              │
              │ semantic layer (YAML) ──► Gemini ──► SQL
              │ SQL validator (SELECT/WITH only, allow-list joins)
              ▼
        PostgreSQL `assignment3`
           ├── retail_dw.*    (warehouse, accessed via read-only role `mcp_readonly`)
           └── app.*          (users, audit_log)

 mcp_server.py  ── separate MCP-protocol entry point exposing the same
                   resources/tools/prompts to any MCP-compatible client.
```

---

## 1. Prerequisites

- PostgreSQL 16+ running locally with database `assignment3` (user `postgres`, password `123` by default — edit `backend/.env` if yours differ).
- Python 3.11+
- Node 20+

---

## 2. Backend setup

The virtualenv lives inside the repo at `backend/.venv` (created during initial setup). Nothing is installed against your system Python.

```bash
cd backend
# Create the venv (one-time)
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
cp .env.example .env              # adjust DB / JWT / Gemini values as needed
```

### Initialize the warehouse (full assignment scale)

```bash
# Schema + indexes + dimensions + app tables + read-only role + facts (2.5M sales lines)
python scripts/init_db.py --facts --scale 2500000 --inventory-products 1000
```

What this loads:

| Table | Rows |
| --- | --- |
| `dim_date` | 1,096 (2024-01-01 → 2026-12-31) |
| `dim_store` | 10 |
| `dim_payment_method` | 5 |
| `dim_promotion` | 50 |
| `dim_customer` | 100,000 |
| `dim_product` | 10,000 (10 categories × 10 subcategories × 100) |
| `fact_sales_line` | **2,500,000** |
| `fact_returns` | ~25,000 (~1% of sales) |
| `fact_inventory_daily_snapshot` | ~10,960,000 (1,000 products × 10 stores × 1,096 days) |

The script is idempotent — re-running truncates and reloads.

You can tune scale for development:
```bash
# Fast dev (≈30s seed)
python scripts/init_db.py --facts --scale 250000 --inventory-products 200
```

### Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

Health check: <http://localhost:8000/api/health>. Interactive docs: <http://localhost:8000/docs>.

### Run the MCP server (optional, for Claude Desktop / Cursor / etc.)

```bash
python mcp_server.py
```

Exposes:
- `retail://schema/overview` and `retail://semantic/model` (resources)
- `profile_table`, `validate_sql_tool`, `run_readonly_query`, `generate_sql_tool`, `explain_result_tool`, `suggest_chart_tool` (tools)
- `analyst_system_prompt` (prompt)

---

## 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>, register an account, and start asking questions.
`NEXT_PUBLIC_API_BASE` defaults to `http://localhost:8000` (configured in `.env.local`).

---

## 4. Dumping & restoring the populated database

This repo includes a ready-to-commit dump of the warehouse so a reviewer can skip the multi-minute seed and restore directly.

### Generate the dump (after seeding)

```bash
cd backend
python scripts/dump_db.py
```

Produces two artifacts in `backend/db_dump/`:

| File | Format | Used with | Notes |
| --- | --- | --- | --- |
| `retail_dw.dump` | PostgreSQL custom (`-Fc`) | `pg_restore` | Fastest, supports parallel restore. |
| `retail_dw.sql.gz` | Plain SQL, gzip-compressed | `psql` | Inspectable. Easier code review. |

Both files contain the **structure of both schemas** (`retail_dw` and `app`) plus the **full warehouse data**. User accounts and audit history (`app.users`, `app.audit_log`) are **excluded by design** — you don't want to ship a teammate's password hashes.

### Restore on another machine

The target database (default `assignment3`) must already exist; create it once with:
```sql
CREATE DATABASE assignment3;
```

Then:
```bash
cd backend
.venv\Scripts\activate
python scripts/restore_db.py                      # auto-picks db_dump/retail_dw.dump
# or
python scripts/restore_db.py --file db_dump/retail_dw.sql.gz
```

The script drops `retail_dw` and `app`, restores from the dump, and re-applies `sql/05_app_tables.sql` so the `mcp_readonly` role and app tables are guaranteed to exist.

### Committing the dump to GitHub

The dump for the full assignment scale (2.5M sales lines + 10.96M inventory rows) is **~131 MB** for each artifact — GitHub's hard limit is 100 MB per file, so you'll need **Git LFS**:

```bash
git lfs install
git lfs track "backend/db_dump/*.dump"
git lfs track "backend/db_dump/*.sql.gz"
git add .gitattributes backend/db_dump/
git commit -m "Add full warehouse dump"
git push
```

Alternative if you don't want LFS: reduce scale until both files are <100 MB (e.g. `--scale 1000000 --inventory-products 300` produces a ~50 MB dump), or skip committing the dump entirely and rely on `python scripts/init_db.py --facts --scale 2500000 --inventory-products 1000` to recreate it.

---

## 5. Key safety guarantees

- **Read-only role.** Analyst SQL runs as `mcp_readonly`, which has `SELECT` only on `retail_dw.*` and no privileges on `app.*` (users / audit log).
- **Validator.** Rejects anything that is not a single `SELECT`/`WITH`; blocks comments, semicolons, DDL/DML keywords, and references to `app`, `pg_catalog`, `information_schema`.
- **Statement timeout.** Every analyst query runs with `SET statement_timeout` (default 10s).
- **Row limit.** `LIMIT` is enforced automatically when missing (default 100, max 1000).
- **Restricted columns.** `email_hash`, `phone_hash`, `password_hash` are flagged restricted in the semantic layer.
- **Audit log.** Every question is persisted with generated SQL, validation outcome, safety status, execution status, row count, latency, and originating user.

---

## 6. Sample demo questions

1. *"What is total net sales by category for 2025?"*
2. *"Top 10 products by revenue this year."*
3. *"Which store has the highest average order value in Punjab?"*
4. *"Show monthly sales trend for Electronics in 2025."*
5. *"Which subcategory has the highest return rate?"*
6. *"Delete low-profit products from the database."* → refused.

---

## 7. Project layout

```
backend/
  app/
    main.py           FastAPI app + lifespan
    config.py         Pydantic settings (.env)
    db.py             psycopg pools (app + read-only)
    security.py       bcrypt + JWT
    deps.py           CurrentUser dependency
    schemas.py        Pydantic request/response models
    semantic.py       Loads semantic_model.yml
    sql_validator.py  Read-only SQL validator
    llm.py            Gemini text-to-SQL + explain + chart heuristics
    analyst.py        Orchestrates ask → validate → execute → audit
    routers/          auth.py, schema.py, analyst.py, history.py
  sql/
    01_schema.sql, 02_indexes.sql, 03_seed_dimensions.sql,
    04_seed_facts.sql, 05_app_tables.sql
  semantic_model.yml
  mcp_server.py
  scripts/
    init_db.py        Bootstrap warehouse + facts
    dump_db.py        Export to backend/db_dump/
    restore_db.py     Restore from backend/db_dump/
  db_dump/            Versioned dumps (committed; see §4)

frontend/
  app/
    layout.tsx, page.tsx
    login/page.tsx, register/page.tsx
    dashboard/{layout,page}.tsx, schema/page.tsx, history/page.tsx
  lib/
    api.ts, auth.tsx
```

---

## 8. Configuration reference

`backend/.env`:

| Key | Default | Purpose |
| --- | --- | --- |
| `PG_HOST` `PG_PORT` `PG_DB` | `localhost` `5432` `assignment3` | PostgreSQL target |
| `PG_APP_USER` `PG_APP_PASSWORD` | `postgres` `123` | Owns warehouse + app schema |
| `PG_RO_USER` `PG_RO_PASSWORD` | `mcp_readonly` `readonly_demo_pw_change_me` | Read-only role (created by `05_app_tables.sql`) |
| `JWT_SECRET` | _change me_ | HS256 signing key |
| `GEMINI_API_KEY` `GEMINI_MODEL` | provided / `gemini-2.0-flash` | Text-to-SQL backend |
| `QUERY_TIMEOUT_SECONDS` `QUERY_DEFAULT_LIMIT` `QUERY_MAX_LIMIT` | `10` `100` `1000` | Governance |

---

## 9. Production hardening checklist

- Rotate `JWT_SECRET` and `PG_RO_PASSWORD`.
- Put FastAPI behind a reverse proxy with TLS.
- Move audit log to a separate database / sink.
- Use a managed secrets store for `GEMINI_API_KEY`.
- Add per-user rate limiting on `/api/analyst/ask`.
- Partition `fact_sales_line` by month for very large workloads.
