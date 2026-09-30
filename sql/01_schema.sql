-- 01_schema.sql — şemalar ve tablolar (idempotent).
-- raw   : CSV'nin tipli, satır satır karşılığı (hiçbir şey silinmez, günlere göre bölümlü)
-- clean : denetimden geçmiş, tekrarsız kayıtlar (günlere göre bölümlü)
-- features : SQL ile üretilen türetilmiş + zaman penceresi özellikleri ve ayrım etiketleri
-- meta  : içe aktarma, temizleme, zamanlama, EXPLAIN ve deney kayıtları

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS clean;
CREATE SCHEMA IF NOT EXISTS features;
CREATE SCHEMA IF NOT EXISTS meta;

-- Bölümlendirme: yakalama günü (LIST). Her gün ayrı CSV ve ayrı saldırı senaryosu
-- olduğundan gün, hem yükleme/yeniden yükleme birimi hem de pencere hesaplarının
-- doğal sınırıdır. Tek günlük sorgular yalnızca ilgili bölümü tarar (partition pruning).
CREATE TABLE IF NOT EXISTS raw.flows (
    capture_day            date      NOT NULL,
    line_no                bigint    NOT NULL,   -- CSV'deki fiziksel satır numarası (başlık = 1)
    flow_key               text,                 -- yalnız 20-02 dosyasında
    src_ip                 inet,
    src_port               integer,
    dst_ip                 inet,
    dst_port               integer,
    protocol               smallint,
    ts                     timestamp,
    flow_duration          numeric,
    tot_fwd_pkts           numeric,
    tot_bwd_pkts           numeric,
    totlen_fwd_pkts        numeric,
    totlen_bwd_pkts        numeric,
    fwd_pkt_len_max        numeric,
    fwd_pkt_len_min        numeric,
    fwd_pkt_len_mean       numeric,
    fwd_pkt_len_std        numeric,
    bwd_pkt_len_max        numeric,
    bwd_pkt_len_min        numeric,
    bwd_pkt_len_mean       numeric,
    bwd_pkt_len_std        numeric,
    flow_byts_s            numeric,
    flow_pkts_s            numeric,
    flow_iat_mean          numeric,
    flow_iat_std           numeric,
    flow_iat_max           numeric,
    flow_iat_min           numeric,
    fwd_iat_tot            numeric,
    fwd_iat_mean           numeric,
    fwd_iat_std            numeric,
    fwd_iat_max            numeric,
    fwd_iat_min            numeric,
    bwd_iat_tot            numeric,
    bwd_iat_mean           numeric,
    bwd_iat_std            numeric,
    bwd_iat_max            numeric,
    bwd_iat_min            numeric,
    fwd_psh_flags          numeric,
    bwd_psh_flags          numeric,
    fwd_urg_flags          numeric,
    bwd_urg_flags          numeric,
    fwd_header_len         numeric,
    bwd_header_len         numeric,
    fwd_pkts_s             numeric,
    bwd_pkts_s             numeric,
    pkt_len_min            numeric,
    pkt_len_max            numeric,
    pkt_len_mean           numeric,
    pkt_len_std            numeric,
    pkt_len_var            numeric,
    fin_flag_cnt           numeric,
    syn_flag_cnt           numeric,
    rst_flag_cnt           numeric,
    psh_flag_cnt           numeric,
    ack_flag_cnt           numeric,
    urg_flag_cnt           numeric,
    cwe_flag_count         numeric,
    ece_flag_cnt           numeric,
    down_up_ratio          numeric,
    pkt_size_avg           numeric,
    fwd_seg_size_avg       numeric,
    bwd_seg_size_avg       numeric,
    fwd_byts_b_avg         numeric,
    fwd_pkts_b_avg         numeric,
    fwd_blk_rate_avg       numeric,
    bwd_byts_b_avg         numeric,
    bwd_pkts_b_avg         numeric,
    bwd_blk_rate_avg       numeric,
    subflow_fwd_pkts       numeric,
    subflow_fwd_byts       numeric,
    subflow_bwd_pkts       numeric,
    subflow_bwd_byts       numeric,
    init_fwd_win_byts      numeric,
    init_bwd_win_byts      numeric,
    fwd_act_data_pkts      numeric,
    fwd_seg_size_min       numeric,
    active_mean            numeric,
    active_std             numeric,
    active_max             numeric,
    active_min             numeric,
    idle_mean              numeric,
    idle_std               numeric,
    idle_max               numeric,
    idle_min               numeric,
    label                  text
) PARTITION BY LIST (capture_day);

CREATE TABLE IF NOT EXISTS clean.flows (
    flow_id                bigint    NOT NULL,   -- gün sırası * 1e9 + line_no (kararlı kimlik)
    capture_day            date      NOT NULL,
    ts                     timestamp NOT NULL,
    end_ts                 timestamp NOT NULL,   -- ts + flow_duration: akışın tahmin edilebildiği an
    label                  text      NOT NULL,
    is_attack              boolean   NOT NULL,
    dst_port               integer   NOT NULL,
    protocol               smallint  NOT NULL,
    flow_duration          real,
    tot_fwd_pkts           real,
    tot_bwd_pkts           real,
    totlen_fwd_pkts        real,
    totlen_bwd_pkts        real,
    fwd_pkt_len_max        real,
    fwd_pkt_len_min        real,
    fwd_pkt_len_mean       real,
    fwd_pkt_len_std        real,
    bwd_pkt_len_max        real,
    bwd_pkt_len_min        real,
    bwd_pkt_len_mean       real,
    bwd_pkt_len_std        real,
    flow_byts_s            real,
    flow_pkts_s            real,
    flow_iat_mean          real,
    flow_iat_std           real,
    flow_iat_max           real,
    flow_iat_min           real,
    fwd_iat_tot            real,
    fwd_iat_mean           real,
    fwd_iat_std            real,
    fwd_iat_max            real,
    fwd_iat_min            real,
    bwd_iat_tot            real,
    bwd_iat_mean           real,
    bwd_iat_std            real,
    bwd_iat_max            real,
    bwd_iat_min            real,
    fwd_psh_flags          real,
    bwd_psh_flags          real,
    fwd_urg_flags          real,
    bwd_urg_flags          real,
    fwd_header_len         real,
    bwd_header_len         real,
    fwd_pkts_s             real,
    bwd_pkts_s             real,
    pkt_len_min            real,
    pkt_len_max            real,
    pkt_len_mean           real,
    pkt_len_std            real,
    pkt_len_var            real,
    fin_flag_cnt           real,
    syn_flag_cnt           real,
    rst_flag_cnt           real,
    psh_flag_cnt           real,
    ack_flag_cnt           real,
    urg_flag_cnt           real,
    cwe_flag_count         real,
    ece_flag_cnt           real,
    down_up_ratio          real,
    pkt_size_avg           real,
    fwd_seg_size_avg       real,
    bwd_seg_size_avg       real,
    fwd_byts_b_avg         real,
    fwd_pkts_b_avg         real,
    fwd_blk_rate_avg       real,
    bwd_byts_b_avg         real,
    bwd_pkts_b_avg         real,
    bwd_blk_rate_avg       real,
    subflow_fwd_pkts       real,
    subflow_fwd_byts       real,
    subflow_bwd_pkts       real,
    subflow_bwd_byts       real,
    init_fwd_win_byts      real,
    init_bwd_win_byts      real,
    fwd_act_data_pkts      real,
    fwd_seg_size_min       real,
    active_mean            real,
    active_std             real,
    active_max             real,
    active_min             real,
    idle_mean              real,
    idle_std               real,
    idle_max               real,
    idle_min               real,
    fv_hash                bigint    NOT NULL    -- akış özellik vektörünün özeti (sızıntı denetimi)
) PARTITION BY LIST (capture_day);

CREATE TABLE IF NOT EXISTS meta.ingest_files (
    source_file      text PRIMARY KEY,
    capture_day      date NOT NULL,
    file_bytes       bigint,
    lines_total      bigint,
    header_repeats   bigint,
    malformed_lines  bigint,
    rows_loaded      bigint,
    seconds          numeric,
    method           text,
    loaded_at        timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta.ingest_rejects (
    source_file text, line_no bigint, reason text, sample text
);

CREATE TABLE IF NOT EXISTS meta.cleaning_log (
    id            serial PRIMARY KEY,
    step          integer NOT NULL,
    rule          text    NOT NULL,
    action        text    NOT NULL,
    rows_affected bigint  NOT NULL,
    details       jsonb   DEFAULT '{}',
    created_at    timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta.audit (
    check_name text, capture_day date, label text, value double precision, details jsonb,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta.timings (
    id serial PRIMARY KEY, stage text, step text, seconds double precision,
    rows_affected bigint, details jsonb, created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta.explain_plans (
    id serial PRIMARY KEY, name text, query text, plan text, created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta.split_definitions (
    scheme text PRIMARY KEY, params jsonb, created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta.split_summary (
    scheme text, split text, label text, rows bigint, created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta.leakage_checks (
    check_name text, scheme text, split text, rows bigint, overlapping_rows bigint,
    details jsonb, created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta.experiments (
    run_id       text PRIMARY KEY,
    name         text NOT NULL,
    created_at   timestamptz DEFAULT now(),
    params       jsonb,
    features     jsonb,
    environment  jsonb,
    data         jsonb,
    results      jsonb
);

-- Performans karşılaştırmaları (python -m ids bench)
CREATE TABLE IF NOT EXISTS meta.benchmarks (
    id serial PRIMARY KEY, name text, variant text, metric text, value double precision,
    details jsonb, created_at timestamptz DEFAULT now()
);
