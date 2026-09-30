"""Sentetik uç durumlarla SQL veri hattı testi (PostgreSQL gerekir, ~20 s)."""
from __future__ import annotations

from datetime import datetime

import pytest

from ids import db, ingest, pipeline

from .conftest import flow_row, requires_db, write_csv

pytestmark = [requires_db, pytest.mark.db]

DAY_FILE = "Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv"


def build_rows():
    r = {}
    # Port 80 üzerinde bitiş zamanları bilinen akışlar (süre µs):
    r["b1"] = flow_row("14/02/2018 09:00:00", **{"Flow Duration": 0})
    r["b2"] = flow_row("14/02/2018 09:00:30", **{"Flow Duration": 0, "Flow Byts/s": "Infinity",
                                                  "Flow Pkts/s": "Infinity"})
    r["b3"] = flow_row("14/02/2018 09:01:10", **{"Flow Duration": 0, "Tot Fwd Pkts": 7})
    r["b4"] = flow_row("14/02/2018 09:00:20", **{"Dst Port": 443, "Flow Duration": 50_000_000})
    # b5 b3'ten ÖNCE başlar ama SONRA biter -> b3'ün penceresinde görünmemeli
    r["b5"] = flow_row("14/02/2018 09:00:59", **{"Flow Duration": 30_000_000})
    r["pm"] = flow_row("14/02/2018 02:15:00", **{"Dst Port": 22})           # 14:15 olmalı
    r["old"] = flow_row("05/01/1970 03:01:17")                               # gün dışı -> düşer
    r["neg"] = flow_row("14/02/2018 09:30:00", **{"Flow Duration": -5})      # negatif süre -> düşer
    r["dup"] = dict(r["b1"])                                                 # birebir tekrar -> düşer
    r["c1"] = flow_row("14/02/2018 11:30:00", **{"Dst Port": 21, "Flow Duration": 777})
    r["c2"] = flow_row("14/02/2018 11:30:00", label="FTP-BruteForce",
                       **{"Dst Port": 21, "Flow Duration": 777})             # çelişki -> ikisi de düşer
    for i in range(20):  # saldırı olayı 10:40-10:59
        r[f"a{i}"] = flow_row(f"14/02/2018 10:{40 + i}:00", label="FTP-BruteForce",
                              **{"Dst Port": 21, "Flow Duration": 1000 + i})
    return r


@pytest.fixture(scope="module")
def synthetic_db(tmp_path_factory):
    import os
    from .conftest import recreate_db
    recreate_db("ids_test")
    old = os.environ.get("IDS_DB")
    os.environ["IDS_DB"] = "ids_test"
    d = tmp_path_factory.mktemp("csv")
    rows = build_rows()
    header = ",".join(flow_row().keys())
    write_csv(d / DAY_FILE, list(rows.values()), extra_lines={3: header, 6: "80,6,14/02/2018 09:00:01,5"})
    with db.connect() as conn:
        db.run_sql_file(conn, "01_schema.sql")
        conn.autocommit = False
        stats = ingest.load_file(conn, d / DAY_FILE)
        conn.commit()
        conn.autocommit = True
    pipeline.clean()
    pipeline.features()
    yield stats, rows
    if old is None:
        os.environ.pop("IDS_DB", None)
    else:
        os.environ["IDS_DB"] = old


def q(sql, *params):
    with db.connect() as conn:
        return conn.execute(sql, params).fetchall()


def test_ingest_counts(synthetic_db):
    stats, rows = synthetic_db
    assert stats["rows"] == len(rows)
    assert stats["header_repeats"] == 1 and stats["malformed_lines"] == 1
    assert q("SELECT rows_loaded, header_repeats, malformed_lines FROM meta.ingest_files")[0] == (len(rows), 1, 1)


def test_cleaning_log_counts_every_rule(synthetic_db):
    _, rows = synthetic_db
    log = dict(q("SELECT step, sum(rows_affected)::bigint FROM meta.cleaning_log GROUP BY 1"))
    assert log[0] == len(rows)
    assert log[1] == 1   # 1970
    assert log[2] == 1   # 02:15 -> 14:15
    assert log[4] == 1   # negatif süre
    assert log[5] == 2   # b2: iki Infinity hücresi
    assert log[6] == 1   # birebir tekrar
    assert log[7] == 2   # çelişen iki satır
    assert log[9] == len(rows) - 1 - 1 - 1 - 2
    assert q("SELECT count(*) FROM clean.flows")[0][0] == log[9]


def test_cleaned_values(synthetic_db):
    (ts,), = q("SELECT ts FROM clean.flows WHERE dst_port = 22")
    assert ts == datetime(2018, 2, 14, 14, 15)
    (b, p), = q("SELECT flow_byts_s, flow_pkts_s FROM clean.flows WHERE ts = '2018-02-14 09:00:30'")
    assert b is None and p is None
    assert q("SELECT count(*) FROM clean.flows WHERE dst_port = 21 AND ts = '2018-02-14 11:30:00'")[0][0] == 0


def test_window_features_only_see_past(synthetic_db):
    got = dict(q("""SELECT to_char(c.ts, 'HH24:MI:SS'), (f.w60_port_n, f.w60_all_n)::text
                    FROM clean.flows c JOIN features.flow_features f USING (capture_day, flow_id)
                    WHERE c.ts::time BETWEEN '09:00:00' AND '09:02:00'"""))
    # bitişler: b1 09:00:00, b2 09:00:30, b4(443) 09:01:10, b3 09:01:10, b5 09:01:29
    assert got["09:00:00"] == "(0,0)"   # b1: öncesinde hiçbir şey yok
    assert got["09:00:30"] == "(1,1)"   # b2: b1
    assert got["09:01:10"] == "(1,2)"   # b3: port80->b2 (b1 70 s önce), tüm->b2,b4 ; b5 henüz bitmedi
    assert got["09:00:59"] == "(2,3)"   # b5 (09:01:29'da biter): b2,b3 ; tüm: +b4
    assert got["09:00:20"] == "(0,2)"   # b4 (443, 09:01:10'da biter): tüm -> b2, b3


def test_window_features_match_bruteforce(synthetic_db):
    rows = q("""SELECT c.flow_id, c.dst_port, c.end_ts, f.w60_port_n, f.w10_port_n
                FROM clean.flows c JOIN features.flow_features f USING (capture_day, flow_id)""")
    for fid, port, end, w60, w10 in rows:
        exp60 = sum(1 for o in rows if o[0] != fid and o[1] == port and 0 <= (end - o[2]).total_seconds() <= 60)
        exp10 = sum(1 for o in rows if o[0] != fid and o[1] == port and 0 <= (end - o[2]).total_seconds() <= 10)
        assert (w60, w10) == (exp60, exp10)


def test_splits_and_leakage_checks(synthetic_db):
    assert q("SELECT count(*) FROM features.flow_features WHERE split_temporal IS NULL "
             "OR split_temporal NOT IN ('train','val','test','gap')")[0][0] == 0
    checks = dict(((n, s), ov) for n, s, ov in q(
        "SELECT check_name, scheme, overlapping_rows FROM meta.leakage_checks"))
    assert checks[("flow_id_unique", "all")] == 0
    assert checks[("segment_purity", "temporal")] == 0
    # saldırı olayı kronolojik bölünür: train < val < test
    parts = q("""SELECT f.split_temporal, min(c.ts), max(c.ts) FROM clean.flows c
                 JOIN features.flow_features f USING (capture_day, flow_id)
                 WHERE c.is_attack AND f.split_temporal <> 'gap' GROUP BY 1""")
    rng = {s: (a, b) for s, a, b in parts}
    assert rng["train"][1] < rng["val"][0] and rng["val"][1] < rng["test"][0]
