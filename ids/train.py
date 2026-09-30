"""Deneyler: python -m ids train --experiment {main,random_split,ablation,multiclass,lodo,all}

Tüm deneyler sql/40_training_set.sql çıktısını okur (Parquet varsa oradan, yoksa SQL'den
doğrudan belleğe). Ayrım sütunları SQL'de modelden önce sabitlenmiştir.

Bellek: tam veri 15,8 M satırdır. Yükleme sırasında YALNIZCA eğitim bölümündeki normal
akışlar hash(flow_id) ile deterministik olarak seyreltilir (varsayılan %35); tüm saldırı
satırları ve val/test'in tamamı korunur, bu yüzden eşik seçimi ve test metrikleri gerçek
sınıf dağılımında yapılır. Veri hemen float32 matrislere çevrilir.

Her deney sonucu reports/results/<deney>_<db>.json dosyasına ve meta.experiments'a yazılır.
"""
from __future__ import annotations

import gc
import json
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone

import joblib
import numpy as np
import polars as pl

from . import db, export
from .columns import (CANDIDATE_FEATURES, DERIVED_FEATURES, FORBIDDEN_FEATURES,
                      SHORTCUT_RISK_FEATURES, WINDOW_FEATURES)
from .config import MODELS_DIR, REPORTS_DIR, SEED, db_name
from .modeling import (LGBM_PARAMS, Timer, choose_thresholds, environment, fit_lgbm, full_eval,
                       latency_single_row, make_logreg, throughput)

RESULTS_DIR = REPORTS_DIR / "results"
META = ["flow_id", "capture_day", "label", "is_attack", "fv_seen_in_train_temporal", "fv_seen_in_train_random"]


@dataclass
class Part:
    """Bir bölüm: tüm aday özellikler (float32, CANDIDATE_FEATURES sırası) + meta."""
    X: np.ndarray
    meta: pl.DataFrame

    @property
    def y(self) -> np.ndarray:
        return self.meta["is_attack"].to_numpy()

    @property
    def n(self) -> int:
        return self.meta.height

    def take(self, mask: np.ndarray) -> "Part":
        idx = np.flatnonzero(mask)
        return Part(self.X[idx], self.meta[idx])


def load_parts(split_col: str, keep_pct: int | None) -> dict[str, Part]:
    """SQL çıktısını parça parça okuyup doğrudan bölüm bazında float32 matrislere dağıtır.

    Tam veri çerçevesi hiçbir zaman oluşturulmaz (tepe bellek ≈ matrisler + bir birleştirme kopyası).
    """
    import time
    sql = export.training_query(where=f"t.{split_col} IN ('train','val','test')",
                                benign_train_keep_pct=keep_pct, split_col=split_col)
    names = ("train", "val", "test")
    xs = {k: [] for k in names}
    metas = {k: [] for k in names}
    t0 = time.perf_counter()
    with db.connect() as conn:
        for tbl in export.stream_tables(conn, sql):
            d = pl.from_arrow(tbl)
            del tbl
            for k in names:
                sub = d.filter(pl.col(split_col) == k)
                xs[k].append(sub.select([pl.col(c).cast(pl.Float32) for c in CANDIDATE_FEATURES]).to_numpy())
                metas[k].append(sub.select(META))
            del d, sub
        db.log_timing(conn, "export", f"40_training_set.sql -> bellek ({split_col})", time.perf_counter() - t0,
                      sum(sum(len(x) for x in xs[k]) for k in names))
    parts = {}
    for k in names:
        X = np.concatenate(xs[k]) if xs[k] else np.zeros((0, len(CANDIDATE_FEATURES)), np.float32)
        xs[k].clear()
        meta = pl.concat(metas[k]).with_columns(pl.col(["capture_day", "label"]).cast(pl.Utf8))
        metas[k].clear()
        parts[k] = Part(X, meta)
        gc.collect()
    import pyarrow as pa
    pa.default_memory_pool().release_unused()
    print(f"  SQL'den okundu ({time.perf_counter() - t0:,.1f} s, arrow havuzu: "
          f"{pa.default_memory_pool().backend_name})", flush=True)
    for k, p in parts.items():
        print(f"  {split_col}/{k}: {p.n:,} satır, {int(p.y.sum()):,} saldırı, X={p.X.nbytes / 1e9:.2f} GB", flush=True)
    return parts


# ---- özellik seçimi (yalnız eğitim bölümünde) -------------------------------------------
def select_features(train: Part, exclude=()) -> tuple[list[str], list[str]]:
    cands = [c for c in CANDIDATE_FEATURES if c not in set(exclude)]
    if set(cands) & set(FORBIDDEN_FEATURES):
        raise ValueError("Yasaklı alan özellik listesinde")
    idx = [CANDIDATE_FEATURES.index(c) for c in cands]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        lo = np.nanmin(train.X[:, idx], axis=0)
        hi = np.nanmax(train.X[:, idx], axis=0)
    constant = [c for c, a, b in zip(cands, lo, hi) if not (a < b)]  # sabit ya da tamamen boş
    return [c for c in cands if c not in constant], constant


def cols(p: Part, feats: list[str]) -> np.ndarray:
    return p.X[:, [CANDIDATE_FEATURES.index(c) for c in feats]]


def downsample_idx(y: np.ndarray, cap: int | None, seed: int = SEED) -> np.ndarray:
    """Eğitim satırlarını en fazla `cap`'e indirir: saldırılar korunur, normal trafik seyreltilir."""
    n = len(y)
    if cap is None or n <= cap:
        return np.arange(n)
    rng = np.random.default_rng(seed)
    atk, ben = np.flatnonzero(y), np.flatnonzero(~y)
    if len(atk) > cap // 2:
        atk = rng.choice(atk, cap // 2, replace=False)
    ben = rng.choice(ben, min(len(ben), cap - len(atk)), replace=False)
    return np.sort(np.r_[atk, ben])


# ---- kayıt -------------------------------------------------------------------------------
def _jsonable(o):
    """JSON standardı Infinity/NaN içermez (PostgreSQL jsonb de kabul etmez) -> null."""
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def save_result(name: str, payload: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = _jsonable({"experiment": name, "database": db_name(),
                         "created_at": datetime.now(timezone.utc).isoformat(), **payload})
    (RESULTS_DIR / f"{name}_{db_name()}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    run_id = f"{name}-{datetime.now():%Y%m%d-%H%M%S}"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO meta.experiments(run_id, name, params, features, environment, data, results)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (run_id, name, json.dumps(payload.get("params", {})), json.dumps(payload.get("features", {})),
             json.dumps(payload.get("environment", {})), json.dumps(payload.get("data", {})),
             json.dumps(payload.get("results", {}))))
    print(f"  -> reports/results/{name}_{db_name()}.json, meta.experiments[{run_id}]", flush=True)


def split_stats(parts: dict[str, Part], keep_pct) -> dict:
    out = {}
    for k, p in parts.items():
        out[k] = {"rows": p.n, "attack_rows": int(p.y.sum()),
                  "labels": dict(sorted(p.meta.group_by("label").len().iter_rows()))}
    return out


def _summary_line(tag: str, ev: dict, op: str = "best_f1_val") -> str:
    o = ev["operating_points"][op]
    pr = ev["pr_auc"]
    return (f"  {tag:42} PR-AUC={'—' if pr is None else f'{pr:.4f}'}  P={o['precision']:.4f} "
            f"R={o['recall']:.4f} F1={o['f1']:.4f}  YA/1000={o['fa_per_1000_benign']:.3f}")


def _proba(model, X):
    return model.predict_proba(X)[:, 1]


# ---- deneyler ------------------------------------------------------------------------------
def exp_main(P: dict[str, Part], quick: bool, keep_pct) -> dict:
    """Ana deney: zamansal ayrım, 4 yöntem, eşik ve model seçimi doğrulamada."""
    tr, va, te = P["train"], P["val"], P["test"]
    feats, constant = select_features(tr)
    print(f"  {len(feats)} özellik ({len(constant)} sabit sütun eğitimde elendi: {constant})", flush=True)
    Xva, Xte = cols(va, feats), cols(te, feats)
    yva = va.y
    results, timings, models = {}, {}, {}

    # 1) Çoğunluk sınıfı: hep BENIGN der.
    inf = {k: float("inf") for k in choose_thresholds(yva, np.zeros(va.n))}
    results["majority"] = {"val": full_eval(va.meta, np.zeros(va.n), inf),
                           "test": full_eval(te.meta, np.zeros(te.n), inf)}

    # 2) Kural: aynı hedef porta son 60 s'de biten akış sayısı (hacim/hız kuralı), eşik val'de.
    j = CANDIDATE_FEATURES.index("w60_port_n")
    s_va, s_te = np.nan_to_num(va.X[:, j]), np.nan_to_num(te.X[:, j])
    th = choose_thresholds(yva, s_va)
    results["rule_w60_port_n"] = {"val": full_eval(va.meta, s_va, th), "test": full_eval(te.meta, s_te, th)}
    models["rule_w60_port_n"] = (None, th, s_te)

    # 3) Lojistik regresyon (medyan doldurma + işaretli log + ölçekleme; hepsi yalnız train'de öğrenilir)
    lr_cap = 300_000 if quick else 2_000_000
    idx = downsample_idx(tr.y, lr_cap)
    lr = make_logreg()
    with Timer() as t:
        lr.fit(cols(tr, feats)[idx], tr.y[idx])
    timings["logreg_train_s"] = t.seconds
    s_va, s_te = _proba(lr, Xva), _proba(lr, Xte)
    th = choose_thresholds(yva, s_va)
    results["logreg"] = {"val": full_eval(va.meta, s_va, th), "test": full_eval(te.meta, s_te, th),
                         "train_rows": len(idx)}
    models["logreg"] = (lr, th, s_te)

    # 4) LightGBM (erken durdurma doğrulamada)
    lg_cap = 300_000 if quick else None
    idx = downsample_idx(tr.y, lg_cap)
    Xtr = cols(tr, feats)[idx]
    with Timer() as t:
        gbm = fit_lgbm(Xtr, tr.y[idx], Xva, yva, {"n_estimators": 300} if quick else None)
    del Xtr
    timings["lightgbm_train_s"] = t.seconds
    s_va, s_te = _proba(gbm, Xva), _proba(gbm, Xte)
    th = choose_thresholds(yva, s_va)
    results["lightgbm"] = {"val": full_eval(va.meta, s_va, th), "test": full_eval(te.meta, s_te, th),
                           "train_rows": len(idx), "best_iteration": int(gbm.best_iteration_ or 0)}
    models["lightgbm"] = (gbm, th, s_te)

    # En iyi model: DOĞRULAMA PR-AUC'una göre (test kullanılmaz).
    best = max(["logreg", "lightgbm"], key=lambda m: results[m]["val"]["pr_auc"])
    best_model, best_th, _ = models[best]

    # Eğitimde birebir görülmemiş özellik vektörleri üzerindeki test sonuçları
    novel = ~te.meta["fv_seen_in_train_temporal"].to_numpy()
    for m, (_, th_m, s_m) in models.items():
        results[m]["test_unseen_feature_vectors"] = full_eval(te.meta.filter(pl.Series(novel)), s_m[novel], th_m)

    for m in results:
        print(_summary_line(f"{m} [val]", results[m]["val"]))
        print(_summary_line(f"{m} [test]", results[m]["test"]))
        if "test_unseen_feature_vectors" in results[m]:
            print(_summary_line(f"{m} [test, görülmemiş vektör]", results[m]["test_unseen_feature_vectors"]))

    # Gecikme ve üretim hızı (model düzeyi)
    if best == "lightgbm":
        booster = best_model.booster_
        fn = lambda X: booster.predict(X, num_threads=1)  # noqa: E731
    else:
        fn = lambda X: best_model.predict_proba(X)[:, 1]  # noqa: E731
    latency = {"single_row": latency_single_row(fn, Xte, n=300 if quick else 2000),
               "batch": throughput(lambda X: best_model.predict_proba(X)[:, 1], Xte)}
    print(f"  gecikme (tek akış, model): p50={latency['single_row']['p50_ms']:.3f} ms "
          f"p95={latency['single_row']['p95_ms']:.3f} ms; toplu: {latency['batch']['rows_per_s']:,.0f} akış/s")

    # API için modeli kaydet
    out = MODELS_DIR / db_name()
    out.mkdir(parents=True, exist_ok=True)
    card = {
        "model": best, "features": feats, "dropped_constant": constant,
        "threshold": best_th["best_f1_val"], "thresholds": best_th,
        "selected_by": "doğrulama PR-AUC", "trained_at": datetime.now(timezone.utc).isoformat(),
        "database": db_name(), "split": "temporal", "benign_train_keep_pct": keep_pct,
        "test_summary": {k: results[best]["test"]["operating_points"]["best_f1_val"][k]
                         for k in ("precision", "recall", "f1", "fa_per_1000_benign")}
                        | {"pr_auc": results[best]["test"]["pr_auc"]},
    }
    joblib.dump({"estimator": best_model, "card": card}, out / "model.joblib")
    (out / "model_card.json").write_text(json.dumps(_jsonable(card), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  en iyi model (val PR-AUC): {best} -> {out / 'model.joblib'}")

    return {"params": {"lgbm": {k: v for k, v in LGBM_PARAMS.items() if k != "n_jobs"},
                       "logreg_train_cap": lr_cap, "lgbm_train_cap": lg_cap,
                       "benign_train_keep_pct": keep_pct},
            "features": {"used": feats, "dropped_constant": constant},
            "data": split_stats(P, keep_pct),
            "results": {"models": results, "best_model": best, "timings": timings, "latency": latency}}


def _lgbm_variant(tr: Part, va: Part, te: Part | None, exclude, quick, seen_col, cap):
    feats, _ = select_features(tr, exclude)
    idx = downsample_idx(tr.y, cap)
    Xva = cols(va, feats)
    with Timer() as t:
        m = fit_lgbm(cols(tr, feats)[idx], tr.y[idx], Xva, va.y, {"n_estimators": 300} if quick else None)
    s_va = _proba(m, Xva)
    th = choose_thresholds(va.y, s_va)
    r = {"n_features": len(feats), "excluded": list(exclude), "train_rows": len(idx),
         "train_s": t.seconds, "best_iteration": int(m.best_iteration_ or 0),
         "val": full_eval(va.meta, s_va, th)}
    if te is not None:
        s_te = _proba(m, cols(te, feats))
        novel = ~te.meta[seen_col].to_numpy()
        r["test"] = full_eval(te.meta, s_te, th)
        r["test_unseen_feature_vectors"] = full_eval(te.meta.filter(pl.Series(novel)), s_te[novel], th)
    return r, m, feats, th


def exp_random_split_part(P: dict[str, Part], scheme: str, quick: bool, keep_pct) -> dict:
    """Rastgele satır ayrımı vs zamansal ayrım: aynı model, aynı eğitim boyutu (bir parça)."""
    cap = 300_000 if quick else 3_000_000
    seen = "fv_seen_in_train_temporal" if scheme == "temporal" else "fv_seen_in_train_random"
    r, *_ = _lgbm_variant(P["train"], P["val"], P["test"], (), quick, seen, cap)
    r["data"] = split_stats(P, keep_pct)
    print(_summary_line(f"{scheme} [test]", r["test"]))
    print(_summary_line(f"{scheme} [test, görülmemiş vektör]", r["test_unseen_feature_vectors"]))
    return r


def exp_ablation(P: dict[str, Part], quick: bool, keep_pct) -> dict:
    cap = 300_000 if quick else 3_000_000
    variants = {
        "all_features": (),
        "no_shortcut_risk (dst_port, init_win)": tuple(SHORTCUT_RISK_FEATURES),
        "no_window_features": tuple(WINDOW_FEATURES),
        "cicflowmeter_only (SQL özellikleri yok)": tuple(WINDOW_FEATURES + DERIVED_FEATURES),
    }
    out = {}
    for name, excl in variants.items():
        out[name], *_ = _lgbm_variant(P["train"], P["val"], P["test"], excl, quick,
                                      "fv_seen_in_train_temporal", cap)
        print(_summary_line(name, out[name]["test"]), flush=True)
    return {"params": {"train_cap": cap, "benign_train_keep_pct": keep_pct}, "results": out}


def exp_multiclass(P: dict[str, Part], quick: bool, keep_pct) -> dict:
    """İkili sistemden sonra ayrı deney: saldırı türü tahmini (LightGBM, çok sınıflı)."""
    import lightgbm as lgb
    from sklearn.metrics import classification_report, confusion_matrix, f1_score

    cap = 300_000 if quick else 1_500_000  # 15 sınıflı model 3 M satırda bellek sınırına dayandı
    tr, va, te = P["train"], P["val"], P["test"]
    classes = sorted(set(tr.meta["label"].to_list()))
    cidx = {c: i for i, c in enumerate(classes)}
    feats, _ = select_features(tr)

    def xy(p: Part, rows: np.ndarray | None = None):
        lab = np.array(p.meta["label"].to_list())
        keep = np.isin(lab, classes)
        if rows is not None:
            m = np.zeros(p.n, bool)
            m[rows] = True
            keep &= m
        return cols(p, feats)[keep], np.array([cidx[x] for x in lab[keep]])

    Xtr, ytr = xy(tr, downsample_idx(tr.y, cap))
    Xva, yva = xy(va)
    model = lgb.LGBMClassifier(objective="multiclass", n_estimators=300 if quick else 1500,
                               learning_rate=0.05, num_leaves=63, min_child_samples=50,
                               subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                               class_weight="balanced", random_state=SEED, verbose=-1)
    with Timer() as t:
        model.fit(Xtr, ytr, eval_X=(Xva,), eval_y=(yva,), eval_metric="multi_logloss",
                  callbacks=[lgb.early_stopping(50, verbose=False)])
    del Xtr, Xva
    Xte, yte = xy(te)
    pred = model.predict(Xte)
    labels = list(range(len(classes)))
    rep = classification_report(yte, pred, labels=labels, target_names=classes, output_dict=True, zero_division=0)
    cm = confusion_matrix(yte, pred, labels=labels)
    macro = f1_score(yte, pred, average="macro", labels=labels, zero_division=0)
    print(f"  çok sınıflı: macro-F1={macro:.4f}, {len(classes)} sınıf, eğitim {t.seconds:,.0f} s", flush=True)
    return {"params": {"train_cap": cap, "benign_train_keep_pct": keep_pct}, "features": {"used": feats},
            "results": {"classes": classes, "report": rep, "confusion_matrix": cm.tolist(),
                        "macro_f1": macro, "train_s": t.seconds,
                        "best_iteration": int(model.best_iteration_ or 0),
                        "test_labels_missing_from_train": sorted(set(te.meta["label"].to_list()) - set(classes))}}


def _score_day_stream(model, feats: list[str], day: str) -> tuple[pl.DataFrame, np.ndarray]:
    """Dışarıda bırakılan günün TÜM akışlarını SQL'den parça parça okuyup puanlar."""
    sql = export.training_query(where=f"t.capture_day = DATE '{day}'")
    metas, scores = [], []
    with db.connect() as conn:
        for tbl in export.stream_tables(conn, sql):
            d = pl.from_arrow(tbl)
            X = d.select([pl.col(c).cast(pl.Float32) for c in feats]).to_numpy()
            scores.append(_proba(model, X))
            metas.append(d.select(["label", "is_attack"]))
    return pl.concat(metas), np.concatenate(scores)


def exp_lodo(P: dict[str, Part], quick: bool, keep_pct) -> dict:
    """Zorlayıcı test: bir günü (ve o günün saldırı senaryolarını) tamamen dışarıda bırak.

    Eğitim/doğrulama: diğer günlerin zamansal train/val bölümleri. Test: dışarıda bırakılan
    günün TÜM akışları (gap dahil, seyreltme yok). O günün saldırı türü eğitimde hiç yoksa bu,
    görülmemiş saldırıya genelleme ölçümüdür.
    """
    cap = 200_000 if quick else 2_000_000
    days = sorted(set(P["train"].meta["capture_day"].to_list()))
    out = {}
    for d in days:
        tr = P["train"].take(P["train"].meta["capture_day"].to_numpy() != d)
        va = P["val"].take(P["val"].meta["capture_day"].to_numpy() != d)
        r, model, feats, th = _lgbm_variant(tr, va, None, (), quick, None, cap)
        del tr, va
        gc.collect()
        meta, s = _score_day_stream(model, feats, d)
        r["test"] = full_eval(meta, s, th)
        test_labels = sorted(set(meta["label"].to_list()) - {"Benign"})
        train_labels = set(P["train"].meta.filter(pl.col("capture_day") != d)["label"].to_list())
        r["held_out_attack_labels"] = test_labels
        r["held_out_labels_seen_in_train"] = [x for x in test_labels if x in train_labels]
        out[d] = r
        print(_summary_line(f"hold-out {d} {test_labels}", r["test"]), flush=True)
    return {"params": {"train_cap": cap, "benign_train_keep_pct": keep_pct}, "results": out}


EXPERIMENTS = {"main": exp_main, "ablation": exp_ablation, "multiclass": exp_multiclass, "lodo": exp_lodo}


def run(experiment: str, quick: bool = False, keep_pct: int | None = None) -> None:
    np.random.seed(SEED)
    keep_pct = keep_pct if keep_pct is not None else (None if quick else 35)
    env = environment()
    known = ["main", "ablation", "multiclass", "lodo", "random_split"]
    wanted = known if experiment == "all" else [e.strip() for e in experiment.split(",")]
    if unknown := set(wanted) - set(known):
        raise SystemExit(f"Bilinmeyen deney: {sorted(unknown)}")

    def finish(name, payload, seconds):
        payload["environment"] = env
        payload.setdefault("results", {})["experiment_seconds"] = seconds
        payload["quick"] = quick
        save_result(name, payload)

    rs = {}
    print("\n== veri: zamansal ayrım ==", flush=True)
    P = load_parts("split_temporal", keep_pct)
    for name in EXPERIMENTS:
        if name in wanted:
            print(f"\n== {name} ==", flush=True)
            with Timer() as t:
                payload = EXPERIMENTS[name](P, quick, keep_pct)
            finish(name, payload, t.seconds)
    if "random_split" in wanted:
        print("\n== random_split: zamansal ayrım parçası ==", flush=True)
        with Timer() as t:
            rs["temporal"] = exp_random_split_part(P, "temporal", quick, keep_pct)
        t_temporal = t.seconds
    del P
    gc.collect()
    if "random_split" in wanted:
        print("\n== veri: rastgele ayrım ==", flush=True)
        P = load_parts("split_rand", keep_pct)
        print("\n== random_split: rastgele ayrım parçası ==", flush=True)
        with Timer() as t:
            rs["random"] = exp_random_split_part(P, "random", quick, keep_pct)
        finish("random_split", {"params": {"train_cap": 300_000 if quick else 3_000_000,
                                           "benign_train_keep_pct": keep_pct}, "results": rs},
               t_temporal + t.seconds)
