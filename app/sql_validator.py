"""Read-only SQL validator.

Rejects anything that is not a single SELECT/WITH statement and blocks every
write/DDL/admin keyword plus references to non-warehouse schemas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sqlparse

FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "truncate", "create",
    "copy", "grant", "revoke", "vacuum", "analyze", "call", "execute",
    "merge", "reindex", "lock", "do", "comment", "set",
}

FORBIDDEN_SCHEMAS = {"app", "pg_catalog", "information_schema", "pg_toast"}

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SCHEMA_REF_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\.", re.IGNORECASE)


@dataclass
class ValidationResult:
    valid: bool
    reason: str | None = None
    statement_kind: str | None = None
    has_limit: bool = False

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "statement_kind": self.statement_kind,
            "has_limit": self.has_limit,
        }


def _strip_comments(sql: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    no_line = re.sub(r"--[^\n]*", " ", no_block)
    return no_line


def validate_sql(sql: str) -> ValidationResult:
    if not sql or not sql.strip():
        return ValidationResult(False, "Empty SQL.")

    raw = sql.strip().rstrip(";").strip()

    if "--" in sql or "/*" in sql or "*/" in sql:
        return ValidationResult(False, "SQL comments are not allowed.")

    if ";" in raw:
        return ValidationResult(False, "Multiple SQL statements are not allowed.")

    cleaned = _strip_comments(raw).lower()
    first_token_match = _WORD_RE.search(cleaned)
    if not first_token_match:
        return ValidationResult(False, "Could not identify SQL statement.")
    first_token = first_token_match.group(0)

    if first_token not in {"select", "with"}:
        return ValidationResult(False, f"Only SELECT/WITH queries are allowed (got '{first_token.upper()}').")

    tokens = set(_WORD_RE.findall(cleaned))
    bad = tokens & FORBIDDEN_KEYWORDS
    if bad:
        return ValidationResult(False, f"Forbidden keyword detected: {', '.join(sorted(bad)).upper()}")

    for schema in _SCHEMA_REF_RE.findall(cleaned):
        if schema.lower() in FORBIDDEN_SCHEMAS:
            return ValidationResult(False, f"Access to schema '{schema}' is not allowed.")

    try:
        parsed = sqlparse.parse(raw)
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(False, f"SQL could not be parsed: {exc}")

    if len(parsed) != 1:
        return ValidationResult(False, "Exactly one SQL statement is required.")

    statement_type = parsed[0].get_type()
    if statement_type not in {"SELECT", "UNKNOWN"}:  # 'WITH' shows as UNKNOWN
        return ValidationResult(False, f"Statement type '{statement_type}' is not allowed.")

    has_limit = re.search(r"\blimit\s+\d+", cleaned) is not None
    return ValidationResult(True, None, "SELECT", has_limit)


def enforce_limit(sql: str, limit: int) -> str:
    """Append a LIMIT clause if the statement does not already have one."""
    stripped = sql.strip().rstrip(";").rstrip()
    if re.search(r"\blimit\s+\d+\s*$", stripped, re.IGNORECASE):
        return stripped
    return f"{stripped}\nLIMIT {limit}"
