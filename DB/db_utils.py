"""
Generic SQL Server helpers (pyodbc). Connection details come from config["db"],
whose values are resolved from environment variables — never hardcode them.
"""
from typing import Any, Dict, List, Optional, Sequence

import pyodbc


def get_sql_driver() -> str:
    drivers = pyodbc.drivers()
    for d in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"):
        if d in drivers:
            return d
    raise RuntimeError(f"No SQL Server ODBC driver found: {drivers}")


def create_connection(db_cfg: dict) -> pyodbc.Connection:
    missing = [k for k in ("server", "uid", "pwd") if not db_cfg.get(k)]
    if missing:
        raise ValueError(f"DB config missing {missing} — set DB_* environment variables (see .env.example)")

    driver = db_cfg.get("driver") or get_sql_driver()
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={db_cfg['server']};"
        + (f"DATABASE={db_cfg['database']};" if db_cfg.get("database") else "")
        + f"UID={db_cfg['uid']};"
        f"PWD={db_cfg['pwd']};"
        f"Encrypt={db_cfg.get('encrypt', 'yes')};"
        f"TrustServerCertificate={db_cfg.get('trust_server_certificate', 'no')};"
        f"Connection Timeout={db_cfg.get('timeout', 30)};"
    )
    return pyodbc.connect(conn_str)


def fetch_all(conn: pyodbc.Connection, query: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
    """Run a parameterised SELECT and return rows as a list of dicts."""
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or [])
        if cursor.description is None:
            return []
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()


def fetch_one(conn: pyodbc.Connection, query: str, params: Optional[Sequence[Any]] = None) -> Optional[Dict[str, Any]]:
    rows = fetch_all(conn, query, params)
    return rows[0] if rows else None


def execute(conn: pyodbc.Connection, query: str, params: Optional[Sequence[Any]] = None, commit: bool = True) -> int:
    """Run an INSERT/UPDATE/DELETE; returns affected row count."""
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or [])
        if commit:
            conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
