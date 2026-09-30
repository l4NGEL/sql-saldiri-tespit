-- 20_features.sql — clean.flows -> features.flow_features (gün bazında, idempotent).
--
-- Tahmin anı = akışın BİTİŞ anı (end_ts = ts + flow_duration). CICFlowMeter bir akışın
-- kaydını ancak akış kapandığında üretir; bu yüzden pencere özetleri yalnızca bitiş anı
-- <= bu akışın bitiş anı olan (yani o an gerçekten görülmüş) akışlardan hesaplanır ve
-- akışın kendisi toplamlardan çıkarılır. Etiket hiçbir pencerede kullanılmaz.
--
-- Pencereler gün (sensör kaydı) içinde hesaplanır; test bölümündeki bir akışın penceresi
-- eğitim bölümündeki akışların HAM ölçümlerini görebilir — canlı sistemde de sensör önceki
-- tüm trafiği görür, etiket taşınmadığı için bu bir sızıntı değildir.

-- Ayrım tanımları (model eğitiminden önce sabitlenir) -----------------------------------
DELETE FROM meta.split_definitions;
INSERT INTO meta.split_definitions(scheme, params) VALUES
  ('temporal', jsonb_build_object(
       'description', 'Olay (saldırı patlaması) farkındalıklı kronolojik ayrım. Her gün saldırı '
                      || 'akışları zamana göre sıralanır; aralarında 5 dakikadan uzun boşluk olan '
                      || 'kümeler ayrı patlamadır. Her patlama, kendi saldırı akışlarının zamansal '
                      || '%60 ve %80 yüzdeliklerinden bölünür: öncesi train, arası val, sonrası test '
                      || '(test her zaman train''den sonradır). Her sınırdan sonra min(60 s, patlama '
                      || 'süresinin %5''i) gap; patlamanın 60 s öncesi/sonrası gap. Patlama içindeki '
                      || 'normal akışlar da aynı zaman sınırlarını izler. Patlama dışı (yalnız normal '
                      || 'trafik) zaman 10 dakikalık bloklara bölünür ve bloklar 5''li döngüyle '
                      || 'train,train,val,train,test atanır; bölüm değişen blok başındaki 60 s gap.',
       'episode_split', 'saldırı akışı zaman yüzdelikleri 0.6 / 0.8', 'episode_gap', 'min(60 s, %5)',
       'episode_break_seconds', 300, 'episode_pad_seconds', 60,
       'block_minutes', 10, 'cycle', jsonb_build_array('train','train','val','train','test'),
       'block_gap_seconds', 60)),
  ('random', jsonb_build_object(
       'description', 'Karşılaştırma amaçlı rastgele satır ayrımı: hash(flow_id) mod 100 -> '
                      || '<60 train, <80 val, diğer test. Benzer akışları iki tarafa dağıtır.',
       'train_pct', 60, 'val_pct', 20));

-- Saldırı patlamaları (gaps-and-islands): gün içinde saldırı akışları zamana göre sıralanır,
-- önceki saldırı akışından 5 dakikadan uzun sonra başlayan akış yeni patlama açar.
-- t60/t80: patlamadaki saldırı akışlarının zamansal %60 / %80 yüzdelikleri (bölüm sınırları).
-- Not: patlamalar etiketlerden türetilir; bu yalnızca AYRIMIN tasarımında kullanılır, modele
-- hiçbir zaman/olay bilgisi girmez. (İlk sürüm etiketlerin [ilk, son] aralığını zaman olarak
-- %60/%20/%20 bölüyordu; saldırı sonrası dağınık birkaç akış aralığı uzattığında DDoS-LOIC-HTTP'nin
-- neredeyse tamamı train'e düşüyordu. Bu yüzden yüzdelik tabanlı sürüme geçildi.)
DROP TABLE IF EXISTS features.episodes CASCADE;
CREATE TABLE features.episodes AS
WITH a AS (
    SELECT capture_day, ts, label,
           lag(ts) OVER (PARTITION BY capture_day ORDER BY ts) AS prev_ts
    FROM clean.flows WHERE is_attack
), g AS (
    SELECT *, sum(CASE WHEN prev_ts IS NULL OR ts > prev_ts + interval '5 minutes' THEN 1 ELSE 0 END)
                  OVER (PARTITION BY capture_day ORDER BY ts ROWS UNBOUNDED PRECEDING) AS episode_no
    FROM a
)
SELECT capture_day, episode_no::int, min(ts) AS start_ts, max(ts) AS end_ts,
       percentile_disc(0.6) WITHIN GROUP (ORDER BY ts) AS t60,
       percentile_disc(0.8) WITHIN GROUP (ORDER BY ts) AS t80,
       count(*) AS attack_flows,
       string_agg(DISTINCT label, ', ') AS labels
FROM g GROUP BY 1, 2;

DROP TABLE IF EXISTS features.flow_features CASCADE;
CREATE TABLE features.flow_features (
    flow_id                   bigint   NOT NULL,
    capture_day               date     NOT NULL,
    segment_id                integer  NOT NULL,   -- zaman bloğu ya da olay parçası
    split_temporal            text     NOT NULL,   -- temporal: train/val/test/gap
    split_rand                text     NOT NULL,   -- random: train/val/test
    -- satır düzeyi türetilmiş özellikler
    duration_s                real,
    fwd_bytes_per_pkt         real,
    bwd_bytes_per_pkt         real,
    bwd_fwd_byte_ratio        real,
    bwd_fwd_pkt_ratio         real,
    fwd_payload_share         real,
    log_total_bytes           real,
    flow_iat_cv               real,
    active_idle_ratio         real,
    no_response               smallint,
    zero_duration             smallint,
    well_known_port           smallint,
    -- zaman penceresi özetleri (yalnızca geçmiş, akışın kendisi hariç)
    w10_port_n                integer,
    w60_port_n                integer,
    w60_all_n                 integer,
    w60_port_share            real,
    w60_port_mean_fwd_pkts    real,
    w60_port_mean_duration_s  real,
    w60_port_noresp_share     real,
    w60_port_rst_share        real
) PARTITION BY LIST (capture_day);

CREATE OR REPLACE FUNCTION features.split_time_block(p_ts timestamp, p_day date) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    WITH b AS (
        SELECT floor(extract(epoch FROM p_ts - p_day::timestamp) / 600)::int AS block,
               extract(epoch FROM p_ts - p_day::timestamp)::numeric % 600  AS sec_in_block
    ), s AS (
        SELECT (ARRAY['train','train','val','train','test'])[block % 5 + 1]       AS split,
               (ARRAY['train','train','val','train','test'])[(block + 4) % 5 + 1] AS prev_split,
               sec_in_block
        FROM b
    )
    SELECT CASE WHEN split <> prev_split AND sec_in_block < 60 THEN 'gap' ELSE split END FROM s
$$;

DROP FUNCTION IF EXISTS features.episode_part(timestamp, timestamp, timestamp);
-- Patlama içindeki konum -> 0 train, 1 gap, 2 val, 3 gap, 4 test
CREATE OR REPLACE FUNCTION features.episode_part(p_ts timestamp, p_start timestamp, p_end timestamp,
                                                 p_t60 timestamp, p_t80 timestamp) RETURNS int
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    WITH x AS (SELECT least(60, 0.05 * extract(epoch FROM p_end - p_start)) * interval '1 second' AS g)
    SELECT CASE WHEN p_ts < p_t60         THEN 0
                WHEN p_ts < p_t60 + x.g   THEN 1
                WHEN p_ts < p_t80         THEN 2
                WHEN p_ts < p_t80 + x.g   THEN 3
                ELSE 4 END
    FROM x
$$;

CREATE OR REPLACE FUNCTION features.split_random(p_flow_id bigint) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN h < 60 THEN 'train' WHEN h < 80 THEN 'val' ELSE 'test' END
    FROM (SELECT abs(hashint8(p_flow_id)) % 100 AS h) x
$$;

CREATE OR REPLACE PROCEDURE features.build_day(p_day date)
LANGUAGE plpgsql AS $$
DECLARE
    part text := 'flow_features_' || to_char(p_day, 'YYYYMMDD');
    src  text := 'flows_' || to_char(p_day, 'YYYYMMDD');
BEGIN
    EXECUTE format('DROP TABLE IF EXISTS features.%I', part);
    EXECUTE format('CREATE TABLE features.%I (LIKE features.flow_features)', part);
    EXECUTE format('ALTER TABLE features.%I ADD CONSTRAINT %I CHECK (capture_day = %L)', part, part || '_day', p_day);
    EXECUTE format($q$
    INSERT INTO features.%I
    SELECT
        c.flow_id,
        c.capture_day,
        CASE WHEN e.episode_no IS NULL THEN floor(extract(epoch FROM c.ts - c.capture_day::timestamp) / 600)::int
             WHEN c.ts < e.start_ts OR c.ts > e.end_ts THEN -1
             ELSE 100000 + e.episode_no * 10 + features.episode_part(c.ts, e.start_ts, e.end_ts, e.t60, e.t80) END,
        CASE WHEN e.episode_no IS NULL THEN features.split_time_block(c.ts, c.capture_day)
             WHEN c.ts < e.start_ts OR c.ts > e.end_ts THEN 'gap'
             ELSE (ARRAY['train','gap','val','gap','test'])[features.episode_part(c.ts, e.start_ts, e.end_ts, e.t60, e.t80) + 1] END,
        features.split_random(c.flow_id),
        -- satır düzeyi
        c.flow_duration / 1e6,
        c.totlen_fwd_pkts / nullif(c.tot_fwd_pkts, 0),
        c.totlen_bwd_pkts / nullif(c.tot_bwd_pkts, 0),
        c.totlen_bwd_pkts / (c.totlen_fwd_pkts + 1),
        c.tot_bwd_pkts / nullif(c.tot_fwd_pkts, 0),
        c.totlen_fwd_pkts / nullif(c.totlen_fwd_pkts + c.fwd_header_len, 0),
        ln(1 + c.totlen_fwd_pkts + c.totlen_bwd_pkts),
        c.flow_iat_std / nullif(c.flow_iat_mean, 0),
        c.active_mean / (c.idle_mean + 1),
        (c.tot_bwd_pkts = 0)::int,
        (c.flow_duration = 0)::int,
        (c.dst_port < 1024)::int,
        -- Not: float toplamlarının kayan-pencere ters fonksiyonu yoktur (her satırda yeniden
        -- toplanır); tamsayıya çevrilen toplamlar ise O(1) güncellenir.
        -- pencereler: RANGE çerçevesi bitiş zamanına göre; CURRENT ROW eşzamanlı bitenleri de
        -- kapsar (onlar da o an görülmüştür). Akışın kendi katkısı çıkarılır.
        count(*) OVER w10p - 1,
        count(*) OVER w60p - 1,
        count(*) OVER w60a - 1,
        (count(*) OVER w60p - 1)::real / nullif(count(*) OVER w60a - 1, 0),
        (sum(c.tot_fwd_pkts::bigint) OVER w60p - c.tot_fwd_pkts::bigint)::real / nullif(count(*) OVER w60p - 1, 0),
        (sum(c.flow_duration::bigint) OVER w60p - c.flow_duration::bigint) / 1e6 / nullif(count(*) OVER w60p - 1, 0),
        (sum((c.tot_bwd_pkts = 0)::int) OVER w60p - (c.tot_bwd_pkts = 0)::int)::real / nullif(count(*) OVER w60p - 1, 0),
        (sum((c.rst_flag_cnt > 0)::int) OVER w60p - (c.rst_flag_cnt > 0)::int)::real / nullif(count(*) OVER w60p - 1, 0)
    FROM clean.%I c
    LEFT JOIN features.episodes e
           ON e.capture_day = c.capture_day
          AND c.ts BETWEEN e.start_ts - interval '60 seconds' AND e.end_ts + interval '60 seconds'
    WINDOW
        w10p AS (PARTITION BY c.dst_port ORDER BY c.end_ts RANGE BETWEEN interval '10 seconds' PRECEDING AND CURRENT ROW),
        w60p AS (PARTITION BY c.dst_port ORDER BY c.end_ts RANGE BETWEEN interval '60 seconds' PRECEDING AND CURRENT ROW),
        w60a AS (ORDER BY c.end_ts RANGE BETWEEN interval '60 seconds' PRECEDING AND CURRENT ROW)
    $q$, part, src);
    EXECUTE format('ALTER TABLE features.flow_features ATTACH PARTITION features.%I FOR VALUES IN (%L)', part, p_day);
END $$;
