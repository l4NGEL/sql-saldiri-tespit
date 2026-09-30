"""FastAPI tahmin servisi: python -m ids serve

POST /predict  — tek bir akışın CICFlowMeter ölçümlerini + sensörün son 10/60 s pencere
                 özetlerini alır; saldırı olasılığı, eşik ve karar döner.
POST /explain  — /predict ile aynı girdi; ek olarak kararı en çok etkileyen özellikler
GET  /model    — modelin kartı (özellikler, eşikler, seçim yöntemi, test özeti)
GET  /examples — test bölümünden gerçek örnek akışlar (data/demo/flows.json)
GET  /results  — deney sonuçlarının özeti (reports/results/*_ids.json)
GET  /         — web arayüzü (ids/web/index.html)
GET  /health

Girdi doğrulaması: bilinmeyen alan (ör. label, src_ip, timestamp) reddedilir; sayaç ve
uzunluklar negatif olamaz; protokol {0, 6, 17}; port 0-65535; pencere sayaçları tutarlı olmalı.
"""
from __future__ import annotations

import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import json

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from .columns import NUMERIC_FLOW_COLUMNS
from .config import MODELS_DIR, REPORTS_DIR, db_name
from .demo import DEMO_PATH
from .feature_labels import label as feature_label, source as feature_source
from .features_py import derived, window_share

WEB_DIR = Path(__file__).resolve().parent / "web"

NULLABLE_RATES = {"flow_byts_s", "flow_pkts_s"}
SENTINEL_MINUS_ONE = {"init_fwd_win_byts", "init_bwd_win_byts"}


def _flow_fields() -> dict:
    fields: dict = {
        "dst_port": (int, Field(ge=0, le=65535)),
        "protocol": (Literal[0, 6, 17], Field(description="0=HOPOPT/diğer, 6=TCP, 17=UDP")),
    }
    for c in NUMERIC_FLOW_COLUMNS:
        if c in NULLABLE_RATES:
            fields[c] = (Optional[float], Field(default=None, ge=0, description="süre 0 ise null"))
        elif c in SENTINEL_MINUS_ONE:
            fields[c] = (float, Field(ge=-1, description="-1 = gözlenmedi"))
        else:
            fields[c] = (float, Field(ge=0))
    return fields


_FlowBase = create_model("FlowBase", __config__=ConfigDict(extra="forbid"), **_flow_fields())


class WindowContext(BaseModel):
    """Sensör tarafında, bu akışın bittiği an itibarıyla SON 10/60 saniyede biten diğer akışlar."""
    model_config = ConfigDict(extra="forbid")
    w10_port_n: int = Field(ge=0, description="aynı hedef porta son 10 s'de biten akış sayısı")
    w60_port_n: int = Field(ge=0, description="aynı hedef porta son 60 s'de biten akış sayısı")
    w60_all_n: int = Field(ge=0, description="tüm portlar, son 60 s")
    w60_port_mean_fwd_pkts: Optional[float] = Field(default=None, ge=0)
    w60_port_mean_duration_s: Optional[float] = Field(default=None, ge=0)
    w60_port_noresp_share: Optional[float] = Field(default=None, ge=0, le=1)
    w60_port_rst_share: Optional[float] = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def _consistent(self):
        if self.w10_port_n > self.w60_port_n:
            raise ValueError("w10_port_n, w60_port_n'den büyük olamaz")
        if self.w60_port_n > self.w60_all_n:
            raise ValueError("w60_port_n, w60_all_n'den büyük olamaz")
        means = [self.w60_port_mean_fwd_pkts, self.w60_port_mean_duration_s,
                 self.w60_port_noresp_share, self.w60_port_rst_share]
        if self.w60_port_n > 0 and any(m is None for m in means):
            raise ValueError("w60_port_n > 0 iken pencere ortalamaları zorunludur")
        return self


class Flow(_FlowBase):  # type: ignore[misc, valid-type]
    @model_validator(mode="after")
    def _consistent(self):
        for lo, hi in [("fwd_pkt_len_min", "fwd_pkt_len_max"), ("bwd_pkt_len_min", "bwd_pkt_len_max"),
                       ("flow_iat_min", "flow_iat_max")]:
            if getattr(self, lo) > getattr(self, hi):
                raise ValueError(f"{lo} > {hi}")
        return self


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flow: Flow
    window: WindowContext


class PredictResponse(BaseModel):
    attack_probability: float
    threshold: float
    decision: Literal["ATTACK", "BENIGN"]
    model: str
    inference_ms: float


class Contribution(BaseModel):
    feature: str
    label: str
    source: Literal["CICFlowMeter", "SQL türetilmiş", "SQL pencere"]
    value: Optional[float]
    contribution: float  # log-odds; pozitif = saldırı yönüne iter


class ExplainResponse(PredictResponse):
    base_log_odds: float
    top: list[Contribution]


def model_path() -> Path:
    return Path(os.environ.get("IDS_MODEL_PATH", MODELS_DIR / db_name() / "model.joblib"))


@lru_cache(maxsize=1)
def load_model():
    p = model_path()
    if not p.exists():
        raise RuntimeError(f"Model bulunamadı: {p}. Önce `python -m ids train` çalıştırın.")
    bundle = joblib.load(p)
    return bundle["estimator"], bundle["card"]


def feature_vector(req: PredictRequest, features: list[str]) -> np.ndarray:
    f = req.flow.model_dump()
    w = req.window.model_dump()
    values = {**f, **derived(f), **w, "w60_port_share": window_share(w["w60_port_n"], w["w60_all_n"])}
    missing = [c for c in features if c not in values]
    if missing:
        raise HTTPException(500, f"Model özellikleri girdiden üretilemiyor: {missing}")
    return np.array([[np.nan if values[c] is None else values[c] for c in features]], dtype=np.float32)


app = FastAPI(title="SQL tabanlı ağ saldırısı tespiti", version="1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/model")
def model_card():
    return load_model()[1]


def _predict(req: PredictRequest):
    est, card = load_model()
    t0 = time.perf_counter()
    x = feature_vector(req, card["features"])
    p = float(est.predict_proba(x)[0, 1])
    dt = (time.perf_counter() - t0) * 1000
    thr = float(card["threshold"])
    resp = PredictResponse(attack_probability=p, threshold=thr,
                           decision="ATTACK" if p >= thr else "BENIGN",
                           model=card["model"], inference_ms=dt)
    return resp, x, est, card


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    return _predict(req)[0]


@app.post("/explain", response_model=ExplainResponse)
def explain(req: PredictRequest, top: int = 6):
    """LightGBM katkıları (pred_contrib, TreeSHAP): her özelliğin log-odds'a katkısı."""
    resp, x, est, card = _predict(req)
    if not hasattr(est, "booster_"):
        raise HTTPException(501, "Açıklama yalnızca LightGBM modeli için var")
    contrib = est.booster_.predict(x, pred_contrib=True)[0]
    feats = card["features"]
    order = np.argsort(-np.abs(contrib[:-1]))[:max(1, min(top, len(feats)))]
    items = [Contribution(feature=feats[i], label=feature_label(feats[i]), source=feature_source(feats[i]),
                          value=None if np.isnan(x[0, i]) else float(x[0, i]),
                          contribution=float(contrib[i])) for i in order]
    return ExplainResponse(**resp.model_dump(), base_log_odds=float(contrib[-1]), top=items)


@app.get("/examples")
def examples():
    if not DEMO_PATH.exists():
        raise HTTPException(404, f"{DEMO_PATH} yok. `python -m ids demo-data` çalıştırın.")
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def _load_result(name: str) -> dict | None:
    p = REPORTS_DIR / "results" / f"{name}_ids.json"
    return json.loads(p.read_text(encoding="utf-8"))["results"] if p.exists() else None


def _op(ev: dict) -> dict:
    o = ev["operating_points"]["best_f1_val"]
    return {"pr_auc": ev["pr_auc"], "precision": o["precision"], "recall": o["recall"], "f1": o["f1"],
            "fa_per_1000": o["fa_per_1000_benign"], "rows": ev["rows"], "prevalence": ev.get("prevalence")}


@lru_cache(maxsize=1)
def results_summary() -> dict:
    """Tam veri deney sonuçlarından arayüz için küçük bir özet (test bölümü, doğrulamada seçilen eşik)."""
    out: dict = {}
    if main := _load_result("main"):
        out["methods"] = [{"name": k, **_op(v["test"]),
                           "unseen_pr_auc": v.get("test_unseen_feature_vectors", {}).get("pr_auc")}
                          for k, v in main["models"].items()]
        out["per_label"] = main["models"]["lightgbm"]["test"]["operating_points"]["best_f1_val"]["per_label"]
    if lodo := _load_result("lodo"):
        out["lodo"] = [{"day": d, "labels": r["held_out_attack_labels"],
                        "seen_in_train": bool(r["held_out_labels_seen_in_train"]), **_op(r["test"])}
                       for d, r in lodo.items() if isinstance(r, dict) and "test" in r]
    if abl := _load_result("ablation"):
        out["ablation"] = [{"name": k, "n_features": r["n_features"], **_op(r["test"]),
                            "unseen_pr_auc": r["test_unseen_feature_vectors"]["pr_auc"]}
                           for k, r in abl.items() if isinstance(r, dict) and "test" in r]
    if rs := _load_result("random_split"):
        out["random_split"] = [{"name": k, **_op(r["test"])} for k, r in rs.items()
                               if isinstance(r, dict) and "test" in r]
    if mc := _load_result("multiclass"):
        out["multiclass_macro_f1"] = mc["macro_f1"]
    return out


@app.get("/results")
def results():
    return results_summary()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})
