-- Kayan pencerede float toplamı (ters geçiş fonksiyonu YOK -> her satırda çerçeve yeniden toplanır)
-- {part} = clean bölüm adı
SELECT sum(x) FROM (
    SELECT sum(c.tot_fwd_pkts) OVER w AS x
    FROM clean.{part} c
    WINDOW w AS (PARTITION BY c.dst_port ORDER BY c.end_ts RANGE BETWEEN interval '60 seconds' PRECEDING AND CURRENT ROW)
) s
