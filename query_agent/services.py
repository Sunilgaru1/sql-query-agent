"""
Text-to-SQL agent runtime.

Implements:
- live MySQL schema introspection
- Groq (Llama 3.3) SQL generation
- sqlparse AST security gateway
- Generate → Execute → Observe → Repair self-correction loop
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator

import pymysql
import sqlparse
from django.conf import settings
from groq import Groq
from pymysql.cursors import DictCursor
from sqlparse.sql import Identifier, IdentifierList, Parenthesis, Statement, TokenList
from sqlparse.tokens import DDL, DML, Keyword, Comment

from query_agent.exceptions import (
    ConfigurationError,
    QueryRepairExhaustedError,
    UnsafeSQLError,
)

FORBIDDEN_KEYWORDS = {
    "ALTER",
    "ANALYZE",
    "CALL",
    "CREATE",
    "DELETE",
    "DROP",
    "EXECUTE",
    "FLUSH",
    "GRANT",
    "HANDLER",
    "INSERT",
    "INTO",
    "KILL",
    "LOAD",
    "LOCK",
    "OPTIMIZE",
    "PREPARE",
    "PURGE",
    "RENAME",
    "REPLACE",
    "RESET",
    "REVOKE",
    "SET",
    "SHOW",
    "SHUTDOWN",
    "TRUNCATE",
    "UNLOCK",
    "UPDATE",
    "USE",
    "XA",
}

ALLOWED_STATEMENT_TYPES = {"SELECT"}
SQL_FENCE_RE = re.compile(r"^```(?:sql)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


class TextToSQLAgent:
    def __init__(self) -> None:
        self.max_retries = settings.SQL_AGENT_MAX_RETRIES
        self.query_timeout = settings.SQL_AGENT_QUERY_TIMEOUT
        self.max_rows = settings.SQL_AGENT_MAX_ROWS
        self.model = settings.GROQ_MODEL
        self._client: Groq | None = None

    @property
    def groq_client(self) -> Groq:
        if self._client is None:
            api_key = settings.GROQ_API_KEY
            if not api_key:
                raise ConfigurationError("GROQ_API_KEY is not configured.")
            self._client = Groq(api_key=api_key)
        return self._client

    def run(self, question: str) -> dict[str, Any]:
        question = (question or "").strip()
        if not question:
            raise ValueError("A natural-language question is required.")

        schema = self.introspect_schema()
        repairs: list[dict[str, Any]] = []
        last_sql = ""
        last_error = ""

        for attempt in range(1, self.max_retries + 2):
            sql = self.generate_sql(
                question=question,
                schema=schema,
                previous_sql=last_sql,
                error_trace=last_error,
                attempt=attempt,
            )
            last_sql = sql

            try:
                self.validate_sql(sql)
                rows, columns = self.execute_sql(sql)
            except UnsafeSQLError as exc:
                last_error = str(exc)
                repairs.append(
                    {
                        "attempt": attempt,
                        "sql": sql,
                        "error": last_error,
                        "stage": "validation",
                    }
                )
                continue
            except pymysql.Error as exc:
                last_error = f"{exc.__class__.__name__}: {exc}"
                repairs.append(
                    {
                        "attempt": attempt,
                        "sql": sql,
                        "error": last_error,
                        "stage": "execution",
                    }
                )
                continue

            return {
                "question": question,
                "sql": sql,
                "attempts": attempt,
                "repaired": attempt > 1,
                "repairs": repairs,
                "row_count": len(rows),
                "columns": columns,
                "data": rows,
            }

        raise QueryRepairExhaustedError(
            "The agent could not produce a valid, executable query "
            f"after {self.max_retries + 1} attempts. Last error: {last_error}"
        )

    def introspect_schema(self) -> str:
        """Extract live table blueprints from INFORMATION_SCHEMA."""
        db_name = _require_target_db()["name"]
        with _readonly_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        TABLE_NAME,
                        COLUMN_NAME,
                        COLUMN_TYPE,
                        IS_NULLABLE,
                        COLUMN_KEY,
                        COLUMN_DEFAULT,
                        EXTRA
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s
                    ORDER BY TABLE_NAME, ORDINAL_POSITION
                    """,
                    (db_name,),
                )
                columns = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        TABLE_NAME,
                        COLUMN_NAME,
                        REFERENCED_TABLE_NAME,
                        REFERENCED_COLUMN_NAME
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %s
                      AND REFERENCED_TABLE_NAME IS NOT NULL
                    ORDER BY TABLE_NAME, ORDINAL_POSITION
                    """,
                    (db_name,),
                )
                foreign_keys = cursor.fetchall()

        if not columns:
            raise ConfigurationError(
                f"No tables found in database '{db_name}'. "
                "Check DB_NAME and the read-only user's privileges."
            )

        tables: dict[str, list[str]] = {}
        for col in columns:
            tables.setdefault(col["TABLE_NAME"], []).append(
                "  {name} {col_type}{nullable}{key}{extra}".format(
                    name=col["COLUMN_NAME"],
                    col_type=col["COLUMN_TYPE"],
                    nullable="" if col["IS_NULLABLE"] == "YES" else " NOT NULL",
                    key=f" {col['COLUMN_KEY']}" if col["COLUMN_KEY"] else "",
                    extra=f" {col['EXTRA']}" if col["EXTRA"] else "",
                )
            )

        fk_lines = [
            f"- {fk['TABLE_NAME']}.{fk['COLUMN_NAME']} -> "
            f"{fk['REFERENCED_TABLE_NAME']}.{fk['REFERENCED_COLUMN_NAME']}"
            for fk in foreign_keys
        ]

        table_ddl = "\n\n".join(
            f"TABLE {name} (\n" + ",\n".join(cols) + "\n)"
            for name, cols in tables.items()
        )
        relations = (
            "\n\nFOREIGN KEYS:\n" + "\n".join(fk_lines) if fk_lines else ""
        )
        return table_ddl + relations

    def generate_sql(
        self,
        question: str,
        schema: str,
        previous_sql: str = "",
        error_trace: str = "",
        attempt: int = 1,
    ) -> str:
        messages = [
            {"role": "system", "content": _system_prompt(schema)},
            {"role": "user", "content": question},
        ]

        if attempt > 1 and previous_sql and error_trace:
            messages.append(
                {
                    "role": "assistant",
                    "content": previous_sql,
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "The previous SQL failed. Rewrite a corrected MySQL SELECT "
                        "that answers the original question. Return ONLY raw SQL.\n\n"
                        f"Failed SQL:\n{previous_sql}\n\n"
                        f"Error trace:\n{error_trace}"
                    ),
                }
            )

        response = self.groq_client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=messages,
        )
        raw = (response.choices[0].message.content or "").strip()
        return _clean_sql(raw)

    def validate_sql(self, sql: str) -> None:
        """AST / token-level security gateway. Blocks destructive SQL."""
        if not sql or not sql.strip():
            raise UnsafeSQLError("Empty SQL is not allowed.")

        if ";" in sql.strip().rstrip(";"):
            raise UnsafeSQLError("Multiple SQL statements are not allowed.")

        parsed = sqlparse.parse(sql)
        if not parsed:
            raise UnsafeSQLError("Unable to parse SQL.")
        if len(parsed) != 1:
            raise UnsafeSQLError("Multiple SQL statements are not allowed.")

        statement = parsed[0]
        statement_type = statement.get_type().upper()
        leading = sqlparse.format(sql, strip_comments=True).strip().upper()
        is_select = statement_type in ALLOWED_STATEMENT_TYPES or leading.startswith(
            ("SELECT", "WITH")
        )
        if not is_select:
            raise UnsafeSQLError(
                f"Only SELECT queries are allowed. Received '{statement_type or 'UNKNOWN'}'."
            )

        _assert_no_comments(statement)
        _walk_tokens(statement)

    def execute_sql(self, sql: str) -> tuple[list[dict[str, Any]], list[str]]:
        with _readonly_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SET SESSION MAX_EXECUTION_TIME = {self.query_timeout * 1000}")
                cursor.execute(sql)
                rows = cursor.fetchmany(self.max_rows)
                columns = [col[0] for col in (cursor.description or [])]

        serialized = [_serialize_row(row) for row in rows]
        return serialized, columns


def _system_prompt(schema: str) -> str:
    return f"""You are an expert MySQL analyst that writes safe, read-only SQL.

RULES:
- Return ONLY the raw SQL query. No explanations, no markdown fences.
- Produce a single SELECT (or CTE WITH ... SELECT) statement.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REPLACE, LOAD, or SET.
- Never use INTO OUTFILE, DUMPFILE, LOCK, or multiple statements.
- Only use tables and columns from the live schema below.
- Prefer explicit column names over SELECT *.
- Use valid MySQL 8 syntax.

LIVE SCHEMA:
{schema}
"""


def _clean_sql(raw: str) -> str:
    cleaned = SQL_FENCE_RE.sub("", raw).strip()
    cleaned = cleaned.split(";")[0].strip()
    return cleaned


def _assert_no_comments(statement: Statement) -> None:
    for token in statement.flatten():
        if token.ttype in Comment:
            raise UnsafeSQLError("SQL comments are not allowed.")


def _walk_tokens(token_list: TokenList) -> None:
    for token in token_list.tokens:
        if token.is_whitespace:
            continue

        value = token.value.strip().upper()

        if token.ttype in (Keyword, DML, DDL, Keyword.DML, Keyword.DDL):
            keyword = value.split()[0] if value else ""
            if keyword in FORBIDDEN_KEYWORDS:
                raise UnsafeSQLError(
                    f"Forbidden SQL keyword detected: {keyword}."
                )

        if isinstance(token, (IdentifierList, Identifier, Parenthesis, TokenList)):
            _walk_tokens(token)


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date)):
            serialized[key] = value.isoformat()
        elif isinstance(value, Decimal):
            serialized[key] = float(value)
        elif isinstance(value, (bytes, bytearray)):
            serialized[key] = value.decode("utf-8", errors="replace")
        else:
            serialized[key] = value
    return serialized


def _require_target_db() -> dict[str, Any]:
    cfg = settings.TARGET_DATABASE
    missing = [key for key in ("host", "name", "user") if not cfg.get(key)]
    if missing:
        raise ConfigurationError(
            "Target database is not fully configured. Missing: "
            + ", ".join(missing)
        )
    return cfg


@contextmanager
def _readonly_connection() -> Iterator[pymysql.connections.Connection]:
    cfg = _require_target_db()
    conn = pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["name"],
        cursorclass=DictCursor,
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=10,
        read_timeout=settings.SQL_AGENT_QUERY_TIMEOUT,
        write_timeout=settings.SQL_AGENT_QUERY_TIMEOUT,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
        yield conn
    finally:
        conn.close()
