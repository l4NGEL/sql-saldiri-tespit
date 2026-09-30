"""Performans karşılaştırmaları ve EXPLAIN ANALYZE kayıtları: python -m ids bench

Her karşılaştırma aynı veri üzerinde iki yaklaşımı ölçer ve meta.benchmarks'a yazar.
EXPLAIN çıktıları reports/explain/*.txt ve meta.explain_plans'a kaydedilir.
Sorgular sql/bench/*.sql dosyalarındadır ({part}/{day} yer tutucularıyla).
"""
from __future__ import annotations

import io
import json
import time

from . import db
from .config import REPORTS_DIR, SQL_DIR

EXPLAIN_DIR = REPORTS_DIR / "explain"


def bench_sql(name: str, **kw) -> str:
    return (SQL_DIR / "bench" / name).read_text(encoding="utf-8").format(**kw)


def record(conn, name, variant, metric, value, details=None):
    conn.execute("INSERT INTO meta.benchmarks(name, variant, metric, value, details) VALUES (%s,%s,%s,%s,%s)",
                 (name, variant, metric, value, json.dumps(details or {})))
    print(f"  {name:28} {variant:40} {metric:14} {value:,.3f}")


def timed_exec(conn, sql: str, timeout_s: int | None = None) -> float | None:
    if timeout_s:
        conn.execute(f"SET statement_timeout = '{timeout_s}s'")
    t0 = time.perf_counter()
    try:
        conn.execute(sql)
        return time.perf_counter() - t0
    except Exception as exc:  # zaman aşımı
        if "statement timeout" in str(exc):
            return None
        raise
    finally:
        conn.execute("SET statement_timeout = 0")


def pick_day(conn, dense: bool = False) -> str:
    """Karşılaştırma günü: orta büyüklükte gün; dense=True ise en çok akışlı gün."""
    rows = conn.execute("SELECT capture_day::text, count(*) FROM clean.flows GROUP BY 1 ORDER BY 2 DESC").fetchall()
    if dense:
        return rows[0][0]
    return rows[len(rows) // 2][0]  # orta büyüklükte bir gün


def ingest_methods(conn, part: str, n: int = 100_000) -> None:
    """COPY vs toplu INSERT; aynı işlemde oluşturulan tablo (WAL atlanır) vs mevcut tablo."""
    buf = io.BytesIO()
    with conn.cursor().copy(f"COPY (SELECT * FROM raw.{part} LIMIT {n}) TO STDOUT (FORMAT csv)") as cp:
        for chunk in cp:
            buf.write(chunk)
    data = buf.getvalue()
    rows = conn.execute(f"SELECT * FROM raw.{part} LIMIT {n}").fetchall()
    ncol = len(rows[0])
    n = len(rows)  # bölüm n'den küçükse gerçek satır sayısı

    def wal_lsn():
        # insert konumu: synchronous_commit=off iken yazılmış konum (pg_current_wal_lsn) geride kalır
        return conn.execute("SELECT pg_current_wal_insert_lsn()").fetchone()[0]

    def wal_bytes(a, b):
        return float(conn.execute("SELECT pg_wal_lsn_diff(%s, %s)", (b, a)).fetchone()[0])

    # 1) COPY, tablo aynı işlemde oluşturuluyor (ingest.py'nin yaptığı)
    conn.execute("DROP TABLE IF EXISTS bench_ingest")
    a = wal_lsn(); t0 = time.perf_counter()
    with conn.transaction():
        conn.execute(f"CREATE TABLE bench_ingest (LIKE raw.{part})")
        with conn.cursor().copy("COPY bench_ingest FROM STDIN (FORMAT csv)") as cp:
            cp.write(data)
    dt = time.perf_counter() - t0; w = wal_bytes(a, wal_lsn())
    record(conn, "ingest_100k", "COPY, aynı işlemde oluşturulan tablo", "rows_per_s", n / dt, {"seconds": dt})
    record(conn, "ingest_100k", "COPY, aynı işlemde oluşturulan tablo", "wal_mb", w / 1e6)

    # 2) COPY, önceden var olan tabloya
    conn.execute("TRUNCATE bench_ingest")
    conn.execute("CHECKPOINT")
    a = wal_lsn(); t0 = time.perf_counter()
    with conn.transaction():
        with conn.cursor().copy("COPY bench_ingest FROM STDIN (FORMAT csv)") as cp:
            cp.write(data)
    dt = time.perf_counter() - t0; w = wal_bytes(a, wal_lsn())
    record(conn, "ingest_100k", "COPY, mevcut tablo", "rows_per_s", n / dt, {"seconds": dt})
    record(conn, "ingest_100k", "COPY, mevcut tablo", "wal_mb", w / 1e6)

    # 3) executemany INSERT (satır satır parametreli, tek işlem)
    conn.execute("TRUNCATE bench_ingest")
    ph = ",".join(["%s"] * ncol)
    t0 = time.perf_counter()
    with conn.transaction():
        with conn.cursor() as cur:
            cur.executemany(f"INSERT INTO bench_ingest VALUES ({ph})", rows)
    dt = time.perf_counter() - t0
    record(conn, "ingest_100k", "executemany INSERT", "rows_per_s", n / dt, {"seconds": dt})
    conn.execute("DROP TABLE bench_ingest")


def raw_storage(conn, part: str) -> None:
    """numeric vs float8: aynı satırların sayısal sütunlarının tuple boyutu (kopya tablo yazmadan)."""
    n, num_b, f8_b = conn.execute(bench_sql("raw_numeric_vs_float8.sql", part=part)).fetchone()
    size = conn.execute(f"SELECT pg_total_relation_size('raw.{part}')").fetchone()[0]
    d = {"rows": n, "part": part, "not": "yalnızca 77 akış ölçümü sütunu; tuple başlığı dahil"}
    record(conn, "raw_storage", "numeric (kullanılan)", "tuple_bytes", float(num_b), d)
    record(conn, "raw_storage", "double precision", "tuple_bytes", float(f8_b), d)
    record(conn, "raw_storage", "numeric (kullanılan)", "table_bytes_per_row", size / n, d)


def audit_scan(conn, part: str) -> None:
    for variant, f in [("sütun başına ayrı tarama (ilk sürüm)", "audit_per_column_scan.sql"),
                       ("tek tarama (kullanılan)", "audit_single_scan.sql")]:
        conn.execute("SELECT 1")
        dt = timed_exec(conn, bench_sql(f, part=part))
        record(conn, "audit_one_day", variant, "seconds", dt, {"part": part})


def window_sum(conn, part: str) -> None:
    for variant, f in [("float toplamı (ters fonksiyon yok)", "window_float_sum.sql"),
                       ("bigint toplamı (kullanılan)", "window_int_sum.sql")]:
        dt = timed_exec(conn, bench_sql(f, part=part), timeout_s=600)
        record(conn, "moving_window_sum", variant, "seconds",
               dt if dt is not None else float("nan"),
               {"part": part, "timeout_s": 600, "timed_out": dt is None})


def window_index(conn, part: str) -> None:
    q = bench_sql("window_port_count.sql", part=part)
    conn.execute(f"DROP INDEX IF EXISTS clean.bench_{part}_port_end")
    db.explain_analyze(conn, f"window_port_count_{part}_no_index", q, EXPLAIN_DIR)
    dt = timed_exec(conn, q)
    record(conn, "window_feature_sort", "indeks yok (sıralama)", "seconds", dt, {"part": part})
    t0 = time.perf_counter()
    conn.execute(f"CREATE INDEX bench_{part}_port_end ON clean.{part} (dst_port, end_ts)")
    conn.execute(f"ANALYZE clean.{part}")
    record(conn, "window_feature_sort", "indeks oluşturma", "seconds", time.perf_counter() - t0, {"part": part})
    db.explain_analyze(conn, f"window_port_count_{part}_with_index", q, EXPLAIN_DIR)
    dt = timed_exec(conn, q)
    record(conn, "window_feature_sort", "(dst_port, end_ts) indeksi", "seconds", dt, {"part": part})
    conn.execute(f"DROP INDEX clean.bench_{part}_port_end")


def pruning(conn, day: str) -> None:
    for variant, f in [("capture_day = gün (bölüm budama)", "pruning_partition_key.sql"),
                       ("ts::date = gün (budama yok)", "pruning_non_key.sql")]:
        q = bench_sql(f, day=day)
        db.explain_analyze(conn, f.removesuffix(".sql"), q, EXPLAIN_DIR)
        dt = timed_exec(conn, q)
        record(conn, "partition_pruning", variant, "seconds", dt, {"day": day})


def run(only: str | None = None) -> None:
    if only == "api":
        api_latency()
        return
    with db.connect() as conn:
        db.run_sql_file(conn, "01_schema.sql")
        conn.execute("DELETE FROM meta.benchmarks")
        conn.execute("SET max_parallel_workers_per_gather = 4")
        day = pick_day(conn)
        part = "flows_" + day.replace("-", "")
        print(f"Karşılaştırma günü: {day}")
        small_part = "flows_" + conn.execute(
            "SELECT capture_day::text FROM clean.flows GROUP BY 1 ORDER BY count(*) LIMIT 1").fetchone()[0].replace("-", "")
        ingest_methods(conn, part)
        raw_storage(conn, part)
        audit_scan(conn, part)
        window_sum(conn, part)
        window_index(conn, small_part)  # indeks yazımı disk ister -> en küçük gün
        pruning(conn, day)
        # Önemli üretim sorgularının planları
        db.explain_analyze(conn, "leakage_overlap", bench_sql("leakage_overlap.sql"), EXPLAIN_DIR)
        feat_sql = (SQL_DIR / "20_features.sql").read_text(encoding="utf-8")
        start = feat_sql.index("INSERT INTO features.%I") + len("INSERT INTO features.%I")
        body = feat_sql[start:feat_sql.index("$q$, part, src);")]
        db.explain_analyze(conn, f"features_build_select_{part}", body.replace("%I", part, 1).strip(), EXPLAIN_DIR)
    api_latency()


def api_latency(n: int = 1000) -> None:
    """Gerçek HTTP gecikmesi: uvicorn (arka plan iş parçacığı) + httpx, localhost, keep-alive.

    İstek gövdeleri test bölümündeki gerçek akışlardan kurulur.
    """
    import socket
    import threading

    import httpx
    import numpy as np
    import polars as pl
    import uvicorn

    from . import export
    from .api import app, load_model
    from .columns import NUMERIC_FLOW_COLUMNS

    load_model()
    # Örnekleme SQL'de yapılır: tüm eğitim setini belleğe almak tam veride ~10 GB ister.
    sql = (export.training_query(where="t.split_temporal = 'test'")
           + f" ORDER BY hashint8(t.flow_id) LIMIT {int(n)}")
    df = export.load_training_set(sql)
    win = ["w10_port_n", "w60_port_n", "w60_all_n", "w60_port_mean_fwd_pkts", "w60_port_mean_duration_s",
           "w60_port_noresp_share", "w60_port_rst_share"]
    bodies = []
    for row in df.iter_rows(named=True):
        flow = {c: row[c] for c in ["dst_port", "protocol"] + NUMERIC_FLOW_COLUMNS}
        for k, v in flow.items():  # temizlikte NULL'lanan ölçümler: oranlar null kalır, diğerleri 0
            if v is None or (isinstance(v, float) and np.isnan(v)):
                flow[k] = None if k in ("flow_byts_s", "flow_pkts_s") else 0.0
        flow["fwd_pkt_len_min"] = min(flow["fwd_pkt_len_min"], flow["fwd_pkt_len_max"])
        flow["bwd_pkt_len_min"] = min(flow["bwd_pkt_len_min"], flow["bwd_pkt_len_max"])
        flow["flow_iat_min"] = min(flow["flow_iat_min"], flow["flow_iat_max"])
        bodies.append({"flow": flow, "window": {k: row[k] for k in win}})

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    while not server.started:
        time.sleep(0.05)
    times, codes, server_ms = [], [], []
    with httpx.Client(base_url=f"http://127.0.0.1:{port}") as cl:
        for b in bodies[:50]:
            cl.post("/predict", json=b)  # ısınma
        for b in bodies:
            t0 = time.perf_counter()
            r = cl.post("/predict", json=b)
            times.append((time.perf_counter() - t0) * 1000)
            codes.append(r.status_code)
            if r.status_code == 200:
                server_ms.append(r.json()["inference_ms"])
    server.should_exit = True
    th.join(timeout=10)
    t = np.array(times)
    ok = sum(c == 200 for c in codes)
    with db.connect() as conn:
        conn.execute("DELETE FROM meta.benchmarks WHERE name = 'api_latency'")
        d = {"requests": n, "ok": ok, "transport": "HTTP/1.1 localhost, keep-alive, tek istemci"}
        for p in (50, 95, 99):
            record(conn, "api_latency", "POST /predict uçtan uca", f"p{p}_ms", float(np.percentile(t, p)), d)
        record(conn, "api_latency", "sunucu içi (özellik + model)", "p50_ms", float(np.median(server_ms)), d)
    if ok != n:
        raise RuntimeError(f"{n - ok} istek başarısız: {set(codes)}")
