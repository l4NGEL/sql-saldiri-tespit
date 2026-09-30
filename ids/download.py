"""CSE-CIC-IDS2018 işlenmiş akış CSV'lerini resmi AWS S3 kovasından indirir.

- Kimlik doğrulama gerekmez (herkese açık kova, ca-central-1).
- Dosya boyutu S3 listesinden alınır; yarım kalan indirme Range ile devam eder.
- Boyut tutmazsa hata verir; tamamlanmış dosyalar yeniden indirilmez.
"""
from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .config import DATASET_FILES, RAW_DIR, S3_BASE, S3_PREFIX


def list_remote() -> dict[str, int]:
    url = f"{S3_BASE}/?list-type=2&prefix={urllib.parse.quote(S3_PREFIX)}"
    body = urllib.request.urlopen(url, timeout=60).read().decode()
    out = {}
    for block in body.split("<Contents>")[1:]:
        key = re.search(r"<Key>(.*?)</Key>", block).group(1)
        size = int(re.search(r"<Size>(\d+)</Size>", block).group(1))
        name = key[len(S3_PREFIX):]
        if name:
            out[name] = size
    return out


def download_file(name: str, size: int, dest_dir: Path) -> Path:
    dest = dest_dir / name
    part = dest.with_suffix(dest.suffix + ".part")
    if dest.exists() and dest.stat().st_size == size:
        print(f"  mevcut: {name}")
        return dest
    have = part.stat().st_size if part.exists() else 0
    url = f"{S3_BASE}/{urllib.parse.quote(S3_PREFIX + name)}"
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp, open(part, "ab") as fh:
        while chunk := resp.read(8 << 20):
            fh.write(chunk)
    got = part.stat().st_size
    if got != size:
        raise RuntimeError(f"{name}: boyut uyuşmuyor ({got} != {size}); komutu tekrar çalıştırın")
    part.replace(dest)
    dt = time.perf_counter() - t0
    print(f"  indirildi: {name} ({size / 1e6:,.0f} MB, {dt:,.0f} s)", flush=True)
    return dest


def run(only: list[str] | None = None) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    remote = list_remote()
    missing = set(DATASET_FILES) - set(remote)
    if missing:
        raise RuntimeError(f"Kovada beklenen dosyalar yok: {sorted(missing)}")
    names = [n for n in DATASET_FILES if not only or any(o in n for o in only)]
    total = sum(remote[n] for n in names)
    print(f"{len(names)} dosya, toplam {total / 1e9:.2f} GB -> {RAW_DIR}", flush=True)
    for n in names:
        for attempt in range(5):
            try:
                download_file(n, remote[n], RAW_DIR)
                break
            except Exception as exc:  # ağ kesintisi: bir sonraki denemede Range ile devam eder
                print(f"  hata ({attempt + 1}/5): {exc}", flush=True)
                time.sleep(5)
        else:
            raise RuntimeError(f"{n} indirilemedi")
