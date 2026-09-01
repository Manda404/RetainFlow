"""Read-only PostgreSQL tool for RetainFlow agents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text

from retainflow.config import ChurnModelConfig
from retainflow.data.dataset import sqlalchemy_dsn
from retainflow.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SQLQueryResult:
    """Structured result returned after a controlled SQL execution."""

    dataframe: pd.DataFrame
    sql: str
    row_count: int
    truncated: bool


class SQLTool:
    """Execute safe read-only SQL queries against the RetainFlow PostgreSQL database.

    This tool is deliberately conservative because it will be called by agents.
    It accepts only `SELECT` or `WITH` statements, blocks mutation keywords, and
    wraps the query with a limit when the user forgot to add one.
    """

    _blocked_keywords = {
        "alter",
        "analyze",
        "call",
        "copy",
        "create",
        "delete",
        "drop",
        "execute",
        "grant",
        "insert",
        "merge",
        "refresh",
        "reindex",
        "replace",
        "revoke",
        "truncate",
        "update",
        "vacuum",
    }

    def __init__(self, config: ChurnModelConfig, default_limit: int = 200) -> None:
        self.config = config
        self.default_limit = default_limit
        self.engine = create_engine(sqlalchemy_dsn(config.postgres_dsn))

    def query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> SQLQueryResult:
        """Validate and execute a SQL query, then return a pandas DataFrame."""
        clean_sql = self._normalize_sql(sql)
        self.validate_read_only(clean_sql)
        executed_sql = self._with_limit(clean_sql, limit or self.default_limit)

        logger.info("SQLTool executing read-only query with limit=%s", limit or self.default_limit)
        with self.engine.connect() as conn:
            frame = pd.read_sql_query(text(executed_sql), conn, params=params or {})
        return SQLQueryResult(
            dataframe=frame,
            sql=executed_sql,
            row_count=len(frame),
            truncated=len(frame) >= (limit or self.default_limit),
        )

    def validate_read_only(self, sql: str) -> None:
        """Raise `ValueError` when the query is not allowed for agent execution."""
        lowered = sql.lower()
        first_token = lowered.split(maxsplit=1)[0] if lowered else ""
        if first_token not in {"select", "with"}:
            raise ValueError("SQLTool accepts only SELECT or WITH queries.")

        tokens = set(re.findall(r"\b[a-z_]+\b", lowered))
        blocked = sorted(tokens.intersection(self._blocked_keywords))
        if blocked:
            raise ValueError(f"Unsafe SQL keyword detected: {', '.join(blocked)}")

        # Keep one statement per call; this prevents hidden mutations after SELECT.
        if ";" in sql.rstrip(";"):
            raise ValueError("SQLTool accepts only one SQL statement at a time.")

    def _with_limit(self, sql: str, limit: int) -> str:
        """Wrap SQL with a hard limit while preserving complex SELECT/WITH queries."""
        if re.search(r"\blimit\s+\d+\b", sql, flags=re.IGNORECASE):
            return sql.rstrip(";")
        return f"SELECT * FROM (\n{sql.rstrip(';')}\n) AS retainflow_agent_query\nLIMIT {int(limit)}"

    @staticmethod
    def _normalize_sql(sql: str) -> str:
        """Remove trailing whitespace and final semicolon for stable execution."""
        clean_sql = sql.strip()
        if clean_sql.endswith(";"):
            clean_sql = clean_sql[:-1].strip()
        return clean_sql
