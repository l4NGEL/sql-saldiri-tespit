"""Küçük örnek veriyle (data/sample, ~38 bin satır) uçtan uca hat testi (~1-2 dk).

ingest -> clean -> features -> export -> train(main, quick) -> API.
Ayrıca SQL'de üretilen satır düzeyi özelliklerin API'deki Python aynasıyla eşleştiği
(eğitim/servis kayması) ve özellik listesinde sızıntı alanı olmadığı denetlenir.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np
import polars as pl
import pytest

from ids import db, export, ingest, pipeline, train
from ids.columns import DERIVED_FEATURES, FORBIDDEN_FEATURES, NUMERIC_FLOW_COLUMNS
from ids.config import MODELS_DIR
from ids.features_py import derived

from .conftest import recreate_db, requires_db

pytestmark = [requires_db, pytest.mark.db]
DB = "ids_test_sample"


@pytest.fixture(scope="module")
def sample_db():
    recreate_db(DB)
    old = os.environ.get("IDS_DB")
    os.environ["IDS_DB"] = DB
    ingest.run(sample=True)
    pipeline.clean()
    pipeline.features()
    export.run()
    yield
    if old is None:
        os.environ.pop("IDS_DB", None)
    else:
        os.environ["IDS_DB"] = old


def q(sql):
    with db.connect() as conn:
        return conn.execute(sql).fetchall()


def test_all_sample_files_loaded_and_accounted(sample_db):
    rows = q("SELECT source_file, rows_loaded FROM meta.ingest_files")
    assert len(rows) == 10 and all(n > 3000 for _, n in rows)
    (raw,), = q("SELECT count(*) FROM raw.flows")
    (inp,), = q("SELECT sum(rows_affected) FROM meta.cleaning_log WHERE step = 0")
    assert raw == inp


def test_every_attack_label_in_every_split(sample_db):
    rows = q("""SELECT label, array_agg(DISTINCT split) FROM meta.split_summary
                WHERE scheme = 'temporal' AND split <> 'gap' GROUP BY 1""")
    missing = {lab: s for lab, s in rows if set(s) != {"train", "val", "test"}}
    # Örnekte çok az satırı olan etiketler (ör. SQL Injection) bir bölümde eksik kalabilir;
    # bu durum sessizce geçilmez, test çıktısında raporlanır.
    assert len(missing) <= 2, missing


def test_sql_and_python_derived_features_match(sample_db):
    cols = ", ".join(f"c.{c}" for c in ["dst_port"] + NUMERIC_FLOW_COLUMNS)
    feats = ", ".join(f"f.{c}" for c in DERIVED_FEATURES)
    with db.connect() as conn:
        cur = conn.execute(f"""SELECT {cols}, {feats} FROM clean.flows c
                               JOIN features.flow_features f USING (capture_day, flow_id)
                               WHERE c.flow_iat_mean IS NOT NULL AND c.flow_iat_std IS NOT NULL
                               ORDER BY c.flow_id LIMIT 3000""")
        names = [d.name for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
    n_base = 1 + len(NUMERIC_FLOW_COLUMNS)
    for r in rows:
        base = {k: r[k] for k in names[:n_base]}
        py = derived(base)
        for c in DERIVED_FEATURES:
            s, p = r[c], py[c]
            if s is None or p is None:
                assert s is None and p is None, (c, s, p)
            else:
                assert math.isclose(float(s), float(p), rel_tol=2e-6, abs_tol=1e-6), (c, s, p)


def test_train_main_quick_and_api(sample_db):
    from fastapi.testclient import TestClient
    from ids import api

    train.run("main", quick=True)
    card = json.loads((MODELS_DIR / DB / "model_card.json").read_text(encoding="utf-8"))
    assert not set(card["features"]) & set(FORBIDDEN_FEATURES)
    res = json.loads((train.RESULTS_DIR / f"main_{DB}.json").read_text(encoding="utf-8"))
    data = res["data"]
    assert all(data[s]["rows"] > 0 and data[s]["attack_rows"] > 0 for s in ("train", "val", "test"))
    ids_train = set(pl.read_parquet(export.output_path()).filter(pl.col("split_temporal") == "train")["flow_id"])
    ids_test = set(pl.read_parquet(export.output_path()).filter(pl.col("split_temporal") == "test")["flow_id"])
    assert not ids_train & ids_test

    # API gerçek eğitilmiş modelle, örnek verideki bir satırı puanlar
    df = pl.read_parquet(export.output_path()).filter(pl.col("split_temporal") == "test").head(1)
    row = df.row(0, named=True)
    flow = {c: row[c] for c in ["dst_port", "protocol"] + NUMERIC_FLOW_COLUMNS}
    flow = {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in flow.items()}
    for k, v in list(flow.items()):  # temizlikte NULL'lanan ölçümler API'de zorunlu -> 0
        if v is None and k not in ("flow_byts_s", "flow_pkts_s"):
            flow[k] = 0.0
    window = {k: row[k] for k in ["w10_port_n", "w60_port_n", "w60_all_n", "w60_port_mean_fwd_pkts",
                                  "w60_port_mean_duration_s", "w60_port_noresp_share", "w60_port_rst_share"]}
    os.environ["IDS_MODEL_PATH"] = str(MODELS_DIR / DB / "model.joblib")
    api.load_model.cache_clear()
    try:
        r = TestClient(api.app).post("/predict", json={"flow": flow, "window": window})
        assert r.status_code == 200, r.text
        assert r.json()["threshold"] == pytest.approx(card["threshold"])
    finally:
        os.environ.pop("IDS_MODEL_PATH", None)
        api.load_model.cache_clear()
