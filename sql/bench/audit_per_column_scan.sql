-- İlk denetim sürümü (karşılaştırma için saklanır): her sütun için AYRI tam tarama.
-- {part} = raw bölüm adı. Sonuçlar geçici tabloya yazılır.
CREATE TEMP TABLE IF NOT EXISTS bench_audit(col text, issue text, cnt bigint);
TRUNCATE bench_audit;
DO $$
DECLARE c text;
BEGIN
    FOREACH c IN ARRAY ARRAY['flow_duration', 'tot_fwd_pkts', 'tot_bwd_pkts', 'totlen_fwd_pkts', 'totlen_bwd_pkts', 'fwd_pkt_len_max', 'fwd_pkt_len_min', 'fwd_pkt_len_mean', 'fwd_pkt_len_std', 'bwd_pkt_len_max', 'bwd_pkt_len_min', 'bwd_pkt_len_mean', 'bwd_pkt_len_std', 'flow_byts_s', 'flow_pkts_s', 'flow_iat_mean', 'flow_iat_std', 'flow_iat_max', 'flow_iat_min', 'fwd_iat_tot', 'fwd_iat_mean', 'fwd_iat_std', 'fwd_iat_max', 'fwd_iat_min', 'bwd_iat_tot', 'bwd_iat_mean', 'bwd_iat_std', 'bwd_iat_max', 'bwd_iat_min', 'fwd_psh_flags', 'bwd_psh_flags', 'fwd_urg_flags', 'bwd_urg_flags', 'fwd_header_len', 'bwd_header_len', 'fwd_pkts_s', 'bwd_pkts_s', 'pkt_len_min', 'pkt_len_max', 'pkt_len_mean', 'pkt_len_std', 'pkt_len_var', 'fin_flag_cnt', 'syn_flag_cnt', 'rst_flag_cnt', 'psh_flag_cnt', 'ack_flag_cnt', 'urg_flag_cnt', 'cwe_flag_count', 'ece_flag_cnt', 'down_up_ratio', 'pkt_size_avg', 'fwd_seg_size_avg', 'bwd_seg_size_avg', 'fwd_byts_b_avg', 'fwd_pkts_b_avg', 'fwd_blk_rate_avg', 'bwd_byts_b_avg', 'bwd_pkts_b_avg', 'bwd_blk_rate_avg', 'subflow_fwd_pkts', 'subflow_fwd_byts', 'subflow_bwd_pkts', 'subflow_bwd_byts', 'init_fwd_win_byts', 'init_bwd_win_byts', 'fwd_act_data_pkts', 'fwd_seg_size_min', 'active_mean', 'active_std', 'active_max', 'active_min', 'idle_mean', 'idle_std', 'idle_max', 'idle_min'] LOOP
        EXECUTE format($f$
            INSERT INTO bench_audit
            SELECT %1$L, v.issue, v.cnt FROM (
                SELECT count(*) FILTER (WHERE %1$I < 0) AS negative,
                       count(*) FILTER (WHERE %1$I IN ('Infinity'::numeric, '-Infinity'::numeric)) AS infinite,
                       count(*) FILTER (WHERE %1$I = 'NaN'::numeric) AS nan,
                       count(*) FILTER (WHERE %1$I IS NULL) AS missing
                FROM raw.{part}
                WHERE clean.fix_ts(ts, capture_day) IS NOT NULL AND flow_duration >= 0) s
            CROSS JOIN LATERAL (VALUES ('negative', negative), ('infinite', infinite),
                                       ('nan', nan), ('missing', missing)) v(issue, cnt)$f$, c);
    END LOOP;
END $$;
