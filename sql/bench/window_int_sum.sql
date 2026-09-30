-- Kayan pencerede tamsayı toplamı (ters geçiş fonksiyonu VAR -> satır başına O(1))
-- {part} = clean bölüm adı
SELECT sum(x) FROM (
    SELECT sum(c.tot_fwd_pkts::bigint) OVER w AS x
    FROM clean.{part} c
    WINDOW w AS (PARTITION BY c.dst_port ORDER BY c.end_ts RANGE BETWEEN interval '60 seconds' PRECEDING AND CURRENT ROW)
) s
