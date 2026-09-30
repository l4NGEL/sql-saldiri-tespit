"""Servis anı için satır düzeyi özelliklerin Python aynası.

EĞİTİM verisi bu modülle ÜRETİLMEZ; eğitim özellikleri sql/20_features.sql'den gelir.
API'nin veritabanına bağlı olmadan tek bir akışı puanlayabilmesi için aynı ifadeler
burada tekrarlanır; tests/test_feature_parity.py iki uygulamanın aynı sonucu verdiğini
PostgreSQL'e karşı doğrular (eğitim/servis kayması denetimi).
"""
from __future__ import annotations

import math


def _div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def derived(f: dict) -> dict:
    fwd_len, bwd_len = f["totlen_fwd_pkts"], f["totlen_bwd_pkts"]
    fwd_n, bwd_n = f["tot_fwd_pkts"], f["tot_bwd_pkts"]
    return {
        "duration_s": f["flow_duration"] / 1e6,
        "fwd_bytes_per_pkt": _div(fwd_len, fwd_n),
        "bwd_bytes_per_pkt": _div(bwd_len, bwd_n),
        "bwd_fwd_byte_ratio": bwd_len / (fwd_len + 1),
        "bwd_fwd_pkt_ratio": _div(bwd_n, fwd_n),
        "fwd_payload_share": _div(fwd_len, fwd_len + f["fwd_header_len"]),
        "log_total_bytes": math.log(1 + fwd_len + bwd_len),
        "flow_iat_cv": _div(f["flow_iat_std"], f["flow_iat_mean"]),
        "active_idle_ratio": f["active_mean"] / (f["idle_mean"] + 1),
        "no_response": int(bwd_n == 0),
        "zero_duration": int(f["flow_duration"] == 0),
        "well_known_port": int(f["dst_port"] < 1024),
    }


def window_share(w60_port_n: int, w60_all_n: int):
    """SQL: (count(*) OVER w60p - 1) / nullif(count(*) OVER w60a - 1, 0)"""
    return _div(float(w60_port_n), float(w60_all_n))
