#!/usr/bin/env bash
# Tam CSE-CIC-IDS2018 işlenmiş akış verisiyle tüm hat. Disk/RAM gereksinimi için README.
# CSV dosyaları yüklenip satır sayıları doğrulandıktan sonra silinir (--delete-csv);
# saklamak istiyorsanız bu bayrağı kaldırın (+6,9 GB).
set -euo pipefail
export IDS_DB=ids PYTHONIOENCODING=utf-8
PY=${PY:-.venv/bin/python}; [ -x "$PY" ] || PY=.venv/Scripts/python
$PY -m ids download
$PY -m ids make-sample
$PY -m ids ingest --delete-csv
$PY -m ids clean
$PY -m ids features
$PY -m ids export
$PY -m ids train --experiment all
$PY -m ids bench
$PY -m ids report
