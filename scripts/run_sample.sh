#!/usr/bin/env bash
# Küçük örnek veriyle (data/sample, repoda) tüm hattı çalıştırır. ~2 dk.
set -euo pipefail
export IDS_DB=ids_sample PYTHONIOENCODING=utf-8
PY=${PY:-.venv/bin/python}; [ -x "$PY" ] || PY=.venv/Scripts/python
$PY -m ids ingest --sample
$PY -m ids clean
$PY -m ids features
$PY -m ids export
$PY -m ids train --experiment all --quick
$PY -m ids report
