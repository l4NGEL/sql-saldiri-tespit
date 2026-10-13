"""PostgreSQL -> gün bölümlü Parquet "lake" (Spark hattının girdisi).

İki ayrı çıktı üretir:
  data/lake/<db>/clean_flows/capture_day=YYYY-MM-DD/part-0.parquet
      clean.flows: temizlenmiş ham akış ölçümleri + etiket + zamansal ayrım bölümü.
      Özellik İÇERMEZ; Spark özellikleri buradan kendisi üretir.
  data/lake/<db>/sql_features/capture_day=YYYY-MM-DD/part-0.parquet
      features.flow_features'taki 20 SQL özelliği. YALNIZCA parite denetimi
      (Spark çıktısı == SQL çıktısı) için; Spark hattı bunu okumaz.

Zaman, saat dilimi belirsizliği olmasın diye epoch mikrosaniyesi (int64) olarak taşınır.
"""
from __future__ import annotations

import io
import shutil
import time

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from . import db
from .columns import DERIVED_FEATURES, NUMERIC_FLOW_COLUMNS, WINDOW_FEATURES
from .config import DATA_DIR, db_name


def lake_dir():
    return DATA_DIR / "lake" / db_name()


def clean_dir():
    return lake_dir() / "clean_flows"


def sql_features_dir():
    return lake_dir() / "sql_features"


INT_FEATURES = {"no_response", "zero_duration", "well_known_port", "w10_port_n", "w60_port_n", "w60_all_n"}


def clean_schema() -> pa.Schema:
    return pa.schema(
        [pa.field("flow_id", pa.int64()), pa.field("end_us", pa.int64()),
         pa.field("label", pa.string()), pa.field("is_attack", pa.bool_()),
         pa.field("split_temporal", pa.string()),
         pa.field("dst_port", pa.int32()), pa.field("protocol", pa.int32())]
        + [pa.field(c, pa.float32()) for c in NUMERIC_FLOW_COLUMNS])


def sql_features_schema() -> pa.Schema:
    return pa.schema([pa.field("flow_id", pa.int64())]
                     + [pa.field(c, pa.int32() if c in INT_FEATURES else pa.float32())
                        for c in DERIVED_FEATURES + WINDOW_FEATURES])


def clean_query(day: str) -> str:
    cols = ", ".join(f"c.{c}" for c in NUMERIC_FLOW_COLUMNS)
    return f"""
        SELECT c.flow_id, (extract(epoch FROM c.end_ts) * 1000000)::bigint, c.label, c.is_attack,
               f.split_temporal, c.dst_port, c.protocol, {cols}
        FROM clean.flows c
        JOIN features.flow_features f ON f.flow_id = c.flow_id AND f.capture_day = c.capture_day
        WHERE c.capture_day = DATE '{day}'"""


def sql_features_query(day: str) -> str:
    cols = ", ".join(DERIVED_FEATURES + WINDOW_FEATURES)
    return f"SELECT flow_id, {cols} FROM features.flow_features WHERE capture_day = DATE '{day}'"


def _copy_to_parquet(conn, sql: str, schema: pa.Schema, out) -> int:
    convert = pacsv.ConvertOptions(column_types={f.name: f.type for f in schema},
                                   true_values=["t"], false_values=["f"], strings_can_be_null=False)
    read = pacsv.ReadOptions(column_names=schema.names, block_size=64 << 20)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    n = 0
    pending = bytearray()
    with pq.ParquetWriter(tmp, schema, compression="zstd") as w, \
            conn.cursor().copy(f"COPY ({sql}) TO STDOUT (FORMAT csv)") as cp:
        def flush(data: bytes):
            tbl = pacsv.read_csv(io.BytesIO(data), read_options=read, convert_options=convert)
            w.write_table(tbl.cast(schema))
            return tbl.num_rows
        for chunk in cp:
            pending += chunk
            if len(pending) >= 128 << 20:
                cut = pending.rfind(b"\n") + 1
                n += flush(bytes(pending[:cut]))
                del pending[:cut]
        if pending:
            n += flush(bytes(pending))
    tmp.replace(out)
    return n


def days(conn) -> list[str]:
    return [str(r[0]) for r in conn.execute("SELECT DISTINCT capture_day FROM clean.flows ORDER BY 1")]


def run(with_sql_features: bool = True) -> None:
    for d in (clean_dir(), sql_features_dir()):
        shutil.rmtree(d, ignore_errors=True)
    t0 = time.perf_counter()
    total = 0
    with db.connect() as conn:
        conn.execute("SET max_parallel_workers_per_gather = 0")
        for day in days(conn):
            n = _copy_to_parquet(conn, clean_query(day), clean_schema(),
                                 clean_dir() / f"capture_day={day}" / "part-0.parquet")
            total += n
            msg = f"  {day}: {n:,} akış"
            if with_sql_features:
                m = _copy_to_parquet(conn, sql_features_query(day), sql_features_schema(),
                                     sql_features_dir() / f"capture_day={day}" / "part-0.parquet")
                if m != n:
                    raise RuntimeError(f"{day}: clean {n} satır, özellik {m} satır")
            print(msg, flush=True)
        dt = time.perf_counter() - t0
        db.log_timing(conn, "lake", "clean.flows -> parquet", dt, total)
    size = sum(p.stat().st_size for p in lake_dir().rglob("*.parquet")) / 1e9
    print(f"  lake: {total:,} akış, {size:.2f} GB, {dt:,.1f} s")
