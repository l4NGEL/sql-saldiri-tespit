"""CSV -> raw.flows içe aktarma (parçalı, bellek dostu).

Dosya hiçbir zaman tamamen belleğe alınmaz: satırlar akış halinde okunur,
~16 MB'lık tamponlar hâlinde PostgreSQL COPY'ye yazılır. Her dosya kendi gün
bölümüne (raw.flows_YYYYMMDD) yüklenir; bölüm aynı işlemde yeniden
oluşturulduğu için komut tekrar çalıştırılabilir (idempotent) ve wal_level=minimal
ile COPY WAL üretmez.
"""
from __future__ import annotations

import gzip
import time
from pathlib import Path

import psycopg

from . import db
from .columns import CSV_TO_SQL
from .config import DATASET_FILES, RAW_DIR, SAMPLE_DIR

BUFFER_BYTES = 16 << 20
MAX_REJECT_SAMPLES = 20


def partition_name(day: str) -> str:
    return "flows_" + day.replace("-", "")


def open_any(path: Path):
    return gzip.open(path, "rb") if path.suffix == ".gz" else open(path, "rb")


def day_for(path: Path) -> str:
    name = path.name.removesuffix(".gz")
    if name not in DATASET_FILES:
        raise ValueError(f"Tanınmayan dosya: {path.name}")
    return DATASET_FILES[name]


def stream_rows(path: Path, day: str, stats: dict):
    """(capture_day,line_no,<csv satırı>) biçiminde bayt blokları üretir; istatistikleri doldurur."""
    with open_any(path) as fh:
        header = fh.readline()
        cols = [c.strip() for c in header.decode("utf-8-sig").strip().split(",")]
        unknown = [c for c in cols if c not in CSV_TO_SQL]
        if unknown:
            raise ValueError(f"{path.name}: bilinmeyen sütunlar {unknown}")
        stats["columns"] = [CSV_TO_SQL[c] for c in cols]
        n_commas = header.count(b",")
        header_stripped = header.strip()
        prefix_day = day.encode() + b","
        buf: list[bytes] = []
        size = 0
        line_no = 1
        for line in fh:
            line_no += 1
            stripped = line.strip()
            if not stripped:
                stats["empty_lines"] += 1
                continue
            if stripped == header_stripped:  # birleştirilmiş dosyalarda tekrar eden başlık
                stats["header_repeats"] += 1
                continue
            if stripped.count(b",") != n_commas:
                stats["malformed_lines"] += 1
                if len(stats["reject_samples"]) < MAX_REJECT_SAMPLES:
                    stats["reject_samples"].append((line_no, "column_count", stripped[:300].decode(errors="replace")))
                continue
            row = prefix_day + str(line_no).encode() + b"," + stripped + b"\n"
            buf.append(row)
            size += len(row)
            stats["rows"] += 1
            if size >= BUFFER_BYTES:
                yield b"".join(buf)
                buf, size = [], 0
        stats["lines_total"] = line_no
        if buf:
            yield b"".join(buf)


def load_file(conn: psycopg.Connection, path: Path) -> dict:
    day = day_for(path)
    part = partition_name(day)
    stats = {"rows": 0, "header_repeats": 0, "malformed_lines": 0, "empty_lines": 0,
             "reject_samples": [], "lines_total": 0}
    t0 = time.perf_counter()
    with conn.transaction():
        conn.execute("SET LOCAL datestyle = 'ISO, DMY'")
        conn.execute(f"DROP TABLE IF EXISTS raw.{part}")
        conn.execute(f"CREATE TABLE raw.{part} (LIKE raw.flows INCLUDING DEFAULTS)")
        conn.execute(f"ALTER TABLE raw.{part} ADD CONSTRAINT {part}_day CHECK (capture_day = DATE '{day}')")
        blocks = stream_rows(path, day, stats)
        first = next(blocks, None)  # başlık okunup sütunlar belirlensin
        col_list = ", ".join(["capture_day", "line_no"] + stats["columns"])
        with conn.cursor().copy(f"COPY raw.{part} ({col_list}) FROM STDIN (FORMAT csv)") as cp:
            if first is not None:
                cp.write(first)
            for block in blocks:
                cp.write(block)
        # CHECK kısıtı sayesinde ATTACH tabloyu yeniden taramaz.
        conn.execute(f"ALTER TABLE raw.flows ATTACH PARTITION raw.{part} FOR VALUES IN ('{day}')")
        conn.execute("DELETE FROM meta.ingest_files WHERE source_file = %s", (path.name,))
        conn.execute("DELETE FROM meta.ingest_rejects WHERE source_file = %s", (path.name,))
        dt = time.perf_counter() - t0
        conn.execute(
            """INSERT INTO meta.ingest_files(source_file, capture_day, file_bytes, lines_total,
                   header_repeats, malformed_lines, rows_loaded, seconds, method)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'copy_stream_same_txn')""",
            (path.name, day, path.stat().st_size, stats["lines_total"], stats["header_repeats"],
             stats["malformed_lines"], stats["rows"], dt),
        )
        for ln, reason, sample in stats["reject_samples"]:
            conn.execute("INSERT INTO meta.ingest_rejects VALUES (%s,%s,%s,%s)", (path.name, ln, reason, sample))
        db.log_timing(conn, "ingest", path.name, dt, stats["rows"], {"file_bytes": path.stat().st_size})
    stats["seconds"] = dt
    return stats


def find_files(sample: bool) -> list[Path]:
    base = SAMPLE_DIR if sample else RAW_DIR
    out = []
    for name in DATASET_FILES:
        for cand in (base / name, base / (name + ".gz")):
            if cand.exists():
                out.append(cand)
                break
    return out


def verify_counts(stats: dict) -> bool:
    """Dosyadaki her veri satırı ya yüklendi ya da gerekçesiyle sayıldı mı?"""
    accounted = stats["rows"] + stats["header_repeats"] + stats["malformed_lines"] + stats["empty_lines"]
    return accounted == stats["lines_total"] - 1


def run(sample: bool = False, only: list[str] | None = None, delete_csv: bool = False) -> None:
    dbname = db.ensure_database()
    with db.connect() as conn:
        db.run_sql_file(conn, "01_schema.sql")
        files = [f for f in find_files(sample) if not only or any(o in f.name for o in only)]
        if not files:
            raise SystemExit("Yüklenecek dosya yok. Önce `python -m ids download` (veya --sample) çalıştırın.")
        print(f"{len(files)} dosya -> {dbname}.raw.flows")
        for f in files:
            conn.autocommit = False
            s = load_file(conn, f)
            conn.commit()
            conn.autocommit = True
            print(f"  {f.name}: {s['rows']:,} satır, {s['header_repeats']} tekrar başlık, "
                  f"{s['malformed_lines']} bozuk satır, {s['seconds']:,.1f} s "
                  f"({s['rows'] / max(s['seconds'], 1e-9):,.0f} satır/s)", flush=True)
            if not verify_counts(s):
                raise RuntimeError(f"{f.name}: satır sayıları tutmuyor {s}")
            if delete_csv and not sample:
                # raw bölümü dosyanın tipli, satır satır karşılığıdır; dosya resmi kaynaktan
                # yeniden indirilebilir. Disk sınırlı makinelerde yer açmak için silinir.
                f.unlink()
                print(f"    silindi (yüklendi ve doğrulandı): {f.name}", flush=True)
        conn.execute("ANALYZE raw.flows")
