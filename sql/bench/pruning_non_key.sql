-- Aynı sonuç, bölüm anahtarı olmayan ifadeyle: tüm bölümler taranır. {day}
SELECT label, count(*) FROM clean.flows WHERE ts::date = DATE '{day}' GROUP BY 1
