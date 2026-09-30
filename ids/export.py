"""sql/40_training_set.sql çıktısını Parquet'e aktarır (akış hâlinde, bellek dostu).

COPY (sorgu) TO STDOUT ile gelen CSV baytları ~128 MB'lık parçalar hâlinde
pyarrow ile ayrıştırılıp tek bir Parquet dosyasına eklenir. Değer dönüşümü
dışında hiçbir işlem yapılmaz.
"""
from __future__ import annotations

import io
import time

import pyarrow as pa
import pyarrow.csv as pacsv
import polars as pl
import pyarrow.parquet as pq

from . import db
from .columns import (CANDIDATE_FEATURES, DERIVED_FEATURES, NUMERIC_FLOW_COLUMNS,
                      WINDOW_FEATURES)
from .config import PROCESSED_DIR, db_name

CHUNK_BYTES = 128 << 20
INT_COLUMNS = {"dst_port", "protocol", "no_response", "zero_duration", "well_known_port",
               "w10_port_n", "w60_port_n", "w60_all_n"}


def schema() -> pa.Schema:
    fields = [
        pa.field("flow_id", pa.int64()),
        pa.field("capture_day", pa.string()),
        pa.field("label", pa.string()),
        pa.field("is_attack", pa.bool_()),
        pa.field("split_temporal", pa.string()),
        pa.field("split_rand", pa.string()),
        pa.field("fv_seen_in_train_temporal", pa.bool_()),
        pa.field("fv_seen_in_train_random", pa.bool_()),
    ]
    for c in CANDIDATE_FEATURES:
        fields.append(pa.field(c, pa.int32() if c in INT_COLUMNS else pa.float32()))
    return pa.schema(fields)


def output_path():
    return PROCESSED_DIR / f"training_set_{db_name()}.parquet"


def training_query(where: str | None = None, benign_train_keep_pct: int | None = None,
                   split_col: str = "split_temporal") -> str:
    """sql/40_training_set.sql + isteğe bağlı satır filtresi.

    benign_train_keep_pct: YALNIZCA eğitim bölümündeki normal akışları hash(flow_id) ile
    deterministik olarak seyreltir (val/test ve tüm saldırı satırları olduğu gibi kalır).
    """
    sql = db.read_sql("40_training_set.sql")
    conds = []
    if where:
        conds.append(f"({where})")
    if benign_train_keep_pct is not None:
        conds.append(f"NOT (t.{split_col} = 'train' AND NOT t.is_attack "
                     f"AND abs(hashint8(t.flow_id)) % 100 >= {int(benign_train_keep_pct)})")
    if not conds:
        return sql
    return f"SELECT * FROM ({sql}) t WHERE " + " AND ".join(conds)


def stream_tables(conn, sql: str | None = None):
    """Eğitim sorgusunun çıktısını ~128 MB'lık pyarrow tabloları hâlinde üretir."""
    sch = schema()
    names = sch.names
    convert = pacsv.ConvertOptions(column_types={f.name: f.type for f in sch},
                                   true_values=["t"], false_values=["f"], strings_can_be_null=False)
    # COPY çıktısı tek akıştır; paralel hash join büyük work_mem ile konteynerin /dev/shm
    # alanını (compose: shm_size 2g) aşıyordu ("could not resize shared memory segment").
    conn.execute("SET work_mem = '1GB'")
    conn.execute("SET max_parallel_workers_per_gather = 0")

    def parse(data: bytes) -> pa.Table:
        tbl = pacsv.read_csv(io.BytesIO(data), read_options=pacsv.ReadOptions(column_names=names),
                             convert_options=convert)
        return tbl.select(names).cast(sch)

    sql = sql or db.read_sql("40_training_set.sql")
    # bytearray'e ekleme amortize O(1); bytes += bytes her seferinde kopyalar (karesel).
    pending = bytearray()
    with conn.cursor().copy(f"COPY ({sql}) TO STDOUT (FORMAT csv)") as cp:
        for chunk in cp:
            pending += chunk
            if len(pending) >= CHUNK_BYTES:
                cut = pending.rfind(b"\n") + 1
                yield parse(bytes(pending[:cut]))
                del pending[:cut]
    if pending:
        yield parse(bytes(pending))


def run(scheme: str | None = None) -> None:  # her iki ayrım da aynı dosyada taşınır
    """Eğitim verisini Parquet'e yazar (disk: tam veri için ~2,5 GB)."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = output_path()
    tmp = out.with_suffix(".tmp")
    t0 = time.perf_counter()
    n = 0
    with db.connect() as conn, pq.ParquetWriter(tmp, schema(), compression="zstd") as writer:
        for tbl in stream_tables(conn):
            writer.write_table(tbl)
            n += tbl.num_rows
            print(f"  {n:,} satır...", flush=True)
        dt = time.perf_counter() - t0
        db.log_timing(conn, "export", "40_training_set.sql -> parquet", dt, n, {"file": out.name})
    tmp.replace(out)
    print(f"  {out} : {n:,} satır, {out.stat().st_size / 1e6:,.0f} MB, {dt:,.1f} s")


def load_training_set(sql: str | None = None) -> pl.DataFrame:
    """Parquet varsa ve filtre yoksa onu, aksi hâlde SQL'i doğrudan belleğe okur (disk gerektirmez)."""
    path = output_path()
    if sql is None and path.exists():
        return pl.read_parquet(path)
    t0 = time.perf_counter()
    frames = []
    with db.connect() as conn:
        for tbl in stream_tables(conn, sql):
            frames.append(pl.from_arrow(tbl).with_columns(
                pl.col(["capture_day", "label", "split_temporal", "split_rand"]).cast(pl.Categorical)))
        df = pl.concat(frames, rechunk=False)
        db.log_timing(conn, "export", "40_training_set.sql -> bellek", time.perf_counter() - t0, df.height)
    print(f"  {df.height:,} satır SQL'den belleğe okundu ({time.perf_counter() - t0:,.1f} s)", flush=True)
    return df
