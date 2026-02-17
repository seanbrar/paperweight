"""Database connection helpers for paperweight."""

from contextlib import contextmanager
from typing import Any, Dict, Generator


class DatabaseConnectionError(RuntimeError):
    """Raised when a configured database is unreachable."""


def is_db_enabled(config: Dict[str, Any]) -> bool:
    """Check if database persistence is enabled in configuration."""
    return bool(config.get("db", {}).get("enabled"))


@contextmanager
def connect_db(db_config: Dict[str, Any], autocommit: bool = False) -> Generator:
    """Create a database connection.

    Args:
        db_config: Database configuration dictionary.
        autocommit: If True, each statement commits immediately.
                   If False (default), use explicit transactions.

    Yields:
        A psycopg connection object.
    """
    import psycopg

    conn = psycopg.connect(
        host=db_config["host"],
        port=db_config["port"],
        dbname=db_config["database"],
        user=db_config["user"],
        password=db_config["password"],
        sslmode=db_config.get("sslmode", "prefer"),
        autocommit=autocommit,
    )
    try:
        yield conn
    finally:
        conn.close()
