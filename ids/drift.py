"""Dağılım kayması (drift) izleme: python -m ids drift   (Spark konteynerinde)

Soru: etiket gelmeden, yalnızca girdi ve skor dağılımına bakarak modelin kötüleştiği
günler fark edilebilir mi?

Ölçüt: PSI (Population Stability Index). Referans dağılımın ondalıklarıyla (decile) bölmeler
kurulur, NULL ayrı bir bölmedir; PSI = Σ (q - p) · ln(q / p). Yaygın eşikler (sektör
geleneği, istatistiksel test değil): < 0,1 kararlı, 0,1-0,25 orta, > 0,25 belirgin kayma.

Üç analiz:
1. Görülmemiş gün (LODO) doğrulaması. Referans = diğer 9 günün zamansal eğitim bölümü,
   hedef = dışarıda bırakılan günün tüm akışları; yani LODO modelinin eğitildiği veri ile
   test edildiği veri. Her gün için özellik PSI'ları özetlenir ve LODO'da ölçülmüş gerçek
   performansla (reports/results/lodo_<db>.json) sıra korelasyonuna bakılır. N = 10 gün.
2. Ayrıştırma. Aynı PSI yalnızca normal (Benign) akışlarda hesaplanır. Kayma saldırı
   trafiğinin kendisinden mi, yoksa normal trafiğin değişmesinden mi geliyor?
   (Etiket kullanır; izleme değil, analiz içindir.)
3. Ana model izleme. Referans = aynı günün doğrulama bölümünün skorları; test bölümü için
   skor PSI'ı ve alarm oranı (etiketsiz), yanında etiketli yakalama/yanlış alarm.

Tek veri geçişi: tüm özellikler için bölme sayımları (gün, bölüm, saldırı mı) gruplarında tek
bir Spark toplamasıyla çıkarılır; PSI'lar bu sayımlardan numpy ile hesaplanır.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .config import MODELS_DIR, REPORTS_DIR, db_name

RESULTS_DIR = REPORTS_DIR / "results"
N_BINS = 10
EPS = 1e-4
PSI_MODERATE, PSI_MAJOR = 0.1, 0.25


# ---- saf fonksiyonlar (Spark gerektirmez, birim testli) -----------------------------------
def interior_edges(quantiles) -> list[float]:
    """Referans yüzdeliklerinden artan, tekrarsız iç sınırlar. Ayrık/sabit özelliklerde
    yüzdelikler çakışır; o zaman daha az bölme oluşur (sabit özellik: 0 sınır, tek bölme)."""
    q = [float(x) for x in quantiles if x is not None and np.isfinite(x)]
    return sorted(set(q))[1:] if q else []


def bin_index(x: np.ndarray, edges: list[float]) -> np.ndarray:
    """bölme = x'in geçtiği sınır sayısı (x >= e); NULL/NaN -> -1. Spark ifadesiyle aynı kural."""
    x = np.asarray(x, dtype=float)
    b = (x[:, None] >= np.asarray(edges)[None, :]).sum(axis=1) if edges else np.zeros(len(x), int)
    return np.where(np.isnan(x), -1, b)


def psi(ref_counts, cur_counts, eps: float = EPS) -> float:
    p = np.asarray(ref_counts, dtype=float)
    q = np.asarray(cur_counts, dtype=float)
    if p.sum() == 0 or q.sum() == 0:
        return float("nan")
    p = np.maximum(p / p.sum(), eps)
    q = np.maximum(q / q.sum(), eps)
    return float(np.sum((q - p) * np.log(q / p)))


def level(v: float) -> str:
    if not np.isfinite(v):
        return "veri yok"
    return "belirgin" if v > PSI_MAJOR else "orta" if v > PSI_MODERATE else "kararlı"


def spearman(x, y) -> dict:
    from scipy.stats import spearmanr
    r = spearmanr(x, y)
    return {"rho": float(r.statistic), "p": float(r.pvalue), "n": len(x)}


# ---- Spark tarafı -------------------------------------------------------------------------
def _bin_expr(col: str, edges: list[float]):
    from pyspark.sql import functions as F
    c = F.col(col).cast("double")
    b = F.lit(0)
    for e in edges:
        b = b + (c >= F.lit(e)).cast("int")
    return F.when(c.isNull() | F.isnan(c), F.lit(-1)).otherwise(b)


def binned_counts(df, cols: dict[str, list[float]], keys: list[str]) -> dict:
    """{(anahtar değerleri): {özellik: {bölme: sayı}}} — tek toplama geçişi."""
    from pyspark.sql import functions as F
    aggs, index = [], []
    for c, edges in cols.items():
        e = _bin_expr(c, edges)
        for b in [-1] + list(range(len(edges) + 1)):
            aggs.append(F.sum((e == b).cast("long")).alias(f"a{len(index)}"))
            index.append((c, b))
    rows = df.groupBy(*keys).agg(*aggs).collect()
    out = {}
    for r in rows:
        d = r.asDict()
        k = tuple(d[x] for x in keys)
        out[k] = {}
        for i, (c, b) in enumerate(index):
            out[k].setdefault(c, {})[b] = d[f"a{i}"]
    return out


def _sum_groups(counts: dict, pred) -> dict[str, np.ndarray]:
    """pred(anahtar) doğru olan grupların sayımlarını özellik başına toplar."""
    tot: dict[str, dict[int, int]] = {}
    for k, feats in counts.items():
        if pred(k):
            for c, bins in feats.items():
                t = tot.setdefault(c, {})
                for b, n in bins.items():
                    t[b] = t.get(b, 0) + (n or 0)
    return {c: np.array([bins[b] for b in sorted(bins)]) for c, bins in tot.items()}


def _psi_table(ref: dict, cur: dict) -> dict[str, float]:
    return {c: psi(ref[c], cur[c]) for c in ref if c in cur}


def _summary(table: dict[str, float], weights: dict[str, float]) -> dict:
    vals = {c: v for c, v in table.items() if np.isfinite(v)}
    w = np.array([weights.get(c, 0.0) for c in vals])
    v = np.array(list(vals.values()))
    top = sorted(vals.items(), key=lambda kv: -kv[1])[:5]
    return {"mean_psi": float(v.mean()), "median_psi": float(np.median(v)),
            "weighted_psi": float((w * v).sum() / w.sum()) if w.sum() else float("nan"),
            "n_major": int((v > PSI_MAJOR).sum()), "n_features": len(v),
            "top": [{"feature": c, "psi": round(x, 4)} for c, x in top]}


def run() -> dict:
    import joblib
    from pyspark.sql import functions as F

    from . import spark_job

    t_start = time.perf_counter()
    bundle = joblib.load(MODELS_DIR / db_name() / "model.joblib")
    card, est = bundle["card"], bundle["estimator"]
    feats = card["features"]
    gain = est.booster_.feature_importance("gain")
    weights = dict(zip(feats, (gain / gain.sum()).tolist()))

    spark = spark_job.session("ids-drift")
    df = spark_job.read_clean(spark).join(
        spark.read.parquet(str(spark_job.features_dir())).drop("capture_day"), "flow_id")
    df = df.select("capture_day", "split_temporal", "is_attack", *feats).cache()

    # Bölmeler: tüm günlerin eğitim bölümünün ondalıkları (etiket kullanılmaz).
    t0 = time.perf_counter()
    probs = [i / N_BINS for i in range(N_BINS + 1)]
    train = df.where("split_temporal = 'train'")
    qs = train.approxQuantile(feats, probs, 1e-3)
    edges = {c: interior_edges(q) for c, q in zip(feats, qs)}
    counts = binned_counts(df, edges, ["capture_day", "split_temporal", "is_attack"])
    t_counts = time.perf_counter() - t0
    print(f"  özellik bölme sayımları: {len(counts)} grup, {t_counts:,.1f} s", flush=True)

    days = sorted({k[0] for k in counts})
    lodo_path = RESULTS_DIR / f"lodo_{db_name()}.json"
    lodo = json.loads(lodo_path.read_text(encoding="utf-8"))["results"] if lodo_path.exists() else {}

    per_day = {}
    for d in days:
        ref = _sum_groups(counts, lambda k: k[0] != d and k[1] == "train")
        cur = _sum_groups(counts, lambda k: k[0] == d)
        ref_b = _sum_groups(counts, lambda k: k[0] != d and k[1] == "train" and not k[2])
        cur_b = _sum_groups(counts, lambda k: k[0] == d and not k[2])
        all_t, ben_t = _psi_table(ref, cur), _psi_table(ref_b, cur_b)
        r = {"all_flows": _summary(all_t, weights), "benign_only": _summary(ben_t, weights),
             "psi_by_feature": {c: round(v, 5) for c, v in all_t.items()}}
        if d in lodo and "test" in lodo[d]:
            t = lodo[d]["test"]
            op = t["operating_points"]["best_f1_val"]
            r["lodo"] = {"pr_auc": t["pr_auc"], "recall": op["recall"],
                         "fa_per_1000_benign": op["fa_per_1000_benign"], "prevalence": t["prevalence"],
                         "attack_labels": lodo[d].get("held_out_attack_labels", []),
                         "labels_seen_in_train": lodo[d].get("held_out_labels_seen_in_train", [])}
        per_day[d] = r

    corr = {}
    have = [d for d in days if "lodo" in per_day[d]]
    if len(have) >= 3:
        for sig in ("mean_psi", "weighted_psi"):
            for part in ("all_flows", "benign_only"):
                x = [per_day[d][part][sig] for d in have]
                for target in ("pr_auc", "recall"):
                    corr[f"{part}.{sig} ~ lodo.{target}"] = spearman(x, [per_day[d]["lodo"][target] for d in have])
        corr["lodo.prevalence ~ all_flows.weighted_psi"] = spearman(
            [per_day[d]["lodo"]["prevalence"] for d in have], [per_day[d]["all_flows"]["weighted_psi"] for d in have])

    # Ana model: skor drift'i (doğrulama skoru referans) ve alarm oranı.
    monitor = {}
    sp = spark_job.scores_dir()
    if sp.exists():
        scores = spark.read.parquet(str(sp)).withColumn("capture_day", F.col("capture_day").cast("string"))
        thr = float(card["threshold"])
        val = scores.where("split_temporal = 'val'")
        s_edges = interior_edges(val.approxQuantile("score", probs, 1e-4))
        sc = binned_counts(scores.where("split_temporal IN ('val','test')"), {"score": s_edges},
                           ["capture_day", "split_temporal"])
        rates = {(r["capture_day"], r["split_temporal"]): r.asDict() for r in (
            scores.where("split_temporal IN ('val','test')")
            .groupBy("capture_day", "split_temporal")
            .agg(F.count(F.lit(1)).alias("n"),
                 F.avg((F.col("score") >= thr).cast("double")).alias("alert_rate"),
                 F.sum(F.col("is_attack").cast("long")).alias("attacks"),
                 F.sum(((F.col("score") >= thr) & F.col("is_attack")).cast("long")).alias("tp"),
                 F.sum(((F.col("score") >= thr) & ~F.col("is_attack")).cast("long")).alias("fp"))
            .collect())}
        for d in days:
            if (d, "test") not in rates or (d, "val") not in rates:
                continue
            r, rv = rates[(d, "test")], rates[(d, "val")]
            ref_s = _sum_groups(sc, lambda k: k[0] == d and k[1] == "val")["score"]
            cur_s = _sum_groups(sc, lambda k: k[0] == d and k[1] == "test")["score"]
            benign = r["n"] - r["attacks"]
            monitor[d] = {"rows": r["n"], "score_psi": psi(ref_s, cur_s), "alert_rate": r["alert_rate"],
                          "val_alert_rate": rv["alert_rate"],
                          "val_attack_share": rv["attacks"] / rv["n"], "attack_share": r["attacks"] / r["n"],
                          "recall": r["tp"] / r["attacks"] if r["attacks"] else None,
                          "fa_per_1000_benign": r["fp"] / benign * 1000 if benign else None}
        monitor = {"threshold": thr, "reference": "aynı günün doğrulama bölümü skorları (zamanca testten hemen önce)",
                   "days": monitor}

    out = {"database": db_name(), "n_bins": N_BINS, "eps": EPS,
           "thresholds": {"moderate": PSI_MODERATE, "major": PSI_MAJOR},
           "reference": "zamansal eğitim bölümü; LODO analizinde dışarıda bırakılan gün hariç",
           "binning": "tüm günlerin eğitim bölümünün ondalıkları (approxQuantile, göreli hata 1e-3)",
           "weights": "ana LightGBM modelinin gain önem dereceleri (toplam 1)",
           "days": per_day, "spearman": corr, "main_model_monitor": monitor,
           "seconds": time.perf_counter() - t_start}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    p = RESULTS_DIR / f"drift_{db_name()}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=lambda o: None), encoding="utf-8")
    write_report(out, REPORTS_DIR / ("drift.md" if db_name() == "ids" else f"{db_name()}/drift.md"))
    if db_name() == "ids":
        plot(out, REPORTS_DIR.parent / "docs" / "img" / "drift.png")
    spark.stop()
    return out


# ---- rapor --------------------------------------------------------------------------------
def _f(v, nd=3):
    return "–" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{nd}f}".replace(".", ",")


def write_report(r: dict, path: Path) -> None:
    L = ["# Dağılım kayması (drift) raporu", "",
         f"Referans: {r['reference']}. Bölmeler: {r['binning']}. PSI eşikleri: "
         f"> {_f(r['thresholds']['moderate'], 2)} orta, > {_f(r['thresholds']['major'], 2)} belirgin.", "",
         "## Görülmemiş gün: drift ve gerçek performans", "",
         "| Gün | Saldırılar | Ağırlıklı PSI (tüm) | Ağırlıklı PSI (yalnız normal) | PSI > 0,25 özellik | "
         "LODO PR-AUC | LODO yakalama | En çok kayan özellikler |",
         "|---|---|---|---|---|---|---|---|"]
    for d, v in r["days"].items():
        a, b, lo = v["all_flows"], v["benign_only"], v.get("lodo", {})
        top = ", ".join(t["feature"] for t in a["top"][:3])
        L.append(f"| {d} | {', '.join(lo.get('attack_labels', []))} | {_f(a['weighted_psi'])} | "
                 f"{_f(b['weighted_psi'])} | {a['n_major']}/{a['n_features']} | {_f(lo.get('pr_auc'))} | "
                 f"{_f(lo.get('recall'))} | {top} |")
    if r["spearman"]:
        L += ["", "Spearman sıra korelasyonu (N = 10 gün; küçük örneklem, p değerleri yol göstericidir):", "",
              "| Sinyal ~ hedef | rho | p |", "|---|---|---|"]
        for k, v in r["spearman"].items():
            L.append(f"| {k} | {_f(v['rho'], 2)} | {_f(v['p'], 3)} |")
    m = r.get("main_model_monitor") or {}
    if m.get("days"):
        L += ["", "## Ana model izleme (test bölümü, gün bazında)", "",
              f"Eşik {_f(m['threshold'])}. Referans: {m['reference']}.", "",
              "| Gün | Test akışı | Skor PSI (val → test) | Alarm oranı val → test | Saldırı payı val → test | "
              "Yakalama | Yanlış alarm / 1000 normal |",
              "|---|---|---|---|---|---|---|"]
        for d, v in m["days"].items():
            L.append(f"| {d} | {v['rows']:,} | {_f(v['score_psi'])} | {_f(v['val_alert_rate'])} → "
                     f"{_f(v['alert_rate'])} | {_f(v['val_attack_share'])} → {_f(v['attack_share'])} | "
                     f"{_f(v['recall'])} | {_f(v['fa_per_1000_benign'], 2)} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def plot(r: dict, path: Path) -> None:
    """Gün başına ağırlıklı PSI (tüm akışlar / yalnız normal) ve LODO PR-AUC."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    days = [d for d, v in r["days"].items() if "lodo" in v]
    if not days:
        return
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, part, title in ((axes[0], "all_flows", "Tüm akışlar"), (axes[1], "benign_only", "Yalnız normal akışlar")):
        x = [r["days"][d][part]["weighted_psi"] for d in days]
        y = [r["days"][d]["lodo"]["pr_auc"] for d in days]
        ax.scatter(x, y, s=46, color="#2f5d8a", zorder=3)
        placed = []
        for d, xi, yi in sorted(zip(days, x, y), key=lambda t: (t[2], t[1])):
            near = sum(abs(np.log10(xi / px)) < 0.12 and abs(yi - py) < 0.04 for px, py in placed)
            ax.annotate(f"{d[8:]}.{d[5:7]}", (xi, yi), textcoords="offset points",
                        xytext=(6, 4 + 11 * near), fontsize=8)
            placed.append((xi, yi))
        ax.axvline(PSI_MAJOR, color="#b4462b", lw=1, ls="--", zorder=1)
        ax.annotate("PSI 0,25", (PSI_MAJOR, 0.05), textcoords="offset points", xytext=(4, 0),
                    fontsize=8, color="#b4462b")
        ax.set_xscale("log")
        key = f"{part}.weighted_psi ~ lodo.pr_auc"
        rho = r["spearman"].get(key, {})
        ax.set_title(f"{title}  (Spearman ρ = {_f(rho.get('rho'), 2)}, p = {_f(rho.get('p'), 2)})", fontsize=10)
        ax.set_xlabel("Önem ağırlıklı PSI (log)")
        ax.grid(alpha=0.3, zorder=0)
    axes[0].set_ylabel("Görülmemiş günde PR-AUC")
    fig.suptitle("Drift sinyali, görülmemiş gün performansını önceden haber veriyor mu?", fontsize=11)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
