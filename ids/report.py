"""meta şeması ve reports/results/*.json -> reports/*.md (python -m ids report).

Raporlardaki her sayı veritabanından ya da gerçekten çalıştırılmış deney çıktısından okunur.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import db
from .config import REPORTS_DIR, db_name

RESULTS_DIR = REPORTS_DIR / "results"


def md_table(headers: list[str], rows: list[list]) -> str:
    def fmt(v):
        if v is None:
            return "—"
        if isinstance(v, float):
            return f"{v:,.4f}" if abs(v) < 100 else f"{v:,.1f}"
        if isinstance(v, int):
            return f"{v:,}"
        return str(v)
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(fmt(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def q(conn, sql, *p):
    return [list(r) for r in conn.execute(sql, p).fetchall()]


# ---------------------------------------------------------------------------------------
def data_audit(conn) -> str:
    s = ["# Veri denetimi ve temizleme raporu", "",
         f"Kaynak veritabanı: `{db_name()}`. Üretim: `python -m ids report`.", ""]
    s += ["## İçe aktarılan dosyalar", "", md_table(
        ["dosya", "gün", "boyut (MB)", "fiziksel satır", "tekrar başlık", "bozuk satır", "yüklenen", "süre (s)", "satır/s"],
        q(conn, """SELECT source_file, capture_day::text, round(file_bytes/1e6)::int, lines_total, header_repeats,
                          malformed_lines, rows_loaded, round(seconds::numeric,1)::float,
                          round(rows_loaded/seconds)::int FROM meta.ingest_files ORDER BY capture_day""")), ""]
    s += ["> 1.048.575 = Excel'in satır sınırı (1.048.576) − başlık. Bu değerde biten dosyalar resmi "
          "işlenmiş CSV'lerde kesilmiştir; kesilen akışlar bu projede geri getirilemez (bkz. README).", ""]
    s += ["## Temizleme kuralları (tüm günler)", "", md_table(
        ["adım", "kural", "işlem", "etkilenen"],
        q(conn, """SELECT step, rule, action, sum(rows_affected)::bigint FROM meta.cleaning_log
                   GROUP BY 1,2,3 ORDER BY 1""")), ""]
    days = q(conn, "SELECT DISTINCT details->>'day' FROM meta.cleaning_log ORDER BY 1")
    steps = q(conn, "SELECT DISTINCT step FROM meta.cleaning_log ORDER BY 1")
    rows = []
    for (d,) in days:
        vals = dict(q(conn, "SELECT step, sum(rows_affected)::bigint FROM meta.cleaning_log "
                            "WHERE details->>'day' = %s GROUP BY 1", d))
        rows.append([d] + [vals.get(st, 0) for (st,) in steps])
    s += ["### Gün bazında", "", md_table(["gün"] + [f"adım {st}" for (st,) in steps], rows), "",
          "Adım 0 = ham, 9 = temiz satır; 2 ve 5 düzeltmedir (satır düşürmez; 5 hücre sayar).", ""]
    s += ["## Sütun sorunları (düşürme kurallarından geçen ham satırlarda)", "", md_table(
        ["sütun", "sorun", "hücre"],
        q(conn, """SELECT details->>'column', details->>'issue', sum(value)::bigint FROM meta.audit
                   WHERE check_name='column_issue' GROUP BY 1,2 ORDER BY 3 DESC""")), "",
        "`init_*_win_byts = -1` CICFlowMeter'ın \"gözlenmedi\" işaretidir; korunur, düzeltme sayımına girmez.", ""]
    s += ["## Tutarlılık denetimleri (bilgi amaçlı, satır düşürülmez)", "", md_table(
        ["kural", "satır"],
        q(conn, """SELECT details->>'rule', sum(value)::bigint FROM meta.audit WHERE check_name='consistency'
                   GROUP BY 1 ORDER BY 1""")), ""]
    s += ["## Etiketlerin zaman aralığı (12 saat düzeltmesi sonrası)", "", md_table(
        ["gün", "etiket", "ilk", "son", "ham satır"],
        q(conn, """SELECT capture_day::text, label, details->>'min', details->>'max', value::bigint
                   FROM meta.audit WHERE check_name='label_time_range' ORDER BY 1, 3""")), ""]
    s += ["## Sınıf dağılımı: ham → temiz", "", md_table(
        ["etiket", "ham", "temiz", "temiz payı"],
        q(conn, """WITH r AS (SELECT label, sum(value)::bigint n FROM meta.audit WHERE check_name='raw_rows' GROUP BY 1),
                        c AS (SELECT label, count(*) n FROM clean.flows GROUP BY 1)
                   SELECT r.label, r.n, coalesce(c.n,0), round(100.0*coalesce(c.n,0)/sum(coalesce(c.n,0)) OVER (),3)::float
                   FROM r LEFT JOIN c USING (label) ORDER BY 3 DESC""")), ""]
    return "\n".join(s)


def splits(conn) -> str:
    s = ["# Ayrım tasarımı ve sızıntı denetimleri", ""]
    for scheme, params in q(conn, "SELECT scheme, params FROM meta.split_definitions ORDER BY 1"):
        s += [f"**{scheme}**: {params.get('description')}", ""]
    s += ["## Saldırı olayları (gün içi, etiketlerden türetilmiş)", "", md_table(
        ["gün", "olay", "başlangıç", "bitiş", "etiketler"],
        q(conn, "SELECT capture_day::text, episode_no, start_ts::text, end_ts::text, labels FROM features.episodes ORDER BY 1,2")), ""]
    for scheme in ("temporal", "random"):
        rows = q(conn, """SELECT label,
                    sum(rows) FILTER (WHERE split='train')::bigint, sum(rows) FILTER (WHERE split='val')::bigint,
                    sum(rows) FILTER (WHERE split='test')::bigint, coalesce(sum(rows) FILTER (WHERE split='gap'),0)::bigint
                  FROM meta.split_summary WHERE scheme=%s GROUP BY 1 ORDER BY 2 DESC NULLS LAST""", scheme)
        tot = [sum((r[i] or 0) for r in rows) for i in range(1, 5)]
        s += [f"## Ayrım `{scheme}`: etiket × bölüm (satır)", "",
              md_table(["etiket", "train", "val", "test", "gap"], rows + [["**toplam**"] + tot]), ""]
    s += ["## Sızıntı denetimleri", "", md_table(
        ["denetim", "ayrım", "bölüm", "satır", "çakışan", "oran %", "ayrıntı"],
        q(conn, """SELECT check_name, scheme, split, rows, overlapping_rows,
                          round(100.0*overlapping_rows/nullif(rows,0),2)::float, details::text
                   FROM meta.leakage_checks ORDER BY 1,2,3""")), "",
        "- `exact_feature_vector_in_train`: val/test satırının tüm akış ölçümleri (zaman damgası hariç) eğitimdeki "
        "bir satırla birebir aynı. Bu tür kayıtlar zamansal ayrımda da kaçınılmazdır (ör. aynı kaba kuvvet isteği "
        "binlerce kez). Bu yüzden test sonuçları ayrıca **eğitimde görülmemiş vektörler** alt kümesinde raporlanır.",
        "- `segment_purity`: bir zaman bloğu/olay parçası birden fazla bölüme düşmemeli (0 olmalı).",
        "- `min_seconds_between_different_split_blocks`: farklı bölümlü komşu parçalar arasındaki boşluk.", ""]
    return "\n".join(s)


def _runs(d: dict):
    """Deney sözlüğünden yalnızca alt çalıştırmaları döner (experiment_seconds gibi sayıları atlar)."""
    return [(k, v) for k, v in d.items() if isinstance(v, dict) and "test" in v]


def _op(ev, name="best_f1_val"):
    return ev["operating_points"][name]


def results() -> str:
    dbn = db_name()
    s = ["# Deney sonuçları", "", f"Kaynak: `reports/results/*_{dbn}.json` (gerçekten çalıştırılmış deneyler).", ""]
    p = RESULTS_DIR / f"main_{dbn}.json"
    if p.exists():
        r = json.loads(p.read_text(encoding="utf-8"))
        env = r["environment"]
        s += ["## Ortam", "", f"- CPU: {env.get('cpu')} ({env.get('logical_cpus')} mantıksal çekirdek), RAM: {env.get('ram_gb')} GB",
              f"- GPU: {env.get('gpu')}", f"- OS: {env.get('os')}, Python {env.get('python')}",
              f"- Sürümler: {env.get('versions')}", f"- Tohum: {env.get('seed')}", ""]
        d = r["data"]
        s += ["## Ana deney (zamansal ayrım)", "", md_table(
            ["bölüm", "satır", "saldırı", "saldırı %"],
            [[k, v["rows"], v["attack_rows"], 100 * v["attack_rows"] / v["rows"]] for k, v in d.items()]), ""]
        rows = []
        for m, res in r["results"]["models"].items():
            for part in ("val", "test", "test_unseen_feature_vectors"):
                if part not in res:
                    continue
                ev = res[part]; o = _op(ev)
                rows.append([m, part, ev["rows"], ev["pr_auc"], o["precision"], o["recall"], o["f1"],
                             o["fa_per_1000_benign"], o["accuracy"], o["threshold"]])
        s += [f"Eşik: doğrulamada F1'i en büyükleyen eşik. En iyi model (doğrulama PR-AUC): **{r['results']['best_model']}**.", "",
              md_table(["model", "bölüm", "satır", "PR-AUC", "precision", "recall", "F1", "YA/1000 normal", "accuracy", "eşik"], rows), ""]
        best = r["results"]["best_model"]
        te = r["results"]["models"][best]["test"]
        o = _op(te)
        s += [f"### {best}: test karışıklık matrisi (eşik = {o['threshold']:.6f})", "",
              md_table(["", "tahmin BENIGN", "tahmin ATTACK"],
                       [["gerçek BENIGN", o["tn"], o["fp"]], ["gerçek ATTACK", o["fn"], o["tp"]]]), ""]
        s += [f"### {best}: farklı eşiklerde saldırı yakalama ve yanlış alarm yükü (eşikler doğrulamada seçildi)", "",
              md_table(["çalışma noktası", "eşik", "test recall", "test precision", "test YA/1000 normal", "test FP", "val YA/1000"],
                       [[k, v["threshold"], v["recall"], v["precision"], v["fa_per_1000_benign"], v["fp"],
                         r["results"]["models"][best]["val"]["operating_points"][k]["fa_per_1000_benign"]]
                        for k, v in te["operating_points"].items()]), ""]
        s += [f"### {best}: saldırı türü bazında test (eşik = en iyi F1)", "",
              md_table(["etiket", "test satırı", "alarm", "oran"],
                       [[x["label"], x["n"], x["flagged"], x["flag_rate"]] for x in o["per_label"]]), "",
              "Benign satırı için oran = yanlış alarm oranı; saldırı satırları için yakalama (recall).", ""]
        if "test_unseen_feature_vectors" in r["results"]["models"][best]:
            ou = _op(r["results"]["models"][best]["test_unseen_feature_vectors"])
            s += [f"### {best}: eğitimde birebir görülmemiş özellik vektörleri (test alt kümesi)", "",
                  md_table(["etiket", "satır", "alarm", "oran"],
                           [[x["label"], x["n"], x["flagged"], x["flag_rate"]] for x in ou["per_label"]]), ""]
        lat = r["results"]["latency"]
        s += ["### Süre ve gecikme", "", md_table(["ölçüm", "değer"], [
            ["LightGBM eğitim (s)", r["results"]["timings"].get("lightgbm_train_s")],
            ["Lojistik regresyon eğitim (s)", r["results"]["timings"].get("logreg_train_s")],
            ["tek akış, model p50 (ms)", lat["single_row"]["p50_ms"]],
            ["tek akış, model p95 (ms)", lat["single_row"]["p95_ms"]],
            ["tek akış, model p99 (ms)", lat["single_row"]["p99_ms"]],
            ["toplu puanlama (akış/s)", lat["batch"]["rows_per_s"]]]), ""]
    p = RESULTS_DIR / f"random_split_{dbn}.json"
    if p.exists():
        r = json.loads(p.read_text(encoding="utf-8"))
        rows = []
        for sch, v in _runs(r["results"]):
            for part in ("test", "test_unseen_feature_vectors"):
                ev = v[part]; o = _op(ev)
                rows.append([sch, part, ev["rows"], ev["pr_auc"], o["precision"], o["recall"], o["f1"], o["fa_per_1000_benign"]])
        s += ["## Rastgele satır ayrımı vs zamansal ayrım (LightGBM, aynı eğitim boyutu)", "",
              md_table(["ayrım", "test kümesi", "satır", "PR-AUC", "precision", "recall", "F1", "YA/1000"], rows), ""]
    p = RESULTS_DIR / f"ablation_{dbn}.json"
    if p.exists():
        r = json.loads(p.read_text(encoding="utf-8"))
        rows = [[k, v["n_features"], v["test"]["pr_auc"], _op(v["test"])["precision"], _op(v["test"])["recall"],
                 _op(v["test"])["f1"], _op(v["test"])["fa_per_1000_benign"],
                 _op(v["test_unseen_feature_vectors"])["recall"]] for k, v in _runs(r["results"])]
        s += ["## Ablasyon (LightGBM, zamansal ayrım, test)", "",
              md_table(["varyant", "özellik", "PR-AUC", "precision", "recall", "F1", "YA/1000", "recall (görülmemiş)"], rows), ""]
    p = RESULTS_DIR / f"multiclass_{dbn}.json"
    if p.exists():
        r = json.loads(p.read_text(encoding="utf-8"))["results"]
        rows = [[c, int(r["report"][c]["support"]), r["report"][c]["precision"], r["report"][c]["recall"], r["report"][c]["f1-score"]]
                for c in r["classes"]]
        s += ["## Çok sınıflı deney (saldırı türü, LightGBM, zamansal ayrım, test)", "",
              f"Macro-F1 = {r['macro_f1']:.4f}", "", md_table(["sınıf", "test satırı", "precision", "recall", "F1"], rows), ""]
        cm = r["confusion_matrix"]
        s += ["Karışıklık matrisi (satır = gerçek, sütun = tahmin; sınıf sırası yukarıdaki gibi):", "",
              md_table(["gerçek \\ tahmin"] + [str(i) for i in range(len(cm))],
                       [[f"{i}: {c}"] + cm[i] for i, c in enumerate(r["classes"])]), ""]
    p = RESULTS_DIR / f"lodo_{dbn}.json"
    if p.exists():
        r = json.loads(p.read_text(encoding="utf-8"))["results"]
        rows = []
        for d, v in _runs(r):
            o = _op(v["test"])
            rec = {x["label"]: x["flag_rate"] for x in o["per_label"]}
            rows.append([d, ", ".join(v["held_out_attack_labels"]) or "—",
                         ", ".join(v["held_out_labels_seen_in_train"]) or "hiçbiri",
                         v["test"]["rows"], v["test"]["pr_auc"], o["precision"], o["recall"], o["fa_per_1000_benign"],
                         "; ".join(f"{k}: {x:.3f}" for k, x in rec.items() if k != "Benign")])
        s += ["## Zorlayıcı test: gün dışarıda bırakma (leave-one-day-out, LightGBM)", "",
              "Eşik, kalan günlerin doğrulama bölümünde seçildi; dışarıda bırakılan gün hiç görülmedi.", "",
              md_table(["test günü", "saldırı türleri", "eğitimde de olanlar", "satır", "PR-AUC", "precision",
                        "recall", "YA/1000", "tür bazında recall"], rows), ""]
    return "\n".join(s)


def performance(conn) -> str:
    s = ["# Performans: süreler, boyutlar, karşılaştırmalar", ""]
    s += ["## Veritabanı boyutu", "", md_table(
        ["şema", "boyut (MB)", "satır (tahmini)"],
        q(conn, """SELECT n.nspname, round(sum(pg_total_relation_size(c.oid))/1e6)::int, sum(c.reltuples)::bigint
                   FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE c.relkind='r' AND n.nspname IN ('raw','clean','features','meta') GROUP BY 1 ORDER BY 1""")),
        "", f"Toplam veritabanı: {q(conn, 'SELECT pg_size_pretty(pg_database_size(current_database()))')[0][0]}", ""]
    s += ["## Aşama süreleri (son çalıştırma)", "", md_table(
        ["aşama", "adım", "süre (s)", "satır"],
        q(conn, """SELECT DISTINCT ON (stage, step) stage, step, round(seconds::numeric,1)::float, rows_affected
                   FROM meta.timings ORDER BY stage, step, id DESC""")), ""]
    s += ["## Aşama toplamları", "", md_table(
        ["aşama", "toplam süre (s)"],
        q(conn, """WITH last AS (SELECT DISTINCT ON (stage, step) * FROM meta.timings ORDER BY stage, step, id DESC)
                   SELECT stage, round(sum(seconds)::numeric,1)::float FROM last GROUP BY 1 ORDER BY 1""")), ""]
    s += ["## Karşılaştırmalar (`python -m ids bench`)", "", md_table(
        ["karşılaştırma", "varyant", "ölçüt", "değer", "ayrıntı"],
        q(conn, "SELECT name, variant, metric, value, details::text FROM meta.benchmarks ORDER BY id")), ""]
    plans = q(conn, "SELECT DISTINCT ON (name) name FROM meta.explain_plans ORDER BY name, id DESC")
    s += ["## EXPLAIN ANALYZE çıktıları", ""] + [f"- [`{n}`](explain/{n}.txt)" for (n,) in plans] + [""]
    return "\n".join(s)


def run() -> None:
    # Tam veri (ids) raporları reports/ altına, diğer veritabanları reports/<db>/ altına yazılır.
    out_dir = REPORTS_DIR if db_name() == "ids" else REPORTS_DIR / db_name()
    out_dir.mkdir(parents=True, exist_ok=True)
    with db.connect() as conn:
        out = {"data_audit.md": data_audit(conn), "splits.md": splits(conn), "performance.md": performance(conn)}
    out["results.md"] = results()
    for name, text in out.items():
        (out_dir / name).write_text(text + "\n", encoding="utf-8")
        print(f"  {out_dir / name}")
