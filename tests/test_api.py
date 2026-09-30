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


def test_explain_contributions_add_up_to_model_logit(client):
    """Açıklama modelin kendisidir: tüm katkılar + başlangıç = olasılığın logit'i."""
    body = client.post(f"/explain?top={len(CANDIDATE_FEATURES)}", json=valid_request()).json()
    p = body["attack_probability"]
    total = body["base_log_odds"] + sum(t["contribution"] for t in body["top"])
    assert total == pytest.approx(np.log(p / (1 - p)), abs=1e-4)
    mags = [abs(t["contribution"]) for t in body["top"]]
    assert mags == sorted(mags, reverse=True)
    assert body["decision"] == client.post("/predict", json=valid_request()).json()["decision"]


def test_demo_flows_are_valid_api_requests(client):
    flows = client.get("/examples").json()["flows"]
    assert len(flows) > 20 and {f["is_attack"] for f in flows} == {True, False}
    for f in flows:
        r = client.post("/predict", json={"flow": f["flow"], "window": f["window"]})
        assert r.status_code == 200, (f["id"], r.text)


def test_ui_and_results_summary_are_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Ağ Saldırısı Tespiti" in r.text
    s = client.get("/results").json()
    assert {m["name"] for m in s["methods"]} >= {"majority", "lightgbm"}
    assert len(s["lodo"]) == 10


def test_committed_model_loads_and_uses_no_forbidden_fields():
    from ids.columns import FORBIDDEN_FEATURES
    from ids.config import MODELS_DIR
    bundle = joblib.load(MODELS_DIR / "ids" / "model.joblib")
    feats = bundle["card"]["features"]
    assert set(feats) <= set(CANDIDATE_FEATURES)
    assert not set(feats) & set(FORBIDDEN_FEATURES)
    assert bundle["estimator"].n_features_in_ == len(feats)
