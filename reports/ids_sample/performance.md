# Performans: süreler, boyutlar, karşılaştırmalar

## Veritabanı boyutu

| şema | boyut (MB) | satır (tahmini) |
|---|---|---|
| clean | 16 | 38,082 |
| features | 8 | 79,602 |
| meta | 1 | 465 |
| raw | 19 | 38,128 |

Toplam veritabanı: 55 MB

## Aşama süreleri (son çalıştırma)

| aşama | adım | süre (s) | satır |
|---|---|---|---|
| clean | 11_audit.sql (ham veri denetimi) | 0.8000 | — |
| clean | ANALYZE clean.flows | 1.6000 | — |
| clean | clean.build_day(2018-02-14) | 0.4000 | 4,188 |
| clean | clean.build_day(2018-02-15) | 0.3000 | 4,191 |
| clean | clean.build_day(2018-02-16) | 0.4000 | 4,175 |
| clean | clean.build_day(2018-02-20) | 0.3000 | 3,600 |
| clean | clean.build_day(2018-02-21) | 0.3000 | 4,200 |
| clean | clean.build_day(2018-02-22) | 0.3000 | 3,362 |
| clean | clean.build_day(2018-02-23) | 0.3000 | 3,566 |
| clean | clean.build_day(2018-02-28) | 0.3000 | 3,600 |
| clean | clean.build_day(2018-03-01) | 0.3000 | 3,600 |
| clean | clean.build_day(2018-03-02) | 0.3000 | 3,600 |
| export | 40_training_set.sql -> bellek | 0.3000 | 1,000 |
| export | 40_training_set.sql -> bellek (split_rand) | 0.6000 | 38,082 |
| export | 40_training_set.sql -> bellek (split_temporal) | 0.7000 | 34,978 |
| export | 40_training_set.sql -> parquet | 1.0000 | 38,082 |
| features | 30_splits_leakage.sql | 0.3000 | — |
| features | ANALYZE features.flow_features | 0.4000 | — |
| features | features.build_day(2018-02-14) | 0.1000 | 4,188 |
| features | features.build_day(2018-02-15) | 0.1000 | 4,191 |
| features | features.build_day(2018-02-16) | 0.1000 | 4,175 |
| features | features.build_day(2018-02-20) | 0.1000 | 3,600 |
| features | features.build_day(2018-02-21) | 0.1000 | 4,200 |
| features | features.build_day(2018-02-22) | 0.1000 | 3,362 |
| features | features.build_day(2018-02-23) | 0.1000 | 3,566 |
| features | features.build_day(2018-02-28) | 0.1000 | 3,600 |
| features | features.build_day(2018-03-01) | 0.1000 | 3,600 |
| features | features.build_day(2018-03-02) | 0.1000 | 3,600 |
| ingest | Friday-02-03-2018_TrafficForML_CICFlowMeter.csv.gz | 0.1000 | 3,600 |
| ingest | Friday-16-02-2018_TrafficForML_CICFlowMeter.csv.gz | 0.1000 | 4,200 |
| ingest | Friday-23-02-2018_TrafficForML_CICFlowMeter.csv.gz | 0.1000 | 3,566 |
| ingest | Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv.gz | 0.1000 | 3,600 |
| ingest | Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv.gz | 0.1000 | 3,600 |
| ingest | Thursday-15-02-2018_TrafficForML_CICFlowMeter.csv.gz | 0.1000 | 4,200 |
| ingest | Thursday-22-02-2018_TrafficForML_CICFlowMeter.csv.gz | 0.1000 | 3,362 |
| ingest | Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv.gz | 0.1000 | 4,200 |
| ingest | Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv.gz | 0.1000 | 4,200 |
| ingest | Wednesday-28-02-2018_TrafficForML_CICFlowMeter.csv.gz | 0.1000 | 3,600 |

## Aşama toplamları

| aşama | toplam süre (s) |
|---|---|
| clean | 5.7000 |
| export | 2.5000 |
| features | 1.5000 |
| ingest | 0.7000 |

## Karşılaştırmalar (`python -m ids bench`)

| karşılaştırma | varyant | ölçüt | değer | ayrıntı |
|---|---|---|---|---|
| ingest_100k | COPY, aynı işlemde oluşturulan tablo | rows_per_s | 1,396,260.0 | {"seconds": 0.0716198999871267} |
| ingest_100k | COPY, aynı işlemde oluşturulan tablo | wal_mb | 0.0000 | {} |
| ingest_100k | COPY, mevcut tablo | rows_per_s | 1,867,455.5 | {"seconds": 0.053548800002317876} |
| ingest_100k | COPY, mevcut tablo | wal_mb | 0.0000 | {} |
| ingest_100k | executemany INSERT | rows_per_s | 289,029.5 | {"seconds": 0.3459854000102496} |
| raw_storage | numeric (kullanılan) | tuple_bytes | 382.1 | {"not": "yalnızca 77 akış ölçümü sütunu; tuple başlığı dahil", "part": "flows_20180228", "rows": 3600} |
| raw_storage | double precision | tuple_bytes | 632.0 | {"not": "yalnızca 77 akış ölçümü sütunu; tuple başlığı dahil", "part": "flows_20180228", "rows": 3600} |
| raw_storage | numeric (kullanılan) | table_bytes_per_row | 473.3 | {"not": "yalnızca 77 akış ölçümü sütunu; tuple başlığı dahil", "part": "flows_20180228", "rows": 3600} |
| audit_one_day | sütun başına ayrı tarama (ilk sürüm) | seconds | 0.2335 | {"part": "flows_20180228"} |
| audit_one_day | tek tarama (kullanılan) | seconds | 0.0870 | {"part": "flows_20180228"} |
| moving_window_sum | float toplamı (ters fonksiyon yok) | seconds | 0.0058 | {"part": "flows_20180228", "timed_out": false, "timeout_s": 600} |
| moving_window_sum | bigint toplamı (kullanılan) | seconds | 0.0055 | {"part": "flows_20180228", "timed_out": false, "timeout_s": 600} |
| window_feature_sort | indeks yok (sıralama) | seconds | 0.0061 | {"part": "flows_20180222"} |
| window_feature_sort | indeks oluşturma | seconds | 0.0914 | {"part": "flows_20180222"} |
| window_feature_sort | (dst_port, end_ts) indeksi | seconds | 0.0028 | {"part": "flows_20180222"} |
| partition_pruning | capture_day = gün (bölüm budama) | seconds | 0.0018 | {"day": "2018-02-28"} |
| partition_pruning | ts::date = gün (budama yok) | seconds | 0.0076 | {"day": "2018-02-28"} |

## EXPLAIN ANALYZE çıktıları

- [`leakage_overlap`](explain/leakage_overlap.txt)
- [`pruning_non_key`](explain/pruning_non_key.txt)
- [`pruning_partition_key`](explain/pruning_partition_key.txt)
- [`window_port_count_flows_20180222_no_index`](explain/window_port_count_flows_20180222_no_index.txt)
- [`window_port_count_flows_20180222_with_index`](explain/window_port_count_flows_20180222_with_index.txt)

