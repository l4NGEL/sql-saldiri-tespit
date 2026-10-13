"""PySpark özellik hattı: önek toplamı pencereleri == rangeBetween == kaba kuvvet.

Spark, Windows'ta yerel dosya sistemi için Hadoop ikilileri istediğinden bu testler
konteynerde koşar:  docker compose run --rm spark python -m pytest tests/test_spark.py
"""
from __future__ import annotations

import math
import os
import random

import pytest

pyspark = pytest.importorskip("pyspark")
pytestmark = pytest.mark.skipif(os.name == "nt", reason="Spark testleri Docker'da: compose 'spark' servisi")

from ids.features_py import derived as derived_py  # noqa: E402
from ids.spark_job import FEATURES, derived, session, windows_naive, windows_prefix  # noqa: E402

WIN_COLS = ["w10_port_n", "w60_port_n", "w60_all_n", "w60_port_share", "w60_port_mean_fwd_pkts",
            "w60_port_mean_duration_s", "w60_port_noresp_share", "w60_port_rst_share"]


@pytest.fixture(scope="module")
def spark():
    s = session("ids-test")
    yield s
    s.stop()


def synthetic_flows(n=600, seed=7):
    """Çok sayıda eşzamanlı bitiş, NULL değerler, iki gün ve birkaç port içeren akışlar."""
    rnd = random.Random(seed)
    rows = []
    for i in range(n):
        day = "2018-02-14" if i % 3 else "2018-02-15"
        end_s = rnd.choice([rnd.randint(0, 200), rnd.randint(0, 200) + 0.5, 30, 30, 90])
        rows.append({
            "flow_id": i, "capture_day": day, "dst_port": rnd.choice([80, 80, 443, 22, 8080]),
            "end_us": int(end_s * 1_000_000) + 1_518_566_400_000_000,
            "tot_fwd_pkts": None if rnd.random() < 0.05 else float(rnd.randint(0, 50)),
            "tot_bwd_pkts": None if rnd.random() < 0.05 else float(rnd.choice([0, 0, 1, 7])),
            "totlen_fwd_pkts": float(rnd.randint(0, 5000)), "totlen_bwd_pkts": float(rnd.randint(0, 5000)),
            "flow_duration": float(rnd.choice([0, 1, 10_000, 3_000_000, 120_000_000])),
            "rst_flag_cnt": None if rnd.random() < 0.05 else float(rnd.choice([0, 0, 1])),
            "fwd_header_len": float(rnd.choice([0, 20, 40])),
            "flow_iat_std": float(rnd.randint(0, 100)), "flow_iat_mean": float(rnd.choice([0, 5, 50])),
            "active_mean": float(rnd.randint(0, 100)), "idle_mean": float(rnd.randint(0, 100)),
        })
    return rows


def frame(spark, rows):
    schema = ("flow_id long, capture_day string, dst_port int, end_us long, tot_fwd_pkts float, "
              "tot_bwd_pkts float, totlen_fwd_pkts float, totlen_bwd_pkts float, flow_duration float, "
              "rst_flag_cnt float, fwd_header_len float, flow_iat_std float, flow_iat_mean float, "
              "active_mean float, idle_mean float")
    return spark.createDataFrame([tuple(r[k] for k in [c.split()[0] for c in schema.split(", ")]) for r in rows],
                                 schema)


def brute_force(rows):
    """sql/20_features.sql pencere tanımının doğrudan Python karşılığı."""
    out = {}
    for r in rows:
        t, day, port = r["end_us"], r["capture_day"], r["dst_port"]
        same_day = [x for x in rows if x["capture_day"] == day]
        p60 = [x for x in same_day if x["dst_port"] == port and t - 60_000_000 <= x["end_us"] <= t]
        p10 = [x for x in same_day if x["dst_port"] == port and t - 10_000_000 <= x["end_us"] <= t]
        a60 = [x for x in same_day if t - 60_000_000 <= x["end_us"] <= t]
        n = len(p60) - 1

        def mean(f, scale=1.0):
            vals = [f(x) for x in p60]
            own = f(r)
            if n == 0 or own is None:
                return None
            s = sum(v for v in vals if v is not None)
            return (s - own) / scale / n

        out[r["flow_id"]] = {
            "w10_port_n": len(p10) - 1, "w60_port_n": n, "w60_all_n": len(a60) - 1,
            "w60_port_share": n / (len(a60) - 1) if len(a60) > 1 else None,
            "w60_port_mean_fwd_pkts": mean(lambda x: None if x["tot_fwd_pkts"] is None else round(x["tot_fwd_pkts"])),
            "w60_port_mean_duration_s": mean(lambda x: round(x["flow_duration"]), 1e6),
            "w60_port_noresp_share": mean(lambda x: None if x["tot_bwd_pkts"] is None else int(x["tot_bwd_pkts"] == 0)),
            "w60_port_rst_share": mean(lambda x: None if x["rst_flag_cnt"] is None else int(x["rst_flag_cnt"] > 0)),
        }
    return out


def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9)


def test_prefix_windows_match_brute_force_and_range_between(spark):
    rows = synthetic_flows()
    df = frame(spark, rows)
    want = brute_force(rows)
    prefix = {r["flow_id"]: r.asDict() for r in windows_prefix(df).collect()}
    naive = {r["flow_id"]: r.asDict() for r in windows_naive(df).collect()}
    assert set(prefix) == set(naive) == set(want)
    for fid, w in want.items():
        for c in WIN_COLS:
            assert close(prefix[fid][c], w[c]), (fid, c, prefix[fid][c], w[c])
            assert close(naive[fid][c], w[c]), (fid, c, naive[fid][c], w[c])


def test_derived_matches_serving_mirror(spark):
    """Spark satır özellikleri == API'nin kullandığı Python aynası (ids/features_py.py)."""
    rows = [r for r in synthetic_flows(200) if r["tot_fwd_pkts"] is not None and r["tot_bwd_pkts"] is not None]
    got = {r["flow_id"]: r.asDict() for r in derived(frame(spark, rows)).collect()}
    for r in rows:
        for c, v in derived_py(r).items():
            assert close(got[r["flow_id"]][c], None if v is None else float(v)), (c, got[r["flow_id"]][c], v)


def test_feature_list_is_sql_feature_list():
    from ids.columns import DERIVED_FEATURES, WINDOW_FEATURES
    assert FEATURES == DERIVED_FEATURES + WINDOW_FEATURES
