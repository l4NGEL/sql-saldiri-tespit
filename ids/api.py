"""FastAPI tahmin servisi: python -m ids serve

POST /predict  — tek bir akışın CICFlowMeter ölçümlerini + sensörün son 10/60 s pencere
                 özetlerini alır; saldırı olasılığı, eşik ve karar döner.
GET  /model    — modelin kartı (özellikler, eşikler, seçim yöntemi, test özeti)
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

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from .columns import NUMERIC_FLOW_COLUMNS
from .config import MODELS_DIR, db_name
from .features_py import derived, window_share

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


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    est, card = load_model()
    t0 = time.perf_counter()
    x = feature_vector(req, card["features"])
    p = float(est.predict_proba(x)[0, 1])
    dt = (time.perf_counter() - t0) * 1000
    thr = float(card["threshold"])
    return PredictResponse(attack_probability=p, threshold=thr,
                           decision="ATTACK" if p >= thr else "BENIGN",
                           model=card["model"], inference_ms=dt)
