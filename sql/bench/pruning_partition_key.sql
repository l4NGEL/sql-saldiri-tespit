-- Bölüm anahtarıyla filtre: yalnızca bir gün bölümü taranır (partition pruning). {day}
SELECT label, count(*) FROM clean.flows WHERE capture_day = DATE '{day}' GROUP BY 1
