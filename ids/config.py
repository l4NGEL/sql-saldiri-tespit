"""Ortak yapılandırma: yollar, veritabanı bağlantısı, veri seti dosyaları."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
DATA_DIR = Path(os.environ.get("IDS_DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
SAMPLE_DIR = DATA_DIR / "sample"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"

SEED = 20180214

S3_BASE = "https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com"
S3_PREFIX = "Processed Traffic Data for ML Algorithms/"

# Resmi kovadaki dosyalar (ListObjectsV2 ile doğrulandı) -> yakalama günü.
# Not: "Thuesday" yazım hatası resmi dosya adında böyle geçer.
DATASET_FILES: dict[str, str] = {
    "Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv": "2018-02-14",
    "Thursday-15-02-2018_TrafficForML_CICFlowMeter.csv": "2018-02-15",
    "Friday-16-02-2018_TrafficForML_CICFlowMeter.csv": "2018-02-16",
    "Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv": "2018-02-20",
    "Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv": "2018-02-21",
    "Thursday-22-02-2018_TrafficForML_CICFlowMeter.csv": "2018-02-22",
    "Friday-23-02-2018_TrafficForML_CICFlowMeter.csv": "2018-02-23",
    "Wednesday-28-02-2018_TrafficForML_CICFlowMeter.csv": "2018-02-28",
    "Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv": "2018-03-01",
    "Friday-02-03-2018_TrafficForML_CICFlowMeter.csv": "2018-03-02",
}


def db_name() -> str:
    return os.environ.get("IDS_DB", "ids")


def db_dsn(dbname: str | None = None) -> str:
    host = os.environ.get("IDS_PG_HOST", "localhost")
    port = os.environ.get("IDS_PG_PORT", "5434")
    user = os.environ.get("IDS_PG_USER", "ids")
    pwd = os.environ.get("IDS_PG_PASSWORD", "ids")
    return f"host={host} port={port} user={user} password={pwd} dbname={dbname or db_name()}"
