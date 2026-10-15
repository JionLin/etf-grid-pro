"""把现有 MySQL 语句改成 SQLite 能执行的形式。MySQL 连接不经过这里。"""
import re
import sqlite3
from typing import Any, Iterable, List, Optional, Sequence, Tuple

_COMMENT = re.compile(r"\s+COMMENT\s+'(?:[^']|'')*'", re.IGNORECASE)
_ENGINE = re.compile(r"\)\s*ENGINE\s*=.*$", re.IGNORECASE | re.DOTALL)
_INSERT_TABLE = re.compile(r"INSERT\s+INTO\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.IGNORECASE)
_DATE_SUB = re.compile(
    r"DATE_SUB\(\s*%s\s*,\s*INTERVAL\s+(\d+)\s+DAY\s*\)",
    re.IGNORECASE,
)
_PROMOTE_LATEST = re.compile(
    r"UPDATE\s+backtest_run\s+SET\s+is_latest\s*=\s*1\s+"
    r"WHERE\s+etf_code\s*=\s*%s\s+AND\s+backtest_days\s*=\s*%s\s+"
    r"AND\s+step_bucket\s*=\s*%s\s+ORDER\s+BY\s+id\s+DESC\s+LIMIT\s+1",
    re.IGNORECASE | re.DOTALL,
)
_BACKFILL_LATEST = re.compile(
    r"UPDATE\s+backtest_run\s+r\s+INNER\s+JOIN\s*\(",
    re.IGNORECASE | re.DOTALL,
)

_CONFLICT_KEYS = {
    "etf_daily_bar": ("etf_code", "trade_date"),
    "etf_instrument": ("etf_code",),
    "etf_sector": ("sector_code",),
    "etf_subsector": ("subsector_code",),
    "grid_fit_cell": ("etf_code", "step_mode", "protocol_version"),
    "backtest_run_payload": ("run_id",),
    "universe_matrix_backtest": ("etf_code", "config_key"),
    "grid_ledger_plan": ("etf_code",),
}


def adapt_ddl(statement: str) -> Tuple[str, List[str]]:
    """CREATE TABLE 转为 SQLite，并把 KEY 拆成建索引语句。"""
    table_match = re.search(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+`?([A-Za-z_][A-Za-z0-9_]*)`?",
        statement,
        re.IGNORECASE,
    )
    if not table_match:
        raise ValueError("无法识别建表语句")
    table = table_match.group(1)
    stripped = _COMMENT.sub("", statement).strip().rstrip(";")
    stripped = _ENGINE.sub(")", stripped)
    open_at = stripped.find("(")
    close_at = stripped.rfind(")")
    parts = _split_commas(stripped[open_at + 1:close_at])
    columns: List[str] = []
    constraints: List[str] = []
    indexes: List[str] = []
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        upper = piece.upper()
        if upper.startswith("PRIMARY KEY"):
            if re.match(r"PRIMARY\s+KEY\s*\(\s*id\s*\)", piece, re.IGNORECASE):
                continue
            constraints.append(piece)
        elif upper.startswith("UNIQUE KEY"):
            cols = piece[piece.find("("):]
            constraints.append(f"UNIQUE {cols}")
        elif upper.startswith("KEY ") or upper.startswith("INDEX "):
            matched = re.match(r"(?:KEY|INDEX)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(\(.*\))", piece, re.IGNORECASE)
            if not matched:
                raise ValueError(f"无法识别索引: {piece}")
            indexes.append(
                f"CREATE INDEX IF NOT EXISTS {matched.group(1)} ON {table} {matched.group(2)}"
            )
        else:
            columns.append(_column_type(piece))
    body = ",\n".join(columns + constraints)
    create_sql = f"CREATE TABLE IF NOT EXISTS {table} (\n{body}\n)"
    return create_sql, indexes


def translate_sql(statement: str) -> str:
    """DML 占位符、upsert、日期函数和两条仅 MySQL 能跑的 UPDATE。"""
    if _BACKFILL_LATEST.search(statement):
        return (
            "UPDATE backtest_run SET is_latest = 1 WHERE id IN ("
            "SELECT MAX(id) FROM backtest_run "
            "GROUP BY etf_code, backtest_days, step_bucket)"
        )
    if _PROMOTE_LATEST.search(statement):
        return (
            "UPDATE backtest_run SET is_latest = 1 WHERE id = ("
            "SELECT id FROM backtest_run "
            "WHERE etf_code = ? AND backtest_days = ? AND step_bucket = ? "
            "ORDER BY id DESC LIMIT 1)"
        )
    statement = _DATE_SUB.sub(r"date(?, '-\1 days')", statement)
    duplicate = re.search(r"ON\s+DUPLICATE\s+KEY\s+UPDATE\s+(.*)$", statement, re.IGNORECASE | re.DOTALL)
    if duplicate:
        table_match = _INSERT_TABLE.search(statement)
        if not table_match:
            raise ValueError("ON DUPLICATE KEY 缺少表名")
        table = table_match.group(1)
        keys = _CONFLICT_KEYS.get(table)
        if not keys:
            raise ValueError(f"没有为 {table} 登记冲突列")
        assignments = re.sub(
            r"VALUES\((\w+)\)",
            r"excluded.\1",
            duplicate.group(1),
            flags=re.IGNORECASE,
        ).strip().rstrip(";")
        head = statement[:duplicate.start()].rstrip()
        statement = (
            f"{head} ON CONFLICT({', '.join(keys)}) DO UPDATE SET {assignments}"
        )
    return statement.replace("%s", "?")


class SqliteCursor:
    """执行前翻译 SQL，结果行用 dict，方便沿用 row['col']。"""

    def __init__(self, cursor: sqlite3.Cursor):
        self._cursor = cursor
        self.rowcount = -1

    def execute(self, statement: str, params: Sequence[Any] = ()):
        adapted = translate_sql(statement)
        self._cursor.execute(adapted, tuple(params))
        self.rowcount = self._cursor.rowcount
        return self

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def executemany(self, statement: str, seq: Iterable[Sequence[Any]]):
        adapted = translate_sql(statement)
        self._cursor.executemany(adapted, [tuple(item) for item in seq])
        self.rowcount = self._cursor.rowcount
        return self

    def fetchone(self) -> Optional[dict]:
        row = self._cursor.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self) -> List[dict]:
        return [dict(row) for row in self._cursor.fetchall()]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._cursor.close()
        return False


class SqliteConnection:
    def __init__(self, raw: sqlite3.Connection):
        self._raw = raw

    def cursor(self, *_args, **_kwargs) -> SqliteCursor:
        return SqliteCursor(self._raw.cursor())

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def connect_sqlite(path) -> SqliteConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA journal_mode=WAL")
    raw.execute("PRAGMA busy_timeout=5000")
    return SqliteConnection(raw)


def _column_type(column: str) -> str:
    rewritten = re.sub(r"\bDOUBLE\b", "REAL", column, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bTINYINT\b", "INTEGER", rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bBIGINT\b", "INTEGER", rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bMEDIUMTEXT\b", "TEXT", rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bVARCHAR\(\d+\)", "TEXT", rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bCHAR\(\d+\)", "TEXT", rewritten, flags=re.IGNORECASE)
    if re.search(r"\bAUTO_INCREMENT\b", rewritten, re.IGNORECASE):
        rewritten = re.sub(r"\s+AUTO_INCREMENT\b", "", rewritten, flags=re.IGNORECASE)
        rewritten = re.sub(
            r"^(\w+)\s+INTEGER\s+NOT\s+NULL",
            r"\1 INTEGER PRIMARY KEY AUTOINCREMENT",
            rewritten,
            count=1,
            flags=re.IGNORECASE,
        )
    return rewritten


def _split_commas(body: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(body):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(body[start:index])
            start = index + 1
    parts.append(body[start:])
    return parts
