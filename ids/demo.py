"""Arayüz için örnek akışlar: python -m ids demo-data

Zamansal ayrımın TEST bölümünden, her etiketten hash(flow_id) sırasıyla ilk birkaç akışı alır
(elle seçim yok: modelin yanıldığı akışlar da doğal oranında listeye girer) ve
data/demo/flows.json dosyasına yazar. Arayüz ve API bu dosyayı okur; veritabanı gerekmez.
"""
from __future__ import annotations

import json
import math

from . import db, export
from .columns import NUMERIC_FLOW_COLUMNS
from .config import ROOT

DEMO_PATH = ROOT / "data" / "demo" / "flows.json"
WINDOW = ["w10_port_n", "w60_port_n", "w60_all_n", "w60_port_mean_fwd_pkts", "w60_port_mean_duration_s",
          "w60_port_noresp_share", "w60_port_rst_share"]
PER_LABEL = {"Benign": 16}
DEFAULT_PER_LABEL = 3


def _clean(v):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return None
    return v


def to_request(row: dict) -> dict:
    """Bir eğitim-seti satırını /predict gövdesine çevirir (temizlikte NULL'lanan ölçümler dahil)."""
    flow = {c: _clean(row[c]) for c in ["dst_port", "protocol"] + NUMERIC_FLOW_COLUMNS}
    for k, v in flow.items():
        if v is None and k not in ("flow_byts_s", "flow_pkts_s"):
            flow[k] = 0.0
    return {"flow": flow, "window": {k: _clean(row[k]) for k in WINDOW}}


def run(per_label: int = DEFAULT_PER_LABEL) -> None:
    base = export.training_query(where="t.split_temporal = 'test'")
    sql = f"""
        SELECT x.*, c.ts::text AS ts
        FROM (SELECT t.*, row_number() OVER (PARTITION BY t.label ORDER BY hashint8(t.flow_id)) AS rn
              FROM ({base}) t) x
        JOIN clean.flows c ON c.capture_day = x.capture_day AND c.flow_id = x.flow_id
        WHERE x.rn <= CASE WHEN x.label = 'Benign' THEN {PER_LABEL['Benign']} ELSE {int(per_label)} END
        ORDER BY x.capture_day, c.ts"""
    with db.connect() as conn:
        cur = conn.execute(sql)
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    out = [{"id": int(r["flow_id"]), "label": r["label"], "is_attack": bool(r["is_attack"]),
            "day": str(r["capture_day"]), "ts": r["ts"],
            "seen_in_train": bool(r["fv_seen_in_train_temporal"]), **to_request(r)} for r in rows]
    DEMO_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEMO_PATH.write_text(json.dumps({"source": "CSE-CIC-IDS2018, zamansal ayrımın test bölümü",
                                     "flows": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {len(out)} akış -> {DEMO_PATH}")
