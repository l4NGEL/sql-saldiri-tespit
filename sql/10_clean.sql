-- 10_clean.sql — raw.flows -> clean.flows (gün bazında, idempotent).
--
-- Kurallar (sıra önemlidir; her birinin etkilediği satır sayısı meta.cleaning_log'a yazılır):
--   1  DROP  zaman damgası boş veya yakalama günü dışında (ör. 1970-01-05)          -> düşürülür
--   2  FIX   12 saatlik saat: AM/PM bilgisi yok; yakalama 08:00-17:59 arası,
--            saat < 8 ise +12 saat (14-02 SSH saldırısı 02:01 -> 14:01, resmi takvimle uyumlu)
--   3  DROP  zorunlu alan eksik (dst_port, protocol, flow_duration, label)       -> düşürülür
--   4  DROP  negatif flow_duration (CICFlowMeter saat hatası)                     -> düşürülür
--   5  FIX   Infinity/NaN/negatif ölçüm -> NULL (flow_byts_s, flow_pkts_s, IAT'ler...);
--            init_*_win_byts = -1 "gözlenmedi" anlamına gelen işaret değeridir, korunur
--   6  DROP  birebir tekrar eden kayıt (tüm sütunlar aynı, line_no hariç) -> ilki tutulur
--   7  DROP  etiket çelişkisi: aynı zaman damgası + aynı özellikler, farklı etiket -> grup düşer
--
-- Model dışı bırakılan ama saklanan alanlar (src_ip vb.) clean'e taşınmaz.

CREATE OR REPLACE FUNCTION clean.fix_ts(ts timestamp, day date) RETURNS timestamp
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN ts IS NULL OR ts::date <> day THEN NULL
                WHEN extract(hour FROM ts) < 8 THEN ts + interval '12 hours'
                ELSE ts END
$$;

-- Aday satırlar: düşürme kuralları 1,3,4 uygulanmış, düzeltmeler 2,5 yapılmış hâli.
-- Özetler (hash) değer eşitliğine göre alınsın diye sayılar float8'e çevrilerek hesaplanır
-- (numeric metin gösterimi "0" ile "0.0"ı farklı yazar).
CREATE OR REPLACE VIEW clean.v_candidates AS
SELECT r.capture_day,
       r.line_no,
       clean.fix_ts(r.ts, r.capture_day)                                   AS ts,
       r.label,
       r.dst_port,
       r.protocol,
       CASE WHEN r.flow_duration < 0 OR r.flow_duration = 'NaN'::numeric OR r.flow_duration IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.flow_duration END::real AS flow_duration,
            CASE WHEN r.tot_fwd_pkts < 0 OR r.tot_fwd_pkts = 'NaN'::numeric OR r.tot_fwd_pkts IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.tot_fwd_pkts END::real AS tot_fwd_pkts,
            CASE WHEN r.tot_bwd_pkts < 0 OR r.tot_bwd_pkts = 'NaN'::numeric OR r.tot_bwd_pkts IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.tot_bwd_pkts END::real AS tot_bwd_pkts,
            CASE WHEN r.totlen_fwd_pkts < 0 OR r.totlen_fwd_pkts = 'NaN'::numeric OR r.totlen_fwd_pkts IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.totlen_fwd_pkts END::real AS totlen_fwd_pkts,
            CASE WHEN r.totlen_bwd_pkts < 0 OR r.totlen_bwd_pkts = 'NaN'::numeric OR r.totlen_bwd_pkts IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.totlen_bwd_pkts END::real AS totlen_bwd_pkts,
            CASE WHEN r.fwd_pkt_len_max < 0 OR r.fwd_pkt_len_max = 'NaN'::numeric OR r.fwd_pkt_len_max IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_pkt_len_max END::real AS fwd_pkt_len_max,
            CASE WHEN r.fwd_pkt_len_min < 0 OR r.fwd_pkt_len_min = 'NaN'::numeric OR r.fwd_pkt_len_min IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_pkt_len_min END::real AS fwd_pkt_len_min,
            CASE WHEN r.fwd_pkt_len_mean < 0 OR r.fwd_pkt_len_mean = 'NaN'::numeric OR r.fwd_pkt_len_mean IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_pkt_len_mean END::real AS fwd_pkt_len_mean,
            CASE WHEN r.fwd_pkt_len_std < 0 OR r.fwd_pkt_len_std = 'NaN'::numeric OR r.fwd_pkt_len_std IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_pkt_len_std END::real AS fwd_pkt_len_std,
            CASE WHEN r.bwd_pkt_len_max < 0 OR r.bwd_pkt_len_max = 'NaN'::numeric OR r.bwd_pkt_len_max IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_pkt_len_max END::real AS bwd_pkt_len_max,
            CASE WHEN r.bwd_pkt_len_min < 0 OR r.bwd_pkt_len_min = 'NaN'::numeric OR r.bwd_pkt_len_min IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_pkt_len_min END::real AS bwd_pkt_len_min,
            CASE WHEN r.bwd_pkt_len_mean < 0 OR r.bwd_pkt_len_mean = 'NaN'::numeric OR r.bwd_pkt_len_mean IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_pkt_len_mean END::real AS bwd_pkt_len_mean,
            CASE WHEN r.bwd_pkt_len_std < 0 OR r.bwd_pkt_len_std = 'NaN'::numeric OR r.bwd_pkt_len_std IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_pkt_len_std END::real AS bwd_pkt_len_std,
            CASE WHEN r.flow_byts_s < 0 OR r.flow_byts_s = 'NaN'::numeric OR r.flow_byts_s IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.flow_byts_s END::real AS flow_byts_s,
            CASE WHEN r.flow_pkts_s < 0 OR r.flow_pkts_s = 'NaN'::numeric OR r.flow_pkts_s IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.flow_pkts_s END::real AS flow_pkts_s,
            CASE WHEN r.flow_iat_mean < 0 OR r.flow_iat_mean = 'NaN'::numeric OR r.flow_iat_mean IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.flow_iat_mean END::real AS flow_iat_mean,
            CASE WHEN r.flow_iat_std < 0 OR r.flow_iat_std = 'NaN'::numeric OR r.flow_iat_std IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.flow_iat_std END::real AS flow_iat_std,
            CASE WHEN r.flow_iat_max < 0 OR r.flow_iat_max = 'NaN'::numeric OR r.flow_iat_max IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.flow_iat_max END::real AS flow_iat_max,
            CASE WHEN r.flow_iat_min < 0 OR r.flow_iat_min = 'NaN'::numeric OR r.flow_iat_min IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.flow_iat_min END::real AS flow_iat_min,
            CASE WHEN r.fwd_iat_tot < 0 OR r.fwd_iat_tot = 'NaN'::numeric OR r.fwd_iat_tot IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_iat_tot END::real AS fwd_iat_tot,
            CASE WHEN r.fwd_iat_mean < 0 OR r.fwd_iat_mean = 'NaN'::numeric OR r.fwd_iat_mean IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_iat_mean END::real AS fwd_iat_mean,
            CASE WHEN r.fwd_iat_std < 0 OR r.fwd_iat_std = 'NaN'::numeric OR r.fwd_iat_std IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_iat_std END::real AS fwd_iat_std,
            CASE WHEN r.fwd_iat_max < 0 OR r.fwd_iat_max = 'NaN'::numeric OR r.fwd_iat_max IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_iat_max END::real AS fwd_iat_max,
            CASE WHEN r.fwd_iat_min < 0 OR r.fwd_iat_min = 'NaN'::numeric OR r.fwd_iat_min IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_iat_min END::real AS fwd_iat_min,
            CASE WHEN r.bwd_iat_tot < 0 OR r.bwd_iat_tot = 'NaN'::numeric OR r.bwd_iat_tot IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_iat_tot END::real AS bwd_iat_tot,
            CASE WHEN r.bwd_iat_mean < 0 OR r.bwd_iat_mean = 'NaN'::numeric OR r.bwd_iat_mean IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_iat_mean END::real AS bwd_iat_mean,
            CASE WHEN r.bwd_iat_std < 0 OR r.bwd_iat_std = 'NaN'::numeric OR r.bwd_iat_std IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_iat_std END::real AS bwd_iat_std,
            CASE WHEN r.bwd_iat_max < 0 OR r.bwd_iat_max = 'NaN'::numeric OR r.bwd_iat_max IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_iat_max END::real AS bwd_iat_max,
            CASE WHEN r.bwd_iat_min < 0 OR r.bwd_iat_min = 'NaN'::numeric OR r.bwd_iat_min IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_iat_min END::real AS bwd_iat_min,
            CASE WHEN r.fwd_psh_flags < 0 OR r.fwd_psh_flags = 'NaN'::numeric OR r.fwd_psh_flags IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_psh_flags END::real AS fwd_psh_flags,
            CASE WHEN r.bwd_psh_flags < 0 OR r.bwd_psh_flags = 'NaN'::numeric OR r.bwd_psh_flags IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_psh_flags END::real AS bwd_psh_flags,
            CASE WHEN r.fwd_urg_flags < 0 OR r.fwd_urg_flags = 'NaN'::numeric OR r.fwd_urg_flags IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_urg_flags END::real AS fwd_urg_flags,
            CASE WHEN r.bwd_urg_flags < 0 OR r.bwd_urg_flags = 'NaN'::numeric OR r.bwd_urg_flags IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_urg_flags END::real AS bwd_urg_flags,
            CASE WHEN r.fwd_header_len < 0 OR r.fwd_header_len = 'NaN'::numeric OR r.fwd_header_len IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_header_len END::real AS fwd_header_len,
            CASE WHEN r.bwd_header_len < 0 OR r.bwd_header_len = 'NaN'::numeric OR r.bwd_header_len IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_header_len END::real AS bwd_header_len,
            CASE WHEN r.fwd_pkts_s < 0 OR r.fwd_pkts_s = 'NaN'::numeric OR r.fwd_pkts_s IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_pkts_s END::real AS fwd_pkts_s,
            CASE WHEN r.bwd_pkts_s < 0 OR r.bwd_pkts_s = 'NaN'::numeric OR r.bwd_pkts_s IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_pkts_s END::real AS bwd_pkts_s,
            CASE WHEN r.pkt_len_min < 0 OR r.pkt_len_min = 'NaN'::numeric OR r.pkt_len_min IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.pkt_len_min END::real AS pkt_len_min,
            CASE WHEN r.pkt_len_max < 0 OR r.pkt_len_max = 'NaN'::numeric OR r.pkt_len_max IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.pkt_len_max END::real AS pkt_len_max,
            CASE WHEN r.pkt_len_mean < 0 OR r.pkt_len_mean = 'NaN'::numeric OR r.pkt_len_mean IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.pkt_len_mean END::real AS pkt_len_mean,
            CASE WHEN r.pkt_len_std < 0 OR r.pkt_len_std = 'NaN'::numeric OR r.pkt_len_std IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.pkt_len_std END::real AS pkt_len_std,
            CASE WHEN r.pkt_len_var < 0 OR r.pkt_len_var = 'NaN'::numeric OR r.pkt_len_var IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.pkt_len_var END::real AS pkt_len_var,
            CASE WHEN r.fin_flag_cnt < 0 OR r.fin_flag_cnt = 'NaN'::numeric OR r.fin_flag_cnt IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fin_flag_cnt END::real AS fin_flag_cnt,
            CASE WHEN r.syn_flag_cnt < 0 OR r.syn_flag_cnt = 'NaN'::numeric OR r.syn_flag_cnt IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.syn_flag_cnt END::real AS syn_flag_cnt,
            CASE WHEN r.rst_flag_cnt < 0 OR r.rst_flag_cnt = 'NaN'::numeric OR r.rst_flag_cnt IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.rst_flag_cnt END::real AS rst_flag_cnt,
            CASE WHEN r.psh_flag_cnt < 0 OR r.psh_flag_cnt = 'NaN'::numeric OR r.psh_flag_cnt IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.psh_flag_cnt END::real AS psh_flag_cnt,
            CASE WHEN r.ack_flag_cnt < 0 OR r.ack_flag_cnt = 'NaN'::numeric OR r.ack_flag_cnt IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.ack_flag_cnt END::real AS ack_flag_cnt,
            CASE WHEN r.urg_flag_cnt < 0 OR r.urg_flag_cnt = 'NaN'::numeric OR r.urg_flag_cnt IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.urg_flag_cnt END::real AS urg_flag_cnt,
            CASE WHEN r.cwe_flag_count < 0 OR r.cwe_flag_count = 'NaN'::numeric OR r.cwe_flag_count IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.cwe_flag_count END::real AS cwe_flag_count,
            CASE WHEN r.ece_flag_cnt < 0 OR r.ece_flag_cnt = 'NaN'::numeric OR r.ece_flag_cnt IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.ece_flag_cnt END::real AS ece_flag_cnt,
            CASE WHEN r.down_up_ratio < 0 OR r.down_up_ratio = 'NaN'::numeric OR r.down_up_ratio IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.down_up_ratio END::real AS down_up_ratio,
            CASE WHEN r.pkt_size_avg < 0 OR r.pkt_size_avg = 'NaN'::numeric OR r.pkt_size_avg IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.pkt_size_avg END::real AS pkt_size_avg,
            CASE WHEN r.fwd_seg_size_avg < 0 OR r.fwd_seg_size_avg = 'NaN'::numeric OR r.fwd_seg_size_avg IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_seg_size_avg END::real AS fwd_seg_size_avg,
            CASE WHEN r.bwd_seg_size_avg < 0 OR r.bwd_seg_size_avg = 'NaN'::numeric OR r.bwd_seg_size_avg IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_seg_size_avg END::real AS bwd_seg_size_avg,
            CASE WHEN r.fwd_byts_b_avg < 0 OR r.fwd_byts_b_avg = 'NaN'::numeric OR r.fwd_byts_b_avg IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_byts_b_avg END::real AS fwd_byts_b_avg,
            CASE WHEN r.fwd_pkts_b_avg < 0 OR r.fwd_pkts_b_avg = 'NaN'::numeric OR r.fwd_pkts_b_avg IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_pkts_b_avg END::real AS fwd_pkts_b_avg,
            CASE WHEN r.fwd_blk_rate_avg < 0 OR r.fwd_blk_rate_avg = 'NaN'::numeric OR r.fwd_blk_rate_avg IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_blk_rate_avg END::real AS fwd_blk_rate_avg,
            CASE WHEN r.bwd_byts_b_avg < 0 OR r.bwd_byts_b_avg = 'NaN'::numeric OR r.bwd_byts_b_avg IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_byts_b_avg END::real AS bwd_byts_b_avg,
            CASE WHEN r.bwd_pkts_b_avg < 0 OR r.bwd_pkts_b_avg = 'NaN'::numeric OR r.bwd_pkts_b_avg IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_pkts_b_avg END::real AS bwd_pkts_b_avg,
            CASE WHEN r.bwd_blk_rate_avg < 0 OR r.bwd_blk_rate_avg = 'NaN'::numeric OR r.bwd_blk_rate_avg IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.bwd_blk_rate_avg END::real AS bwd_blk_rate_avg,
            CASE WHEN r.subflow_fwd_pkts < 0 OR r.subflow_fwd_pkts = 'NaN'::numeric OR r.subflow_fwd_pkts IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.subflow_fwd_pkts END::real AS subflow_fwd_pkts,
            CASE WHEN r.subflow_fwd_byts < 0 OR r.subflow_fwd_byts = 'NaN'::numeric OR r.subflow_fwd_byts IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.subflow_fwd_byts END::real AS subflow_fwd_byts,
            CASE WHEN r.subflow_bwd_pkts < 0 OR r.subflow_bwd_pkts = 'NaN'::numeric OR r.subflow_bwd_pkts IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.subflow_bwd_pkts END::real AS subflow_bwd_pkts,
            CASE WHEN r.subflow_bwd_byts < 0 OR r.subflow_bwd_byts = 'NaN'::numeric OR r.subflow_bwd_byts IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.subflow_bwd_byts END::real AS subflow_bwd_byts,
            r.init_fwd_win_byts::real AS init_fwd_win_byts,
            r.init_bwd_win_byts::real AS init_bwd_win_byts,
            CASE WHEN r.fwd_act_data_pkts < 0 OR r.fwd_act_data_pkts = 'NaN'::numeric OR r.fwd_act_data_pkts IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_act_data_pkts END::real AS fwd_act_data_pkts,
            CASE WHEN r.fwd_seg_size_min < 0 OR r.fwd_seg_size_min = 'NaN'::numeric OR r.fwd_seg_size_min IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.fwd_seg_size_min END::real AS fwd_seg_size_min,
            CASE WHEN r.active_mean < 0 OR r.active_mean = 'NaN'::numeric OR r.active_mean IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.active_mean END::real AS active_mean,
            CASE WHEN r.active_std < 0 OR r.active_std = 'NaN'::numeric OR r.active_std IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.active_std END::real AS active_std,
            CASE WHEN r.active_max < 0 OR r.active_max = 'NaN'::numeric OR r.active_max IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.active_max END::real AS active_max,
            CASE WHEN r.active_min < 0 OR r.active_min = 'NaN'::numeric OR r.active_min IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.active_min END::real AS active_min,
            CASE WHEN r.idle_mean < 0 OR r.idle_mean = 'NaN'::numeric OR r.idle_mean IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.idle_mean END::real AS idle_mean,
            CASE WHEN r.idle_std < 0 OR r.idle_std = 'NaN'::numeric OR r.idle_std IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.idle_std END::real AS idle_std,
            CASE WHEN r.idle_max < 0 OR r.idle_max = 'NaN'::numeric OR r.idle_max IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.idle_max END::real AS idle_max,
            CASE WHEN r.idle_min < 0 OR r.idle_min = 'NaN'::numeric OR r.idle_min IN ('Infinity'::numeric, '-Infinity'::numeric) THEN NULL ELSE r.idle_min END::real AS idle_min,
       md5(ROW(r.ts, r.flow_key, r.src_ip, r.src_port, r.dst_ip, r.dst_port, r.protocol, r.flow_duration::float8, r.tot_fwd_pkts::float8, r.tot_bwd_pkts::float8, r.totlen_fwd_pkts::float8, r.totlen_bwd_pkts::float8, r.fwd_pkt_len_max::float8, r.fwd_pkt_len_min::float8, r.fwd_pkt_len_mean::float8, r.fwd_pkt_len_std::float8, r.bwd_pkt_len_max::float8, r.bwd_pkt_len_min::float8, r.bwd_pkt_len_mean::float8, r.bwd_pkt_len_std::float8, r.flow_byts_s::float8, r.flow_pkts_s::float8, r.flow_iat_mean::float8, r.flow_iat_std::float8, r.flow_iat_max::float8, r.flow_iat_min::float8, r.fwd_iat_tot::float8, r.fwd_iat_mean::float8, r.fwd_iat_std::float8, r.fwd_iat_max::float8, r.fwd_iat_min::float8, r.bwd_iat_tot::float8, r.bwd_iat_mean::float8, r.bwd_iat_std::float8, r.bwd_iat_max::float8, r.bwd_iat_min::float8, r.fwd_psh_flags::float8, r.bwd_psh_flags::float8, r.fwd_urg_flags::float8, r.bwd_urg_flags::float8, r.fwd_header_len::float8, r.bwd_header_len::float8, r.fwd_pkts_s::float8, r.bwd_pkts_s::float8, r.pkt_len_min::float8, r.pkt_len_max::float8, r.pkt_len_mean::float8, r.pkt_len_std::float8, r.pkt_len_var::float8, r.fin_flag_cnt::float8, r.syn_flag_cnt::float8, r.rst_flag_cnt::float8, r.psh_flag_cnt::float8, r.ack_flag_cnt::float8, r.urg_flag_cnt::float8, r.cwe_flag_count::float8, r.ece_flag_cnt::float8, r.down_up_ratio::float8, r.pkt_size_avg::float8, r.fwd_seg_size_avg::float8, r.bwd_seg_size_avg::float8, r.fwd_byts_b_avg::float8, r.fwd_pkts_b_avg::float8, r.fwd_blk_rate_avg::float8, r.bwd_byts_b_avg::float8, r.bwd_pkts_b_avg::float8, r.bwd_blk_rate_avg::float8, r.subflow_fwd_pkts::float8, r.subflow_fwd_byts::float8, r.subflow_bwd_pkts::float8, r.subflow_bwd_byts::float8, r.init_fwd_win_byts::float8, r.init_bwd_win_byts::float8, r.fwd_act_data_pkts::float8, r.fwd_seg_size_min::float8, r.active_mean::float8, r.active_std::float8, r.active_max::float8, r.active_min::float8, r.idle_mean::float8, r.idle_std::float8, r.idle_max::float8, r.idle_min::float8, r.label)::text) AS row_hash,
       md5(ROW(r.ts, r.flow_key, r.src_ip, r.src_port, r.dst_ip, r.dst_port, r.protocol, r.flow_duration::float8, r.tot_fwd_pkts::float8, r.tot_bwd_pkts::float8, r.totlen_fwd_pkts::float8, r.totlen_bwd_pkts::float8, r.fwd_pkt_len_max::float8, r.fwd_pkt_len_min::float8, r.fwd_pkt_len_mean::float8, r.fwd_pkt_len_std::float8, r.bwd_pkt_len_max::float8, r.bwd_pkt_len_min::float8, r.bwd_pkt_len_mean::float8, r.bwd_pkt_len_std::float8, r.flow_byts_s::float8, r.flow_pkts_s::float8, r.flow_iat_mean::float8, r.flow_iat_std::float8, r.flow_iat_max::float8, r.flow_iat_min::float8, r.fwd_iat_tot::float8, r.fwd_iat_mean::float8, r.fwd_iat_std::float8, r.fwd_iat_max::float8, r.fwd_iat_min::float8, r.bwd_iat_tot::float8, r.bwd_iat_mean::float8, r.bwd_iat_std::float8, r.bwd_iat_max::float8, r.bwd_iat_min::float8, r.fwd_psh_flags::float8, r.bwd_psh_flags::float8, r.fwd_urg_flags::float8, r.bwd_urg_flags::float8, r.fwd_header_len::float8, r.bwd_header_len::float8, r.fwd_pkts_s::float8, r.bwd_pkts_s::float8, r.pkt_len_min::float8, r.pkt_len_max::float8, r.pkt_len_mean::float8, r.pkt_len_std::float8, r.pkt_len_var::float8, r.fin_flag_cnt::float8, r.syn_flag_cnt::float8, r.rst_flag_cnt::float8, r.psh_flag_cnt::float8, r.ack_flag_cnt::float8, r.urg_flag_cnt::float8, r.cwe_flag_count::float8, r.ece_flag_cnt::float8, r.down_up_ratio::float8, r.pkt_size_avg::float8, r.fwd_seg_size_avg::float8, r.bwd_seg_size_avg::float8, r.fwd_byts_b_avg::float8, r.fwd_pkts_b_avg::float8, r.fwd_blk_rate_avg::float8, r.bwd_byts_b_avg::float8, r.bwd_pkts_b_avg::float8, r.bwd_blk_rate_avg::float8, r.subflow_fwd_pkts::float8, r.subflow_fwd_byts::float8, r.subflow_bwd_pkts::float8, r.subflow_bwd_byts::float8, r.init_fwd_win_byts::float8, r.init_bwd_win_byts::float8, r.fwd_act_data_pkts::float8, r.fwd_seg_size_min::float8, r.active_mean::float8, r.active_std::float8, r.active_max::float8, r.active_min::float8, r.idle_mean::float8, r.idle_std::float8, r.idle_max::float8, r.idle_min::float8)::text)          AS row_hash_nolabel,
       ('x' || substr(md5(ROW(r.dst_port, r.protocol, r.flow_duration::float8, r.tot_fwd_pkts::float8, r.tot_bwd_pkts::float8, r.totlen_fwd_pkts::float8, r.totlen_bwd_pkts::float8, r.fwd_pkt_len_max::float8, r.fwd_pkt_len_min::float8, r.fwd_pkt_len_mean::float8, r.fwd_pkt_len_std::float8, r.bwd_pkt_len_max::float8, r.bwd_pkt_len_min::float8, r.bwd_pkt_len_mean::float8, r.bwd_pkt_len_std::float8, r.flow_byts_s::float8, r.flow_pkts_s::float8, r.flow_iat_mean::float8, r.flow_iat_std::float8, r.flow_iat_max::float8, r.flow_iat_min::float8, r.fwd_iat_tot::float8, r.fwd_iat_mean::float8, r.fwd_iat_std::float8, r.fwd_iat_max::float8, r.fwd_iat_min::float8, r.bwd_iat_tot::float8, r.bwd_iat_mean::float8, r.bwd_iat_std::float8, r.bwd_iat_max::float8, r.bwd_iat_min::float8, r.fwd_psh_flags::float8, r.bwd_psh_flags::float8, r.fwd_urg_flags::float8, r.bwd_urg_flags::float8, r.fwd_header_len::float8, r.bwd_header_len::float8, r.fwd_pkts_s::float8, r.bwd_pkts_s::float8, r.pkt_len_min::float8, r.pkt_len_max::float8, r.pkt_len_mean::float8, r.pkt_len_std::float8, r.pkt_len_var::float8, r.fin_flag_cnt::float8, r.syn_flag_cnt::float8, r.rst_flag_cnt::float8, r.psh_flag_cnt::float8, r.ack_flag_cnt::float8, r.urg_flag_cnt::float8, r.cwe_flag_count::float8, r.ece_flag_cnt::float8, r.down_up_ratio::float8, r.pkt_size_avg::float8, r.fwd_seg_size_avg::float8, r.bwd_seg_size_avg::float8, r.fwd_byts_b_avg::float8, r.fwd_pkts_b_avg::float8, r.fwd_blk_rate_avg::float8, r.bwd_byts_b_avg::float8, r.bwd_pkts_b_avg::float8, r.bwd_blk_rate_avg::float8, r.subflow_fwd_pkts::float8, r.subflow_fwd_byts::float8, r.subflow_bwd_pkts::float8, r.subflow_bwd_byts::float8, r.init_fwd_win_byts::float8, r.init_bwd_win_byts::float8, r.fwd_act_data_pkts::float8, r.fwd_seg_size_min::float8, r.active_mean::float8, r.active_std::float8, r.active_max::float8, r.active_min::float8, r.idle_mean::float8, r.idle_std::float8, r.idle_max::float8, r.idle_min::float8)::text), 1, 16))::bit(64)::bigint   AS fv_hash
FROM raw.flows r
WHERE clean.fix_ts(r.ts, r.capture_day) IS NOT NULL
  AND r.dst_port IS NOT NULL AND r.protocol IS NOT NULL
  AND r.flow_duration IS NOT NULL AND r.label IS NOT NULL
  AND r.flow_duration >= 0;

CREATE OR REPLACE PROCEDURE clean.build_day(p_day date, p_day_idx int)
LANGUAGE plpgsql AS $$
DECLARE
    part text := 'flows_' || to_char(p_day, 'YYYYMMDD');
    n_raw bigint; n_bad_ts bigint; n_ts_fixed bigint; n_missing bigint; n_negdur bigint;
    n_cand bigint; n_dupe bigint; n_conflict bigint; n_final bigint;
BEGIN
    -- Kural sayımları (şelale sırasıyla, ham bölüm üzerinde)
    SELECT count(*),
           count(*) FILTER (WHERE clean.fix_ts(ts, capture_day) IS NULL),
           count(*) FILTER (WHERE clean.fix_ts(ts, capture_day) IS NOT NULL AND extract(hour FROM ts) < 8),
           count(*) FILTER (WHERE clean.fix_ts(ts, capture_day) IS NOT NULL
                              AND (dst_port IS NULL OR protocol IS NULL OR flow_duration IS NULL OR label IS NULL)),
           count(*) FILTER (WHERE clean.fix_ts(ts, capture_day) IS NOT NULL
                              AND dst_port IS NOT NULL AND protocol IS NOT NULL AND label IS NOT NULL
                              AND flow_duration < 0)
      INTO n_raw, n_bad_ts, n_ts_fixed, n_missing, n_negdur
      FROM raw.flows WHERE capture_day = p_day;

    -- Tekrar ve çelişki tespiti yalnızca küçük bir anahtar tablosunda yapılır
    -- (tüm satırları sıralamak yerine) -> geçici disk kullanımı düşük kalır.
    DROP TABLE IF EXISTS pg_temp.cand;
    CREATE TEMP TABLE cand AS
        SELECT line_no, row_hash, row_hash_nolabel, label
        FROM clean.v_candidates WHERE capture_day = p_day;
    SELECT count(*) INTO n_cand FROM cand;

    DROP TABLE IF EXISTS pg_temp.conflict;
    CREATE TEMP TABLE conflict AS
        SELECT row_hash_nolabel FROM cand GROUP BY 1 HAVING count(DISTINCT label) > 1;

    DROP TABLE IF EXISTS pg_temp.keep;
    CREATE TEMP TABLE keep AS
        SELECT min(line_no) AS line_no, min(row_hash_nolabel) AS row_hash_nolabel
        FROM cand GROUP BY row_hash;
    n_dupe := n_cand - (SELECT count(*) FROM keep);
    DELETE FROM keep k USING conflict c WHERE k.row_hash_nolabel = c.row_hash_nolabel;
    GET DIAGNOSTICS n_conflict = ROW_COUNT;
    CREATE UNIQUE INDEX ON keep(line_no);
    ANALYZE keep;

    EXECUTE format('DROP TABLE IF EXISTS clean.%I', part);
    EXECUTE format('CREATE TABLE clean.%I (LIKE clean.flows)', part);
    EXECUTE format('ALTER TABLE clean.%I ADD CONSTRAINT %I CHECK (capture_day = %L)', part, part || '_day', p_day);
    EXECUTE format($q$
        INSERT INTO clean.%I
        SELECT %s::bigint * 1000000000 + v.line_no, v.capture_day, v.ts,
               v.ts + v.flow_duration * interval '1 microsecond',
               v.label, v.label <> 'Benign', v.dst_port, v.protocol,
               v.flow_duration, v.tot_fwd_pkts, v.tot_bwd_pkts, v.totlen_fwd_pkts, v.totlen_bwd_pkts, v.fwd_pkt_len_max, v.fwd_pkt_len_min, v.fwd_pkt_len_mean, v.fwd_pkt_len_std, v.bwd_pkt_len_max, v.bwd_pkt_len_min, v.bwd_pkt_len_mean, v.bwd_pkt_len_std, v.flow_byts_s, v.flow_pkts_s, v.flow_iat_mean, v.flow_iat_std, v.flow_iat_max, v.flow_iat_min, v.fwd_iat_tot, v.fwd_iat_mean, v.fwd_iat_std, v.fwd_iat_max, v.fwd_iat_min, v.bwd_iat_tot, v.bwd_iat_mean, v.bwd_iat_std, v.bwd_iat_max, v.bwd_iat_min, v.fwd_psh_flags, v.bwd_psh_flags, v.fwd_urg_flags, v.bwd_urg_flags, v.fwd_header_len, v.bwd_header_len, v.fwd_pkts_s, v.bwd_pkts_s, v.pkt_len_min, v.pkt_len_max, v.pkt_len_mean, v.pkt_len_std, v.pkt_len_var, v.fin_flag_cnt, v.syn_flag_cnt, v.rst_flag_cnt, v.psh_flag_cnt, v.ack_flag_cnt, v.urg_flag_cnt, v.cwe_flag_count, v.ece_flag_cnt, v.down_up_ratio, v.pkt_size_avg, v.fwd_seg_size_avg, v.bwd_seg_size_avg, v.fwd_byts_b_avg, v.fwd_pkts_b_avg, v.fwd_blk_rate_avg, v.bwd_byts_b_avg, v.bwd_pkts_b_avg, v.bwd_blk_rate_avg, v.subflow_fwd_pkts, v.subflow_fwd_byts, v.subflow_bwd_pkts, v.subflow_bwd_byts, v.init_fwd_win_byts, v.init_bwd_win_byts, v.fwd_act_data_pkts, v.fwd_seg_size_min, v.active_mean, v.active_std, v.active_max, v.active_min, v.idle_mean, v.idle_std, v.idle_max, v.idle_min,
               v.fv_hash
        FROM clean.v_candidates v JOIN keep k USING (line_no)
        WHERE v.capture_day = %L$q$, part, p_day_idx, p_day);
    GET DIAGNOSTICS n_final = ROW_COUNT;
    EXECUTE format('ALTER TABLE clean.flows ATTACH PARTITION clean.%I FOR VALUES IN (%L)', part, p_day);

    DELETE FROM meta.cleaning_log WHERE details->>'day' = p_day::text AND step <> 5;
    INSERT INTO meta.cleaning_log(step, rule, action, rows_affected, details) VALUES
      (0, 'ham satır (raw.flows)',                              'input', n_raw,      jsonb_build_object('day', p_day)),
      (1, 'zaman damgası boş / yakalama günü dışında',           'drop',  n_bad_ts,   jsonb_build_object('day', p_day)),
      (2, '12 saatlik saat düzeltmesi (saat<8 -> +12 saat)',     'fix',   n_ts_fixed, jsonb_build_object('day', p_day)),
      (3, 'zorunlu alan eksik',                                  'drop',  n_missing,  jsonb_build_object('day', p_day)),
      (4, 'negatif flow_duration',                               'drop',  n_negdur,   jsonb_build_object('day', p_day)),
      (6, 'birebir tekrar eden kayıt',                           'drop',  n_dupe,     jsonb_build_object('day', p_day)),
      (7, 'etiket çelişkisi (aynı akış, farklı etiket)',         'drop',  n_conflict, jsonb_build_object('day', p_day)),
      (9, 'temiz satır (clean.flows)',                           'output', n_final,   jsonb_build_object('day', p_day));
END $$;
