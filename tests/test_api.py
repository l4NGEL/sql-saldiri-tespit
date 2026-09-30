"""API girdi doğrulama ve tahmin testleri (küçük sentetik model ile; DB gerekmez)."""
from __future__ import annotations

import joblib
import lightgbm as lgb
import numpy as np
import pytest
from fastapi.testclient import TestClient

from ids import api
from ids.columns import CANDIDATE_FEATURES, NUMERIC_FLOW_COLUMNS


@pytest.fixture
def client(tmp_path, monkeypatch):
    rng = np.random.default_rng(0)
    X = rng.random((400, len(CANDIDATE_FEATURES))).astype(np.float32)
    y = (X[:, CANDIDATE_FEATURES.index("w60_port_n")] > 0.5).astype(int)
    model = lgb.LGBMClassifier(n_estimators=20, verbose=-1).fit(X, y)
    card = {"model": "lightgbm", "features": CANDIDATE_FEATURES, "threshold": 0.5}
    path = tmp_path / "model.joblib"
    joblib.dump({"estimator": model, "card": card}, path)
    monkeypatch.setenv("IDS_MODEL_PATH", str(path))
    api.load_model.cache_clear()
    yield TestClient(api.app)
    api.load_model.cache_clear()


def valid_request() -> dict:
    flow = {c: 0.0 for c in NUMERIC_FLOW_COLUMNS}
    flow.update(dst_port=80, protocol=6, flow_duration=1000, tot_fwd_pkts=2, tot_bwd_pkts=1,
                totlen_fwd_pkts=100, totlen_bwd_pkts=50, fwd_pkt_len_max=60, fwd_pkt_len_min=40,
                flow_byts_s=150000.0, flow_pkts_s=3000.0, init_fwd_win_byts=8192, init_bwd_win_byts=-1)
    window = {"w10_port_n": 1, "w60_port_n": 3, "w60_all_n": 10, "w60_port_mean_fwd_pkts": 2.0,
              "w60_port_mean_duration_s": 0.5, "w60_port_noresp_share": 0.0, "w60_port_rst_share": 0.0}
    return {"flow": flow, "window": window}


def test_predict_returns_probability_threshold_and_decision(client):
    r = client.post("/predict", json=valid_request())
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0.0 <= body["attack_probability"] <= 1.0
    assert body["threshold"] == 0.5
    assert body["decision"] == ("ATTACK" if body["attack_probability"] >= 0.5 else "BENIGN")


def test_zero_duration_flow_accepts_null_rates(client):
    req = valid_request()
    req["flow"].update(flow_duration=0, flow_byts_s=None, flow_pkts_s=None)
    assert client.post("/predict", json=req).status_code == 200


@pytest.mark.parametrize("mutate", [
    lambda r: r["flow"].update(tot_fwd_pkts=-1),                 # negatif sayaç
    lambda r: r["flow"].update(protocol=99),                     # geçersiz protokol
    lambda r: r["flow"].update(dst_port=70000),                  # port aralık dışı
    lambda r: r["flow"].pop("flow_duration"),                    # eksik alan
    lambda r: r["flow"].update(label="Benign"),                  # sızıntı alanı: etiket
    lambda r: r["flow"].update(src_ip="1.2.3.4"),                # sızıntı alanı: IP
    lambda r: r["flow"].update(timestamp="14/02/2018 10:00:00"),  # sızıntı alanı: zaman
    lambda r: r["flow"].update(fwd_pkt_len_min=100),             # min > max
    lambda r: r["flow"].update(flow_iat_mean="abc"),             # sayı değil
    lambda r: r["window"].update(w60_port_n=20),                 # port sayısı > toplam
    lambda r: r["window"].update(w10_port_n=5),                  # 10 s sayısı > 60 s sayısı
    lambda r: r["window"].update(w60_port_mean_fwd_pkts=None),   # w60_port_n>0 iken ortalama yok
    lambda r: r["window"].update(w60_port_rst_share=1.5),        # oran > 1
])
def test_invalid_inputs_are_rejected(client, mutate):
    req = valid_request()
    mutate(req)
    assert client.post("/predict", json=req).status_code == 422


def test_model_card_endpoint(client):
    assert client.get("/model").json()["threshold"] == 0.5
    assert client.get("/health").json() == {"status": "ok"}
