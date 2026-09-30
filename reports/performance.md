# Performans: süreler, boyutlar, karşılaştırmalar

## Veritabanı boyutu

| şema | boyut (MB) | satır (tahmini) |
|---|---|---|
| clean | 6,228 | 15,809,650 |
| features | 2,966 | 30,187,460 |
| meta | 1 | 444 |
| raw | 8,098 | 16,233,842 |

Toplam veritabanı: 16 GB

## Aşama süreleri (son çalıştırma)

| aşama | adım | süre (s) | satır |
|---|---|---|---|
| clean | 11_audit.sql (ham veri denetimi) | 340.2 | — |
| clean | ANALYZE clean.flows | 14.7000 | — |
| clean | clean.build_day(2018-02-14) | 54.0000 | 822,942 |
| clean | clean.build_day(2018-02-15) | 64.7000 | 1,046,154 |
| clean | clean.build_day(2018-02-16) | 56.1000 | 900,988 |
| clean | clean.build_day(2018-02-20) | 507.1 | 7,948,746 |
| clean | clean.build_day(2018-02-21) | 57.0000 | 1,031,018 |
| clean | clean.build_day(2018-02-22) | 61.0000 | 1,045,288 |
| clean | clean.build_day(2018-02-23) | 61.3000 | 1,045,961 |
| clean | clean.build_day(2018-02-28) | 35.2000 | 593,780 |
| clean | clean.build_day(2018-03-01) | 19.3000 | 331,017 |
| clean | clean.build_day(2018-03-02) | 59.2000 | 1,043,116 |
| export | 40_training_set.sql -> bellek | 29.9000 | 1,000 |
| export | 40_training_set.sql -> bellek (split_rand) | 246.7 | 12,442,146 |
| export | 40_training_set.sql -> bellek (split_temporal) | 177.2 | 9,679,986 |
| features | 30_splits_leakage.sql | 151.1 | — |
| features | ANALYZE features.flow_features | 3.0000 | — |
| features | features.build_day(2018-02-14) | 17.0000 | 822,942 |
| features | features.build_day(2018-02-15) | 21.5000 | 1,046,154 |
| features | features.build_day(2018-02-16) | 18.9000 | 900,988 |
| features | features.build_day(2018-02-20) | 172.4 | 7,948,746 |
| features | features.build_day(2018-02-21) | 21.7000 | 1,031,018 |
| features | features.build_day(2018-02-22) | 20.6000 | 1,045,288 |
| features | features.build_day(2018-02-23) | 21.2000 | 1,045,961 |
| features | features.build_day(2018-02-28) | 12.2000 | 593,780 |
| features | features.build_day(2018-03-01) | 6.4000 | 331,017 |
| features | features.build_day(2018-03-02) | 20.6000 | 1,043,116 |
| ingest | Friday-02-03-2018_TrafficForML_CICFlowMeter.csv | 56.0000 | 1,048,575 |
| ingest | Friday-16-02-2018_TrafficForML_CICFlowMeter.csv | 27.2000 | 1,048,574 |
| ingest | Friday-23-02-2018_TrafficForML_CICFlowMeter.csv | 64.9000 | 1,048,575 |
| ingest | Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv | 898.7 | 7,948,748 |
| ingest | Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv | 6.7000 | 331,100 |
| ingest | Thursday-15-02-2018_TrafficForML_CICFlowMeter.csv | 27.4000 | 1,048,575 |
| ingest | Thursday-22-02-2018_TrafficForML_CICFlowMeter.csv | 73.9000 | 1,048,575 |
| ingest | Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv | 20.1000 | 1,048,575 |
| ingest | Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv | 53.9000 | 1,048,575 |
| ingest | Wednesday-28-02-2018_TrafficForML_CICFlowMeter.csv | 19.7000 | 613,071 |

## Aşama toplamları

| aşama | toplam süre (s) |
|---|---|
| clean | 1,329.8 |
| export | 453.8 |
| features | 486.8 |
| ingest | 1,248.5 |

## Karşılaştırmalar (`python -m ids bench`)

| karşılaştırma | varyant | ölçüt | değer | ayrıntı |
|---|---|---|---|---|
| ingest_100k | COPY, aynı işlemde oluşturulan tablo | rows_per_s | 78,970.0 | {"seconds": 1.266304000004311} |
| ingest_100k | COPY, aynı işlemde oluşturulan tablo | wal_mb | 0.1161 | {} |
| ingest_100k | COPY, mevcut tablo | rows_per_s | 85,633.1 | {"seconds": 1.1677731999952812} |
| ingest_100k | COPY, mevcut tablo | wal_mb | 42.3493 | {} |
| ingest_100k | executemany INSERT | rows_per_s | 12,789.3 | {"seconds": 7.819028300000355} |
| raw_storage | numeric (kullanılan) | tuple_bytes | 357.4 | {"not": "yalnızca 77 akış ölçümü sütunu; tuple başlığı dahil", "part": "flows_20180221", "rows": 1048575} |
| raw_storage | double precision | tuple_bytes | 632.0 | {"not": "yalnızca 77 akış ölçümü sütunu; tuple başlığı dahil", "part": "flows_20180221", "rows": 1048575} |
| raw_storage | numeric (kullanılan) | table_bytes_per_row | 440.8 | {"not": "yalnızca 77 akış ölçümü sütunu; tuple başlığı dahil", "part": "flows_20180221", "rows": 1048575} |
| audit_one_day | sütun başına ayrı tarama (ilk sürüm) | seconds | 55.5453 | {"part": "flows_20180221"} |
| audit_one_day | tek tarama (kullanılan) | seconds | 3.3220 | {"part": "flows_20180221"} |
| moving_window_sum | float toplamı (ters fonksiyon yok) | seconds | nan | {"part": "flows_20180221", "timed_out": true, "timeout_s": 600} |
| moving_window_sum | bigint toplamı (kullanılan) | seconds | 1.3143 | {"part": "flows_20180221", "timed_out": false, "timeout_s": 600} |
| window_feature_sort | indeks yok (sıralama) | seconds | 0.4055 | {"part": "flows_20180301"} |
| window_feature_sort | indeks oluşturma | seconds | 0.9418 | {"part": "flows_20180301"} |
| window_feature_sort | (dst_port, end_ts) indeksi | seconds | 0.1940 | {"part": "flows_20180301"} |
| partition_pruning | capture_day = gün (bölüm budama) | seconds | 0.0728 | {"day": "2018-02-21"} |
| partition_pruning | ts::date = gün (budama yok) | seconds | 0.9196 | {"day": "2018-02-21"} |
| api_latency | POST /predict uçtan uca | p50_ms | 5.1534 | {"ok": 1000, "requests": 1000, "transport": "HTTP/1.1 localhost, keep-alive, tek istemci"} |
| api_latency | POST /predict uçtan uca | p95_ms | 5.7571 | {"ok": 1000, "requests": 1000, "transport": "HTTP/1.1 localhost, keep-alive, tek istemci"} |
| api_latency | POST /predict uçtan uca | p99_ms | 6.1410 | {"ok": 1000, "requests": 1000, "transport": "HTTP/1.1 localhost, keep-alive, tek istemci"} |
| api_latency | sunucu içi (özellik + model) | p50_ms | 1.3037 | {"ok": 1000, "requests": 1000, "transport": "HTTP/1.1 localhost, keep-alive, tek istemci"} |

## EXPLAIN ANALYZE çıktıları

- [`features_build_select_flows_20180221`](explain/features_build_select_flows_20180221.txt)
- [`leakage_overlap`](explain/leakage_overlap.txt)
- [`pruning_non_key`](explain/pruning_non_key.txt)
- [`pruning_partition_key`](explain/pruning_partition_key.txt)
- [`window_port_count_flows_20180301_no_index`](explain/window_port_count_flows_20180301_no_index.txt)
- [`window_port_count_flows_20180301_with_index`](explain/window_port_count_flows_20180301_with_index.txt)

