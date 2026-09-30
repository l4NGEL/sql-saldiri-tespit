"""Ortak test yardımcıları.

Veritabanı gerektiren testler, PostgreSQL erişilemezse atlanır (docker compose up -d).
Testler ayrı veritabanları kullanır (ids_test, ids_test_sample); tam veri 'ids' DB'sine dokunulmaz.
Tam veri testleri `-m full` ile ayrıca çalıştırılır (varsayılan test komutunun parçası değildir).
"""
from __future__ import annotations

import os

import psycopg
import pytest

from ids.columns import FLOW_COLUMNS
from ids.config import db_dsn

CSV_HEADER = [c for c, _ in FLOW_COLUMNS]


def pytest_configure(config):
    config.addinivalue_line("markers", "db: PostgreSQL gerektirir")
    config.addinivalue_line("markers", "full: tam veri seti gerektirir (varsayılan olarak çalışmaz)")


def pytest_collection_modifyitems(config, items):
    if "full" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="tam veri testi: `pytest -m full` ile çalıştırın")
    for it in items:
        if "full" in it.keywords:
            it.add_marker(skip)


def pg_available() -> bool:
    try:
        with psycopg.connect(db_dsn("ids"), connect_timeout=3):
            return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not pg_available(), reason="PostgreSQL erişilemiyor")


def recreate_db(name: str) -> None:
    with psycopg.connect(db_dsn("ids"), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{name}"')


@pytest.fixture
def use_db(monkeypatch):
    def _use(name: str, fresh: bool = True):
        if fresh:
            recreate_db(name)
        monkeypatch.setenv("IDS_DB", name)
        return name
    return _use


def flow_row(ts: str = "14/02/2018 09:00:00", label: str = "Benign", **kw) -> dict:
    """CICFlowMeter biçiminde, tutarlı değerlere sahip varsayılan bir akış satırı."""
    row = {c: "0" for c in CSV_HEADER}
    row.update({
        "Dst Port": "80", "Protocol": "6", "Timestamp": ts, "Flow Duration": "1000",
        "Tot Fwd Pkts": "2", "Tot Bwd Pkts": "1", "TotLen Fwd Pkts": "100", "TotLen Bwd Pkts": "50",
        "Fwd Pkt Len Max": "60", "Fwd Pkt Len Min": "40", "Fwd Pkt Len Mean": "50",
        "Bwd Pkt Len Max": "50", "Bwd Pkt Len Min": "50", "Bwd Pkt Len Mean": "50",
        "Flow Byts/s": "150000", "Flow Pkts/s": "3000", "Flow IAT Mean": "500", "Flow IAT Std": "10",
        "Flow IAT Max": "510", "Flow IAT Min": "490", "Fwd Header Len": "64", "Bwd Header Len": "32",
        "Subflow Fwd Pkts": "2", "Subflow Bwd Pkts": "1", "Init Fwd Win Byts": "8192",
        "Init Bwd Win Byts": "-1", "Idle Mean": "0", "Active Mean": "0", "Label": label,
    })
    for k, v in kw.items():
        row[k] = str(v)
    return row


def write_csv(path, rows, extra_lines: dict[int, str] | None = None) -> None:
    """rows: dict listesi; extra_lines: {sıra: ham satır} (tekrar başlık / bozuk satır eklemek için)."""
    lines = [",".join(CSV_HEADER)]
    for i, r in enumerate(rows):
        if extra_lines and i in extra_lines:
            lines.append(extra_lines[i])
        lines.append(",".join(r[c] for c in CSV_HEADER))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(autouse=True)
def _utf8(monkeypatch):
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    yield
    os.environ.pop("IDS_MODEL_PATH", None)
