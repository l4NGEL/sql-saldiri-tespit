"""Model, eşik seçimi ve metrik yardımcıları.

Kurallar:
- Ölçekleme, eksik değer doldurma, sabit sütun eleme ve örnekleme YALNIZCA eğitim
  bölümünde öğrenilir (sklearn Pipeline fit(train)).
- Eşik ve model seçimi YALNIZCA doğrulama bölümünde yapılır; test bölümü en sonda bir kez
  değerlendirilir.
"""
from __future__ import annotations

import os
import platform
import subprocess
import time
from dataclasses import dataclass, field

import numpy as np
import polars as pl
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from .columns import CANDIDATE_FEATURES, FORBIDDEN_FEATURES
from .config import SEED

FA_BUDGETS = [0.1, 1.0, 10.0]  # 1.000 normal akış başına izin verilen yanlış alarm


# ---- özellik seçimi -------------------------------------------------------------------
def select_features(train: pl.DataFrame, exclude: list[str] | tuple = ()) -> tuple[list[str], list[str]]:
    """Aday özelliklerden yasaklıları ve EĞİTİMDE sabit olanları çıkarır."""
    cands = [c for c in CANDIDATE_FEATURES if c not in set(exclude)]
    leaked = set(cands) & set(FORBIDDEN_FEATURES)
    if leaked:
        raise ValueError(f"Yasaklı alanlar özellik listesinde: {leaked}")
    stats = train.select([pl.col(c).min().alias(f"{c}__min") for c in cands]
                         + [pl.col(c).max().alias(f"{c}__max") for c in cands]).row(0, named=True)
    constant = [c for c in cands if stats[f"{c}__min"] == stats[f"{c}__max"]]
    return [c for c in cands if c not in constant], constant


def to_xy(df: pl.DataFrame, feats: list[str], target: str = "is_attack"):
    X = df.select([pl.col(c).cast(pl.Float32) for c in feats]).to_numpy()
    y = df[target].to_numpy()
    return X, y


def downsample(df: pl.DataFrame, cap: int | None, seed: int = SEED) -> pl.DataFrame:
    """Eğitim bölümünü en fazla `cap` satıra indirir: saldırı satırları korunur, normal
    trafik rastgele seyreltilir. Yalnızca eğitim bölümüne uygulanır."""
    if cap is None or df.height <= cap:
        return df
    atk = df.filter(pl.col("is_attack"))
    ben = df.filter(~pl.col("is_attack"))
    if atk.height >= cap // 2:
        atk = atk.sample(n=cap // 2, seed=seed)
    ben = ben.sample(n=min(ben.height, cap - atk.height), seed=seed)
    return pl.concat([atk, ben]).sample(fraction=1.0, shuffle=True, seed=seed)


# ---- modeller -------------------------------------------------------------------------
def _signed_log1p(x):
    return np.sign(x) * np.log1p(np.abs(x))


def make_logreg() -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("log", FunctionTransformer(_signed_log1p, feature_names_out="one-to-one")),
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(C=1.0, class_weight="balanced", max_iter=500, random_state=SEED)),
    ])


LGBM_PARAMS = dict(
    n_estimators=2000, learning_rate=0.05, num_leaves=63, min_child_samples=100,
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
    class_weight="balanced", random_state=SEED, n_jobs=os.cpu_count(), verbose=-1,
)


def fit_lgbm(Xtr, ytr, Xva, yva, params: dict | None = None, early_stopping: int = 100):
    import lightgbm as lgb
    p = dict(LGBM_PARAMS, **(params or {}))
    model = lgb.LGBMClassifier(**p)
    model.fit(Xtr, ytr, eval_X=(Xva,), eval_y=(yva,), eval_metric="average_precision",
              callbacks=[lgb.early_stopping(early_stopping, first_metric_only=True, verbose=False)])
    return model


# ---- eşikler ve metrikler -------------------------------------------------------------
def threshold_best_f1(y: np.ndarray, s: np.ndarray) -> float:
    order = np.argsort(-s, kind="stable")
    ys, ss = y[order].astype(np.int64), s[order]
    tp = np.cumsum(ys)
    fp = np.cumsum(1 - ys)
    # yalnızca farklı skor değerlerinin son indeksinde karar verilebilir
    last = np.r_[ss[1:] != ss[:-1], True]
    tp, fp, ss = tp[last], fp[last], ss[last]
    p = tp / np.maximum(tp + fp, 1)
    r = tp / max(ys.sum(), 1)
    f1 = np.where(p + r > 0, 2 * p * r / np.maximum(p + r, 1e-12), 0)
    return float(ss[int(np.argmax(f1))])


def threshold_for_fa_budget(y: np.ndarray, s: np.ndarray, per_1000: float) -> float:
    """Doğrulamada 1.000 normal akış başına en fazla `per_1000` yanlış alarm veren en düşük eşik."""
    ben = np.sort(s[y == 0])[::-1]
    k = int(np.floor(per_1000 / 1000 * len(ben)))
    if k >= len(ben):
        return float(ben[-1])
    return float(np.nextafter(ben[k], np.inf))  # skor >= eşik -> alarm; en fazla k normal akış


def binary_metrics(y: np.ndarray, s: np.ndarray, thr: float) -> dict:
    pred = s >= thr
    y = y.astype(bool)
    tp = int(np.sum(pred & y)); fp = int(np.sum(pred & ~y))
    fn = int(np.sum(~pred & y)); tn = int(np.sum(~pred & ~y))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "threshold": float(thr), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": prec, "recall": rec, "f1": f1,
        "fa_per_1000_benign": 1000 * fp / max(fp + tn, 1),
        "accuracy": (tp + tn) / max(len(y), 1),
    }


def ranking_metrics(y: np.ndarray, s: np.ndarray) -> dict:
    if len(np.unique(y)) < 2:
        return {"pr_auc": None, "roc_auc": None, "prevalence": float(np.mean(y))}
    return {"pr_auc": float(average_precision_score(y, s)), "roc_auc": float(roc_auc_score(y, s)),
            "prevalence": float(np.mean(y))}


def per_label(labels: np.ndarray, s: np.ndarray, thr: float) -> list[dict]:
    out = []
    for lab in sorted(set(labels.tolist())):
        m = labels == lab
        hit = int(np.sum(s[m] >= thr))
        out.append({"label": lab, "n": int(m.sum()), "flagged": hit, "flag_rate": hit / int(m.sum())})
    return out


def full_eval(df: pl.DataFrame, s: np.ndarray, thresholds: dict[str, float]) -> dict:
    y = df["is_attack"].to_numpy()
    res = {"rows": df.height, "attack_rows": int(y.sum()), **ranking_metrics(y, s), "operating_points": {}}
    labels = df["label"].to_numpy()
    for name, thr in thresholds.items():
        op = binary_metrics(y, s, thr)
        op["per_label"] = per_label(labels, s, thr)
        res["operating_points"][name] = op
    return res


def choose_thresholds(y_val: np.ndarray, s_val: np.ndarray) -> dict[str, float]:
    th = {"best_f1_val": threshold_best_f1(y_val, s_val)}
    for b in FA_BUDGETS:
        th[f"fa<={b:g}/1000_val"] = threshold_for_fa_budget(y_val, s_val, b)
    return th


# ---- süre/donanım ---------------------------------------------------------------------
@dataclass
class Timer:
    seconds: float = 0.0
    _t0: float = field(default=0.0, repr=False)

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self._t0


def latency_single_row(predict_fn, X: np.ndarray, n: int = 2000, seed: int = SEED) -> dict:
    """Tek akışlık çağrı gecikmesi (model düzeyi, ms)."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(X), size=n)
    for i in idx[:50]:  # ısınma
        predict_fn(X[i:i + 1])
    times = []
    for i in idx:
        t0 = time.perf_counter()
        predict_fn(X[i:i + 1])
        times.append((time.perf_counter() - t0) * 1000)
    t = np.array(times)
    return {"n_calls": n, "p50_ms": float(np.percentile(t, 50)), "p95_ms": float(np.percentile(t, 95)),
            "p99_ms": float(np.percentile(t, 99))}


def throughput(predict_fn, X: np.ndarray, n: int = 200_000) -> dict:
    Xb = X[:n]
    t0 = time.perf_counter()
    predict_fn(Xb)
    dt = time.perf_counter() - t0
    return {"batch_rows": len(Xb), "seconds": dt, "rows_per_s": len(Xb) / dt}


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def environment() -> dict:
    import lightgbm, sklearn, polars, pyarrow, psycopg
    env = {
        "os": platform.platform(), "python": platform.python_version(),
        "cpu": platform.processor(), "logical_cpus": os.cpu_count(),
        "versions": {"scikit-learn": sklearn.__version__, "lightgbm": lightgbm.__version__,
                     "polars": polars.__version__, "pyarrow": pyarrow.__version__,
                     "numpy": np.__version__, "psycopg": psycopg.__version__},
        "seed": SEED,
    }
    if platform.system() == "Windows":
        cpu = _run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"])
        ram = _run(["powershell", "-NoProfile", "-Command",
                    "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        env["cpu"] = cpu or env["cpu"]
        env["ram_gb"] = round(int(ram) / 2**30, 1) if ram.isdigit() else None
    gpu = _run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    env["gpu"] = (gpu + " (kullanılmadı; eğitim CPU'da)") if gpu else None
    return env
