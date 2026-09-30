"""Veritabanı gerektirmeyen birim testleri."""
from __future__ import annotations

import re

import numpy as np
import polars as pl
import pytest

from ids import ingest
from ids.columns import (CANDIDATE_FEATURES, DERIVED_FEATURES, FORBIDDEN_FEATURES,
                         NUMERIC_FLOW_COLUMNS, WINDOW_FEATURES)
from ids.config import SQL_DIR
from ids.modeling import (binary_metrics, downsample, make_logreg, select_features,
                          threshold_best_f1, threshold_for_fa_budget)

from .conftest import flow_row, write_csv


# ---- sütun / özellik politikası --------------------------------------------------------
def test_schema_has_every_flow_column():
    schema = (SQL_DIR / "01_schema.sql").read_text(encoding="utf-8")
    for c in NUMERIC_FLOW_COLUMNS:
        assert re.search(rf"^\s+{c}\s+numeric,", schema, re.M), f"raw.flows'ta {c} yok"
        assert re.search(rf"^\s+{c}\s+real,", schema, re.M), f"clean.flows'ta {c} yok"


def test_training_query_selects_all_candidates_in_order():
    sql = (SQL_DIR / "40_training_set.sql").read_text(encoding="utf-8")
    body = sql[sql.index("SELECT"):sql.index("FROM clean.flows")]
    selected = [m.split(".")[-1].split(" AS ")[-1].strip()
                for m in re.findall(r"^\s+(?:[a-z]+\.)?([a-z_0-9]+(?:\s+AS\s+[a-z_0-9]+)?)[,\s]*$", body, re.M)]
    assert selected[-len(CANDIDATE_FEATURES):] == CANDIDATE_FEATURES


def test_features_sql_defines_derived_and_window_columns():
    sql = (SQL_DIR / "20_features.sql").read_text(encoding="utf-8")
    for c in DERIVED_FEATURES + WINDOW_FEATURES:
        assert re.search(rf"^\s+{c}\s+(real|integer|smallint),?$", sql, re.M), c


def test_no_forbidden_feature_is_a_candidate():
    assert not set(CANDIDATE_FEATURES) & set(FORBIDDEN_FEATURES)


def test_select_features_rejects_forbidden_and_drops_train_constants():
    df = pl.DataFrame({c: np.arange(10, dtype=np.float32) for c in CANDIDATE_FEATURES})
    df = df.with_columns(pl.lit(0.0).alias("fwd_urg_flags"))
    feats, constant = select_features(df)
    assert "fwd_urg_flags" in constant and "fwd_urg_flags" not in feats
    import ids.modeling as m
    orig = m.CANDIDATE_FEATURES
    try:
        m.CANDIDATE_FEATURES = orig + ["label"]
        with pytest.raises(ValueError):
            select_features(df.with_columns(pl.lit("x").alias("label")))
    finally:
        m.CANDIDATE_FEATURES = orig


# ---- içe aktarma (akış hâlinde okuma) -----------------------------------------------------
def test_stream_rows_skips_repeated_header_and_counts_malformed(tmp_path):
    p = tmp_path / "Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv"
    rows = [flow_row(), flow_row(ts="14/02/2018 09:00:05"), flow_row(ts="14/02/2018 09:00:09")]
    header = ",".join(flow_row().keys())
    write_csv(p, rows, extra_lines={1: header, 2: "80,6,14/02/2018 09:00:01,1,2"})
    stats = {"rows": 0, "header_repeats": 0, "malformed_lines": 0, "empty_lines": 0,
             "reject_samples": [], "lines_total": 0}
    data = b"".join(ingest.stream_rows(p, "2018-02-14", stats))
    assert stats["rows"] == 3 and stats["header_repeats"] == 1 and stats["malformed_lines"] == 1
    assert ingest.verify_counts(stats)
    first = data.split(b"\n")[0]
    assert first.startswith(b"2018-02-14,2,80,6,14/02/2018 09:00:00,")  # gün + fiziksel satır no


# ---- eşikler ve metrikler ------------------------------------------------------------
def test_fa_budget_threshold_respects_budget():
    rng = np.random.default_rng(0)
    y = np.r_[np.zeros(10_000), np.ones(500)].astype(int)
    s = np.r_[rng.random(10_000), rng.random(500) + 0.5]
    for budget in (0.1, 1, 10):
        thr = threshold_for_fa_budget(y, s, budget)
        fp = np.sum((s >= thr) & (y == 0))
        assert fp <= budget / 1000 * 10_000


def test_best_f1_threshold_on_separable_data():
    y = np.array([0, 0, 0, 1, 1])
    s = np.array([0.1, 0.2, 0.3, 0.8, 0.9])
    thr = threshold_best_f1(y, s)
    assert binary_metrics(y, s, thr)["f1"] == 1.0


def test_binary_metrics_confusion_and_false_alarms():
    y = np.array([0, 0, 0, 0, 1, 1])
    s = np.array([0.9, 0.1, 0.1, 0.1, 0.9, 0.1])
    m = binary_metrics(y, s, 0.5)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 1, 1, 3)
    assert m["fa_per_1000_benign"] == pytest.approx(250.0)


def test_downsample_keeps_attacks_and_only_thins_benign():
    df = pl.DataFrame({"is_attack": [True] * 100 + [False] * 10_000, "x": range(10_100)})
    out = downsample(df, 1_000)
    assert out.height == 1_000 and int(out["is_attack"].sum()) == 100


def test_preprocessing_is_learned_on_train_only():
    rng = np.random.default_rng(1)
    Xtr = rng.normal(0, 1, (500, 3)); ytr = (Xtr[:, 0] > 0).astype(int)
    Xte = rng.normal(100, 1, (500, 3))
    pipe = make_logreg().fit(Xtr, ytr)
    before = pipe.named_steps["scale"].mean_.copy()
    pipe.predict_proba(Xte)  # test verisi hiçbir durumu değiştirmemeli
    assert np.allclose(pipe.named_steps["scale"].mean_, before)
    signed = np.sign(Xtr) * np.log1p(np.abs(Xtr))
    assert np.allclose(before, signed.mean(axis=0))
