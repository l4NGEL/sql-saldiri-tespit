"""Veritabanı yardımcıları: bağlantı, SQL dosyası çalıştırma, süre ve plan kaydı."""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg

from .config import SQL_DIR, db_dsn, db_name


def connect(dbname: str | None = None, autocommit: bool = True) -> psycopg.Connection:
    return psycopg.connect(db_dsn(dbname), autocommit=autocommit)


def ensure_database(dbname: str | None = None) -> str:
    """Hedef veritabanı yoksa bakım veritabanı ('ids') üzerinden oluşturur."""
    dbname = dbname or db_name()
    with connect("ids") as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (dbname,)).fetchone():
            conn.execute(f'CREATE DATABASE "{dbname}"')
    return dbname


def read_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def run_sql_file(conn: psycopg.Connection, name: str) -> float:
    """SQL dosyasını tek parça çalıştırır, geçen süreyi saniye olarak döner."""
    t0 = time.perf_counter()
    conn.execute(read_sql(name))
    return time.perf_counter() - t0


def log_timing(conn: psycopg.Connection, stage: str, step: str, seconds: float,
               rows: int | None = None, details: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO meta.timings(stage, step, seconds, rows_affected, details) VALUES (%s,%s,%s,%s,%s)",
        (stage, step, seconds, rows, json.dumps(details or {})),
    )


@contextmanager
def timed(conn: psycopg.Connection, stage: str, step: str, details: dict | None = None):
    box: dict = {"rows": None}
    t0 = time.perf_counter()
    yield box
    dt = time.perf_counter() - t0
    box["seconds"] = dt
    log_timing(conn, stage, step, dt, box.get("rows"), details)
    rows = f", {box['rows']:,} satır" if box.get("rows") is not None else ""
    print(f"  [{stage}] {step}: {dt:,.1f} s{rows}", flush=True)


def explain_analyze(conn: psycopg.Connection, name: str, sql: str, out_dir: Path) -> str:
    """EXPLAIN (ANALYZE, BUFFERS) çıktısını hem meta.explain_plans'a hem dosyaya yazar."""
    rows = conn.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql).fetchall()
    text = "\n".join(r[0] for r in rows)
    conn.execute("INSERT INTO meta.explain_plans(name, query, plan) VALUES (%s,%s,%s)", (name, sql, text))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.txt").write_text(f"-- {name}\n{sql.strip()}\n\n{text}\n", encoding="utf-8")
    return text
