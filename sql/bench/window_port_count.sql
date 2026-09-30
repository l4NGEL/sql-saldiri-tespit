-- Pencere özelliği sorgusunun çekirdeği (indeks karşılaştırması için). {part} = clean bölüm adı
SELECT sum(n) FROM (
    SELECT count(*) OVER w AS n
    FROM clean.{part} c
    WINDOW w AS (PARTITION BY c.dst_port ORDER BY c.end_ts RANGE BETWEEN interval '60 seconds' PRECEDING AND CURRENT ROW)
) s
