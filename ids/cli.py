"""Komut satırı: python -m ids <komut>.

Tam veri:   download -> ingest -> clean -> features -> export -> train -> evaluate
Örnek veri: aynı komutlar --sample ile (IDS_DB=ids_sample önerilir)
"""
from __future__ import annotations

import argparse
import os


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m ids")
    p.add_argument("--db", help="Veritabanı adı (varsayılan IDS_DB ya da 'ids')")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("download", help="Resmi S3 kovasından CSV indir")
    d.add_argument("--only", nargs="*", help="Dosya adında geçen parça (ör. 14-02)")

    i = sub.add_parser("ingest", help="CSV -> raw.flows (COPY, parçalı)")
    i.add_argument("--sample", action="store_true", help="data/sample altındaki küçük örnekleri yükle")
    i.add_argument("--only", nargs="*")
    i.add_argument("--delete-csv", action="store_true",
                   help="Yükleme doğrulandıktan sonra CSV'yi sil (disk tasarrufu)")

    sub.add_parser("clean", help="Denetim + temizleme: raw -> clean (SQL)")
    sub.add_parser("features", help="SQL özellik üretimi + ayrımlar + sızıntı denetimleri")

    e = sub.add_parser("export", help="SQL eğitim sorgusunu Parquet'e aktar")
    e.add_argument("--scheme", default="temporal", choices=["temporal", "random"])

    t = sub.add_parser("train", help="Modelleri eğit, eşiği doğrulamada seç, testte değerlendir")
    t.add_argument("--experiment", default="main",
                   help="main, random_split, ablation, multiclass, lodo, all ya da virgüllü liste (ör. multiclass,lodo)")
    t.add_argument("--quick", action="store_true", help="Küçük örnek veri için hızlı ayarlar")

    b = sub.add_parser("bench", help="Performans karşılaştırmaları + EXPLAIN ANALYZE + API gecikmesi")
    b.add_argument("--only", choices=["api"], help="Yalnızca API gecikmesini ölç")
    sub.add_parser("report", help="meta şemasından Markdown raporları üret")

    s = sub.add_parser("serve", help="FastAPI tahmin servisini başlat")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)

    sub.add_parser("make-sample", help="Tam CSV'lerden küçük, etiket-tabakalı örnek üret")
    sub.add_parser("demo-data", help="Arayüz için test bölümünden örnek akışlar (data/demo/flows.json)")

    args = p.parse_args()
    if args.db:
        os.environ["IDS_DB"] = args.db

    if args.cmd == "download":
        from . import download
        download.run(args.only)
    elif args.cmd == "ingest":
        from . import ingest
        ingest.run(sample=args.sample, only=args.only, delete_csv=args.delete_csv)
    elif args.cmd == "clean":
        from . import pipeline
        pipeline.clean()
    elif args.cmd == "features":
        from . import pipeline
        pipeline.features()
    elif args.cmd == "export":
        from . import export
        export.run(args.scheme)
    elif args.cmd == "train":
        from . import train
        train.run(args.experiment, quick=args.quick)
    elif args.cmd == "bench":
        from . import bench
        bench.run(args.only)
    elif args.cmd == "report":
        from . import report
        report.run()
    elif args.cmd == "serve":
        import uvicorn
        uvicorn.run("ids.api:app", host=args.host, port=args.port)
    elif args.cmd == "demo-data":
        from . import demo
        demo.run()
    elif args.cmd == "make-sample":
        from . import sample
        sample.run()


if __name__ == "__main__":
    main()
