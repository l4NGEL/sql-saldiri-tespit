"""SQL aşamalarını sırayla çalıştırır; her adımın süresini meta.timings'e yazar.

Bu modül hesaplama yapmaz: tüm dönüşümler sql/ altındaki dosyalardadır.
"""
from __future__ import annotations

from . import db
from .config import DATASET_FILES


def _days(conn, schema_table: str) -> list[str]:
    rows = conn.execute(f"SELECT DISTINCT capture_day::text FROM {schema_table} ORDER BY 1").fetchall()
    return [r[0] for r in rows]


def clean() -> None:
    day_index = {d: i + 1 for i, d in enumerate(sorted(set(DATASET_FILES.values())))}
    with db.connect() as conn:
        db.run_sql_file(conn, "01_schema.sql")
        db.run_sql_file(conn, "10_clean.sql")
        with db.timed(conn, "clean", "11_audit.sql (ham veri denetimi)"):
            db.run_sql_file(conn, "11_audit.sql")
        for day in _days(conn, "raw.flows"):
            with db.timed(conn, "clean", f"clean.build_day({day})") as t:
                conn.execute("SET work_mem = '1GB'")
                conn.execute("CALL clean.build_day(%s, %s)", (day, day_index[day]))
                t["rows"] = conn.execute(
                    "SELECT rows_affected FROM meta.cleaning_log WHERE step = 9 AND details->>'day' = %s", (day,)
                ).fetchone()[0]
        with db.timed(conn, "clean", "ANALYZE clean.flows"):
            conn.execute("ANALYZE clean.flows")
        summary = conn.execute(
            "SELECT step, rule, action, sum(rows_affected) FROM meta.cleaning_log GROUP BY 1,2,3 ORDER BY 1"
        ).fetchall()
    print("\nTemizleme özeti (tüm günler):")
    for step, rule, action, n in summary:
        print(f"  {step}. [{action:6}] {rule}: {n:,}")


def features() -> None:
    with db.connect() as conn:
        db.run_sql_file(conn, "20_features.sql")
        for day in _days(conn, "clean.flows"):
            with db.timed(conn, "features", f"features.build_day({day})") as t:
                conn.execute("SET work_mem = '1GB'")
                conn.execute("CALL features.build_day(%s)", (day,))
                t["rows"] = conn.execute(
                    "SELECT count(*) FROM features.flow_features WHERE capture_day = %s", (day,)
                ).fetchone()[0]
        with db.timed(conn, "features", "ANALYZE features.flow_features"):
            conn.execute("ANALYZE features.flow_features")
        with db.timed(conn, "features", "30_splits_leakage.sql"):
            db.run_sql_file(conn, "30_splits_leakage.sql")
        checks = conn.execute(
            "SELECT check_name, scheme, split, rows, overlapping_rows FROM meta.leakage_checks ORDER BY 1,2,3"
        ).fetchall()
    print("\nSızıntı denetimleri:")
    for name, scheme, split, rows, ov in checks:
        pct = 100 * ov / rows if rows else 0
        print(f"  {name:36} {scheme:10} {split:5} {ov:>12,} / {rows:>12,} ({pct:5.2f}%)")
