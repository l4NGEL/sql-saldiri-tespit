-- 30_splits_leakage.sql — ayrım özetleri ve veri sızıntısı denetimleri (meta şemasına yazar).

-- Ayrım x etiket dağılımı ---------------------------------------------------------------
DELETE FROM meta.split_summary;
INSERT INTO meta.split_summary(scheme, split, label, rows)
SELECT 'temporal', f.split_temporal, c.label, count(*)
FROM clean.flows c JOIN features.flow_features f USING (capture_day, flow_id)
GROUP BY 2, 3;
INSERT INTO meta.split_summary(scheme, split, label, rows)
SELECT 'random', f.split_rand, c.label, count(*)
FROM clean.flows c JOIN features.flow_features f USING (capture_day, flow_id)
GROUP BY 2, 3;

-- Eğitim bölümündeki özellik vektörü özetleri (dışa aktarımda "test satırı eğitimde
-- birebir görüldü mü?" bayrağı için de kullanılır) --------------------------------------
DROP TABLE IF EXISTS features.train_fv_temporal;
CREATE TABLE features.train_fv_temporal AS
SELECT DISTINCT c.fv_hash FROM clean.flows c JOIN features.flow_features f USING (capture_day, flow_id)
WHERE f.split_temporal = 'train';
CREATE UNIQUE INDEX ON features.train_fv_temporal(fv_hash);

DROP TABLE IF EXISTS features.train_fv_random;
CREATE TABLE features.train_fv_random AS
SELECT DISTINCT c.fv_hash FROM clean.flows c JOIN features.flow_features f USING (capture_day, flow_id)
WHERE f.split_rand = 'train';
CREATE UNIQUE INDEX ON features.train_fv_random(fv_hash);
ANALYZE features.train_fv_temporal;
ANALYZE features.train_fv_random;

DELETE FROM meta.leakage_checks;

-- 1) Her akış tek bir bölümde mi? (flow_id tekrarı olmamalı)
INSERT INTO meta.leakage_checks(check_name, scheme, split, rows, overlapping_rows, details)
SELECT 'flow_id_unique', 'all', 'all', count(*), count(*) - count(DISTINCT flow_id), '{}'::jsonb
FROM features.flow_features;

-- 2) Zaman bloğu saflığı: bir blok (gap hariç) birden fazla bölüme düşmemeli
INSERT INTO meta.leakage_checks(check_name, scheme, split, rows, overlapping_rows, details)
SELECT 'segment_purity', 'temporal', 'all', count(*), count(*) FILTER (WHERE n_splits > 1), '{}'::jsonb
FROM (SELECT capture_day, segment_id, count(DISTINCT split_temporal) AS n_splits
      FROM features.flow_features WHERE split_temporal <> 'gap' GROUP BY 1, 2) b;

-- 3) Birebir aynı özellik vektörünün eğitim ile val/test arasında paylaşılması
--    (zaman damgası farklı ama tüm akış ölçümleri aynı kayıtlar)
INSERT INTO meta.leakage_checks(check_name, scheme, split, rows, overlapping_rows, details)
SELECT 'exact_feature_vector_in_train', 'temporal', f.split_temporal, count(*),
       count(*) FILTER (WHERE t.fv_hash IS NOT NULL),
       jsonb_build_object(
         'attack_rows', count(*) FILTER (WHERE c.is_attack),
         'attack_overlap', count(*) FILTER (WHERE c.is_attack AND t.fv_hash IS NOT NULL),
         'benign_rows', count(*) FILTER (WHERE NOT c.is_attack),
         'benign_overlap', count(*) FILTER (WHERE NOT c.is_attack AND t.fv_hash IS NOT NULL))
FROM clean.flows c JOIN features.flow_features f USING (capture_day, flow_id)
LEFT JOIN features.train_fv_temporal t ON t.fv_hash = c.fv_hash
WHERE f.split_temporal IN ('val', 'test')
GROUP BY f.split_temporal;

INSERT INTO meta.leakage_checks(check_name, scheme, split, rows, overlapping_rows, details)
SELECT 'exact_feature_vector_in_train', 'random', f.split_rand, count(*),
       count(*) FILTER (WHERE t.fv_hash IS NOT NULL),
       jsonb_build_object(
         'attack_rows', count(*) FILTER (WHERE c.is_attack),
         'attack_overlap', count(*) FILTER (WHERE c.is_attack AND t.fv_hash IS NOT NULL),
         'benign_rows', count(*) FILTER (WHERE NOT c.is_attack),
         'benign_overlap', count(*) FILTER (WHERE NOT c.is_attack AND t.fv_hash IS NOT NULL))
FROM clean.flows c JOIN features.flow_features f USING (capture_day, flow_id)
LEFT JOIN features.train_fv_random t ON t.fv_hash = c.fv_hash
WHERE f.split_rand IN ('val', 'test')
GROUP BY f.split_rand;

-- 4) Zamansal ayrılık: farklı bölümlere düşen ardışık bloklar arasındaki en küçük boşluk
--    (bir bloğun son akışı ile sonraki farklı bölümlü bloğun ilk akışı arası, saniye).
INSERT INTO meta.leakage_checks(check_name, scheme, split, rows, overlapping_rows, details)
SELECT 'min_seconds_between_different_split_blocks', 'temporal', 'all', count(*),
       count(*) FILTER (WHERE gap_s < 60),
       jsonb_build_object('min_gap_s', min(gap_s), 'median_gap_s',
                          percentile_cont(0.5) WITHIN GROUP (ORDER BY gap_s))
FROM (
    SELECT extract(epoch FROM lead(min_ts) OVER w - max_ts) AS gap_s,
           split_temporal, lead(split_temporal) OVER w AS next_split
    FROM (SELECT c.capture_day, f.segment_id, f.split_temporal, min(c.ts) AS min_ts, max(c.ts) AS max_ts
          FROM clean.flows c JOIN features.flow_features f USING (capture_day, flow_id)
          WHERE f.split_temporal <> 'gap' GROUP BY 1, 2, 3) b
    WINDOW w AS (PARTITION BY capture_day ORDER BY min_ts)
) x
WHERE next_split IS NOT NULL AND next_split <> split_temporal;
