"""PostgreSQL connection helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection


@contextmanager
def postgres_connection(dsn: str) -> Iterator[Connection]:
    with psycopg.connect(dsn) as conn:
        yield conn
