"""Tam CSV'lerden küçük, etiket-tabakalı örnek dosyalar üretir (data/sample/*.csv.gz).

Örnek yalnızca veri hattını ve testleri hızlı çalıştırmak içindir; sınıf oranları
bilerek değiştirilmiştir (her saldırı etiketinden en fazla N satır), bu yüzden örnek
üzerindeki metrikler tam veri sonuçları yerine geçmez.

Dosya tek geçişte akış hâlinde okunur (etiket başına rezervuar örnekleme); seçilen
satırlar dosyadaki özgün sıralarıyla ve özgün başlıkla yazılır.
"""
from __future__ import annotations

import gzip
import random
from pathlib import Path

from .config import RAW_DIR, SAMPLE_DIR, SEED, DATASET_FILES

BENIGN_PER_FILE = 3000
ATTACK_PER_LABEL = 600


def sample_file(path: Path, out_dir: Path) -> Path:
    rng = random.Random(f"{SEED}-{path.name}")
    reservoirs: dict[bytes, list[tuple[int, bytes]]] = {}
    seen: dict[bytes, int] = {}
    with open(path, "rb") as fh:
        header = fh.readline()
        for line_no, line in enumerate(fh, start=2):
            if line.strip() == header.strip():
                continue
            label = line.rstrip(b"\r\n").rsplit(b",", 1)[-1]
            cap = BENIGN_PER_FILE if label == b"Benign" else ATTACK_PER_LABEL
            n = seen.get(label, 0) + 1
            seen[label] = n
            res = reservoirs.setdefault(label, [])
            if len(res) < cap:
                res.append((line_no, line))
            else:
                j = rng.randrange(n)
                if j < cap:
                    res[j] = (line_no, line)
    rows = sorted((r for res in reservoirs.values() for r in res), key=lambda r: r[0])
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (path.name + ".gz")
    with gzip.open(out, "wb", compresslevel=9) as gz:
        gz.write(header)
        for _, line in rows:
            gz.write(line if line.endswith(b"\n") else line + b"\n")
    counts = {k.decode(): min(len(v), 10**9) for k, v in reservoirs.items()}
    print(f"  {path.name}: {len(rows):,} satır örneklendi {counts}", flush=True)
    return out


def run(files: list[Path] | None = None) -> None:
    files = files or [RAW_DIR / n for n in DATASET_FILES if (RAW_DIR / n).exists()]
    for f in files:
        if (SAMPLE_DIR / (f.name + ".gz")).exists():
            print(f"  mevcut: {f.name}.gz")
            continue
        sample_file(f, SAMPLE_DIR)
