"""Özellik hattının PySpark sürümü + Spark üzerinde toplu skorlama.

sql/20_features.sql'deki 20 özelliği (12 satır düzeyi + 8 zaman penceresi) gün bölümlü
Parquet lake'ten (ids/lake.py) üretir. Amaç SQL'in yerini almak değil, aynı tanımın
dağıtık bir motorda da birebir aynı sonucu verdiğini göstermek: `parity` adımı her
özelliği SQL çıktısıyla satır satır karşılaştırır.

Pencere özellikleri ve neden önek toplamı:
  SQL'deki `RANGE BETWEEN interval '60 s' PRECEDING AND CURRENT ROW` Spark'ta doğrudan
  `rangeBetween(-60e6, 0)` olarak yazılabilir (`windows_naive`). Ancak Spark sınırlı kayan
  çerçevede toplamı her satırda pencerenin tamamı üzerinden yeniden hesaplar: maliyet
  O(n * pencere boyu). DoS günlerinde tek porta 60 sn'de 100 binin üzerinde akış düştüğü
  için bu, tam veride pratikte bitmez. `windows_prefix` aynı sonucu önek toplamlarıyla
  O(n log n)'de üretir:
      pencere(t) = önek(bitiş <= t) - önek(bitiş < t - L)
  Her akış için t - L anında bir "sonda" satırı eklenir; veri ve sonda satırları tek bir
  sıralamada birleştirilir (anahtar: veri 2t+1, sonda 2(t-L); böylece veri satırı eşit
  zamanlı tüm akışları kapsar, sonda ise t-L anındakileri dışlar), ardından
  `UNBOUNDED PRECEDING .. CURRENT ROW` birikimli toplamı (Spark'ta artımlı, O(1)/satır) alınır.

Çalıştırma: Dockerfile.spark (Linux + JDK 17). Windows'ta Spark yerel dosya sistemine
Hadoop'un winutils/hadoop.dll ikilileri olmadan erişemiyor; bu yüzden işler konteynerde koşar:
    docker compose run --rm spark python -m ids spark features
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from .columns import DERIVED_FEATURES, WINDOW_FEATURES
from .config import MODELS_DIR, REPORTS_DIR, db_name
from .lake import INT_FEATURES, clean_dir, lake_dir, sql_features_dir

FEATURES = DERIVED_FEATURES + WINDOW_FEATURES
RESULTS_DIR = REPORTS_DIR / "results"


def features_dir() -> Path:
    return lake_dir() / "spark_features"


def scores_dir() -> Path:
    return lake_dir() / "scores"


# ---- oturum ------------------------------------------------------------------------------
def session(app: str = "ids"):
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    from pyspark.sql import SparkSession
    spark = (SparkSession.builder.master(os.environ.get("IDS_SPARK_MASTER", "local[*]")).appName(app)
             .config("spark.driver.memory", os.environ.get("IDS_SPARK_MEMORY", "8g"))
             .config("spark.sql.shuffle.partitions", os.environ.get("IDS_SPARK_PARTITIONS", "64"))
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.execution.arrow.pyspark.enabled", "true")
             .config("spark.ui.enabled", "false")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def read_clean(spark, path: Path | None = None):
    from pyspark.sql import functions as F
    df = spark.read.parquet(str(path or clean_dir()))
    return df.withColumn("capture_day", F.col("capture_day").cast("string"))


# ---- satır düzeyi özellikler --------------------------------------------------------------
def derived(df):
    """sql/20_features.sql satır düzeyi ifadeleri. Spark'ta 0'a bölme NULL döner; SQL'deki
    nullif(..., 0) ile aynı sonuç için yine de açıkça yazıldı."""
    from pyspark.sql import functions as F
    c = F.col

    def div(a, b):
        return F.when(b != 0, a / b)

    fwd_len, bwd_len, fwd_n, bwd_n = c("totlen_fwd_pkts"), c("totlen_bwd_pkts"), c("tot_fwd_pkts"), c("tot_bwd_pkts")
    exprs = {
        "duration_s": c("flow_duration") / 1e6,
        "fwd_bytes_per_pkt": div(fwd_len, fwd_n),
        "bwd_bytes_per_pkt": div(bwd_len, bwd_n),
        "bwd_fwd_byte_ratio": bwd_len / (fwd_len + 1),
        "bwd_fwd_pkt_ratio": div(bwd_n, fwd_n),
        "fwd_payload_share": div(fwd_len, fwd_len + c("fwd_header_len")),
        "log_total_bytes": F.log(1 + fwd_len + bwd_len),
        "flow_iat_cv": div(c("flow_iat_std"), c("flow_iat_mean")),
        "active_idle_ratio": c("active_mean") / (c("idle_mean") + 1),
        "no_response": (bwd_n == 0).cast("int"),
        "zero_duration": (c("flow_duration") == 0).cast("int"),
        "well_known_port": (c("dst_port") < 1024).cast("int"),
    }
    return df.withColumns({k: v.cast("int" if k in INT_FEATURES else "float") for k, v in exprs.items()})


# ---- pencere özellikleri ------------------------------------------------------------------
PORT_KEYS = ["capture_day", "dst_port"]
DAY_KEYS = ["capture_day"]
W60 = 60_000_000
W10 = 10_000_000


def _window_inputs(df):
    """Pencerede toplanan değerler; SQL'deki `::bigint` (yuvarla) ve `(x = 0)::int` dönüşümleri."""
    from pyspark.sql import functions as F
    return df.select(
        "flow_id", "capture_day", "dst_port", "end_us",
        F.bround("tot_fwd_pkts").cast("long").alias("v_fwd"),
        F.bround("flow_duration").cast("long").alias("v_dur"),
        (F.col("tot_bwd_pkts") == 0).cast("long").alias("v_noresp"),
        (F.col("rst_flag_cnt") > 0).cast("long").alias("v_rst"),
    )


SUM_COLS = ["v_fwd", "v_dur", "v_noresp", "v_rst"]


def _finish(w):
    """Ham pencere toplamlarından (akışın kendisi DAHİL) 8 özelliği üretir; akışın kendi katkısı
    SQL'deki gibi çıkarılır (count - 1, sum - kendi değeri)."""
    from pyspark.sql import functions as F
    c = F.col
    n60 = c("n60p") - 1

    def mean(s, own, scale=1.0):
        return F.when(n60 != 0, (c(s) - c(own)) / scale / n60)

    return w.select(
        "flow_id",
        (c("n10p") - 1).cast("int").alias("w10_port_n"),
        n60.cast("int").alias("w60_port_n"),
        (c("n60a") - 1).cast("int").alias("w60_all_n"),
        F.when(c("n60a") - 1 != 0, n60 / (c("n60a") - 1)).cast("float").alias("w60_port_share"),
        mean("s_fwd", "v_fwd").cast("float").alias("w60_port_mean_fwd_pkts"),
        mean("s_dur", "v_dur", 1e6).cast("float").alias("w60_port_mean_duration_s"),
        mean("s_noresp", "v_noresp").cast("float").alias("w60_port_noresp_share"),
        mean("s_rst", "v_rst").cast("float").alias("w60_port_rst_share"),
    )


def windows_naive(df):
    """Doğrudan çeviri: rangeBetween. Anlamca SQL'in birebir aynısı; büyük veride çok yavaş.
    Yalnızca küçük veride kıyas (doğruluk kâhini ve süre karşılaştırması) için."""
    from pyspark.sql import Window, functions as F
    v = _window_inputs(df)
    wp10 = Window.partitionBy(*PORT_KEYS).orderBy("end_us").rangeBetween(-W10, 0)
    wp60 = Window.partitionBy(*PORT_KEYS).orderBy("end_us").rangeBetween(-W60, 0)
    wa60 = Window.partitionBy(*DAY_KEYS).orderBy("end_us").rangeBetween(-W60, 0)
    w = v.select(
        "flow_id", *SUM_COLS,
        F.count(F.lit(1)).over(wp10).alias("n10p"),
        F.count(F.lit(1)).over(wp60).alias("n60p"),
        F.count(F.lit(1)).over(wa60).alias("n60a"),
        *[F.sum(s).over(wp60).alias("s" + s[1:]) for s in SUM_COLS],
    )
    return _finish(w)


def _prefix_window(v, keys, lengths: dict[str, int], sums: list[str]):
    """keys bölümünde, her L için [t-L, t] aralığındaki satır sayısı ve `sums` toplamları.

    Dönüş: flow_id, n<ad> ve (yalnızca ilk L için) s_<değer> sütunları — akışın kendisi dahil.
    """
    from pyspark.sql import Window, functions as F
    zero = {s: F.lit(0).cast("long") for s in sums}
    data = v.select(*keys, "flow_id", (F.col("end_us") * 2 + 1).alias("k"), F.lit("d").alias("tag"),
                    F.lit(1).cast("long").alias("one"), *[F.coalesce(F.col(s), F.lit(0)).alias(s) for s in sums])
    parts = [data]
    for name, L in lengths.items():
        parts.append(v.select(*keys, "flow_id", ((F.col("end_us") - L) * 2).alias("k"), F.lit(name).alias("tag"),
                              F.lit(0).cast("long").alias("one"), *[zero[s].alias(s) for s in sums]))
    u = parts[0]
    for p in parts[1:]:
        u = u.unionByName(p)
    cum = Window.partitionBy(*keys).orderBy("k").rangeBetween(Window.unboundedPreceding, Window.currentRow)
    u = u.select("flow_id", "tag", F.sum("one").over(cum).alias("cn"),
                 *[F.sum(s).over(cum).alias("c_" + s) for s in sums])
    first = next(iter(lengths))
    aggs = [(F.max(F.when(F.col("tag") == "d", F.col("cn")))
             - F.max(F.when(F.col("tag") == name, F.col("cn")))).alias("n" + name) for name in lengths]
    aggs += [(F.max(F.when(F.col("tag") == "d", F.col("c_" + s)))
              - F.max(F.when(F.col("tag") == first, F.col("c_" + s)))).alias("s" + s[1:]) for s in sums]
    return u.groupBy("flow_id").agg(*aggs)


def windows_prefix(df):
    v = _window_inputs(df)
    port = _prefix_window(v, PORT_KEYS, {"60p": W60, "10p": W10}, SUM_COLS)
    day = _prefix_window(v, DAY_KEYS, {"60a": W60}, [])
    w = v.select("flow_id", *SUM_COLS).join(port, "flow_id").join(day, "flow_id")
    return _finish(w)


def add_features(df, method: str = "prefix"):
    """clean_flows çerçevesine 20 özelliği ekler (ham sütunlar korunur)."""
    win = windows_prefix(df) if method == "prefix" else windows_naive(df)
    return derived(df).join(win, "flow_id")


# ---- yazma --------------------------------------------------------------------------------
def write_parquet(df, out: Path, partition_by: str = "capture_day") -> int:
    df.write.mode("overwrite").partitionBy(partition_by).parquet(str(out))
    return df.sparkSession.read.parquet(str(out)).count()


# ---- parite -------------------------------------------------------------------------------
def parity(spark, feats, sql_path: Path | None = None, rel_tol: float = 1e-5) -> dict:
    """Spark özelliklerini SQL özellikleriyle flow_id üzerinden karşılaştırır.

    Sayısal fark ölçütü: |spark - sql| <= rel_tol * max(1, |sql|) (float32 depolama yuvarlaması).
    NULL'ların yeri birebir aynı olmalı.
    """
    from pyspark.sql import functions as F
    sql = spark.read.parquet(str(sql_path or sql_features_dir()))
    counts = sql.count(), feats.count()
    sql = sql.select("flow_id", *[F.col(c).alias("q_" + c) for c in FEATURES])
    j = feats.select("flow_id", *FEATURES).join(sql, "flow_id", "full_outer")
    aggs = [F.count(F.lit(1)).alias("rows")]
    for c in FEATURES:
        a, b = F.col(c).cast("double"), F.col("q_" + c).cast("double")
        null_mismatch = a.isNull() != b.isNull()
        diff = F.abs(a - b) / F.greatest(F.lit(1.0), F.abs(b))
        aggs += [F.sum(null_mismatch.cast("long")).alias(f"{c}__null_mismatch"),
                 F.sum((diff > rel_tol).cast("long")).alias(f"{c}__over_tol"),
                 F.max(diff).alias(f"{c}__max_rel_diff"),
                 F.sum(a.isNull().cast("long")).alias(f"{c}__nulls")]
    r = j.agg(*aggs).collect()[0].asDict()
    out = {"rows_sql": counts[0], "rows_spark": counts[1], "rows_joined": r["rows"],
           "rel_tol": rel_tol, "features": {}}
    for c in FEATURES:
        out["features"][c] = {k: r[f"{c}__{k}"] for k in ("null_mismatch", "over_tol", "max_rel_diff", "nulls")}
    out["all_equal"] = (counts[0] == counts[1] == r["rows"]
                        and all(v["null_mismatch"] == 0 and v["over_tol"] == 0 for v in out["features"].values()))
    return out


# ---- toplu skorlama ----------------------------------------------------------------------
def score(spark, df, model_path: Path):
    """LightGBM modelini her Spark bölümünde (mapInPandas) çalıştırır.

    Model dosyası SparkFiles ile dağıtılır; her Python işçisi onu bir kez yükler. İşçi başına
    tek LightGBM iş parçacığı: paralellik Spark görevlerinden gelir.
    """
    import pandas as pd
    from pyspark import SparkFiles

    spark.sparkContext.addFile(str(model_path))
    name = model_path.name
    import joblib
    feats = joblib.load(model_path)["card"]["features"]
    keep = ["flow_id", "capture_day", "label", "is_attack", "split_temporal"]

    def predict(it):
        import joblib
        import numpy as np
        est = joblib.load(SparkFiles.get(name))["estimator"]
        for pdf in it:
            X = pdf[feats].to_numpy(dtype=np.float32, na_value=np.nan)
            s = est.predict_proba(X, num_threads=1)[:, 1] if len(pdf) else np.zeros(0)
            yield pd.DataFrame({**{k: pdf[k] for k in keep}, "score": s.astype("float64")})

    schema = "flow_id long, capture_day string, label string, is_attack boolean, split_temporal string, score double"
    return df.select(*keep, *[c for c in feats if c not in keep]).mapInPandas(predict, schema)


# ---- komutlar -----------------------------------------------------------------------------
def _save(name: str, payload: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    p = RESULTS_DIR / f"{name}_{db_name()}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return p


def run_features(naive_bench: bool = False) -> dict:
    spark = session("ids-features")
    clean = read_clean(spark)
    n = clean.count()
    out: dict = {"database": db_name(), "rows": n, "spark": spark.version,
                 "master": spark.sparkContext.master, "cpu": os.cpu_count()}
    t0 = time.perf_counter()
    feats = add_features(clean, "prefix").select("flow_id", "capture_day", *FEATURES)
    written = write_parquet(feats, features_dir())
    out["prefix_seconds"] = time.perf_counter() - t0
    out["rows_written"] = written
    print(f"  özellikler (önek toplamı): {written:,} satır, {out['prefix_seconds']:,.1f} s", flush=True)
    if naive_bench:
        t0 = time.perf_counter()
        add_features(clean, "naive").select("flow_id", *FEATURES).write.format("noop").mode("overwrite").save()
        out["naive_seconds"] = time.perf_counter() - t0
        print(f"  özellikler (rangeBetween): {out['naive_seconds']:,.1f} s", flush=True)
    t0 = time.perf_counter()
    out["parity"] = parity(spark, spark.read.parquet(str(features_dir())))
    out["parity_seconds"] = time.perf_counter() - t0
    print(f"  SQL paritesi: {'TAMAM' if out['parity']['all_equal'] else 'FARK VAR'} "
          f"({out['parity']['rows_joined']:,} satır, {out['parity_seconds']:,.1f} s)", flush=True)
    for c, v in out["parity"]["features"].items():
        if v["null_mismatch"] or v["over_tol"]:
            print(f"    {c}: {v}", flush=True)
    _save("spark_features", out)
    spark.stop()
    return out


def run_window_bench(day: str, timeout_s: int = 900) -> dict:
    """Tek bir günde iki pencere yöntemini (yalnızca pencere özellikleri) karşılaştırır.

    rangeBetween sürümü süre sınırını aşarsa iş iptal edilir ve sonuç "> sınır" olarak kaydedilir.
    """
    import threading

    spark = session("ids-window-bench")
    df = read_clean(spark).where(f"capture_day = '{day}'").cache()
    n = df.count()
    out = {"database": db_name(), "day": day, "rows": n, "timeout_s": timeout_s}
    for method, fn in (("prefix", windows_prefix), ("naive", windows_naive)):
        box: dict = {}

        def job():
            try:
                t0 = time.perf_counter()
                fn(df).write.format("noop").mode("overwrite").save()
                box["seconds"] = time.perf_counter() - t0
            except Exception as e:  # iptal edilen iş
                box["error"] = type(e).__name__

        th = threading.Thread(target=job, daemon=True)
        th.start()
        th.join(timeout_s)
        if th.is_alive():
            spark.sparkContext.cancelAllJobs()
            th.join(60)
            out[method] = {"seconds": None, "timed_out": True}
        else:
            out[method] = {"seconds": box.get("seconds"), "timed_out": False, "error": box.get("error")}
        sec = out[method]["seconds"]
        print(f"  {day} {method}: {f'{sec:,.1f} s' if sec else f'> {timeout_s} s (iptal)'}", flush=True)
    _save(f"spark_window_bench_{day}", out)
    spark.stop()
    return out


def run_score(model_path: Path | None = None) -> dict:
    """Tüm akışları Spark'ta skorlar; test bölümünde eğitimdeki metrikleri yeniden üretir."""
    import joblib
    import numpy as np
    from sklearn.metrics import average_precision_score

    model_path = model_path or (MODELS_DIR / db_name() / "model.joblib")
    card = joblib.load(model_path)["card"]
    spark = session("ids-score")
    df = read_clean(spark).join(spark.read.parquet(str(features_dir())).drop("capture_day"), "flow_id")
    t0 = time.perf_counter()
    n = write_parquet(score(spark, df, model_path), scores_dir())
    dt = time.perf_counter() - t0
    print(f"  skorlama: {n:,} akış, {dt:,.1f} s ({n / dt:,.0f} akış/s)", flush=True)
    test = (spark.read.parquet(str(scores_dir())).where("split_temporal = 'test'")
            .select("is_attack", "score").toPandas())
    y, s = test["is_attack"].to_numpy(), test["score"].to_numpy()
    thr = float(card["threshold"])
    pred = s >= thr
    benign = (~y).sum()
    ev = {"rows": int(len(y)), "pr_auc": float(average_precision_score(y, s)),
          "recall": float((pred & y).sum() / y.sum()),
          "fa_per_1000_benign": float((pred & ~y).sum() / benign * 1000), "threshold": thr}
    ref = card.get("test_summary", {})
    out = {"database": db_name(), "rows": n, "seconds": dt, "rows_per_s": n / dt, "test": ev,
           "trained_model_test_summary": ref,
           "matches_training_eval": bool(ref) and all(
               np.isclose(ev[k], ref[k], rtol=1e-4) for k in ("pr_auc", "recall", "fa_per_1000_benign"))}
    print(f"  test (Spark): PR-AUC {ev['pr_auc']:.4f}, yakalama {ev['recall']:.4f}, "
          f"yanlış alarm {ev['fa_per_1000_benign']:.2f}/1000 — eğitimdeki değerlendirmeyle "
          f"{'aynı' if out['matches_training_eval'] else 'FARKLI'}", flush=True)
    _save("spark_score", out)
    spark.stop()
    return out
