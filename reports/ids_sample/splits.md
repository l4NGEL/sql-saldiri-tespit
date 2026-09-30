# Ayrım tasarımı ve sızıntı denetimleri

**random**: Karşılaştırma amaçlı rastgele satır ayrımı: hash(flow_id) mod 100 -> <60 train, <80 val, diğer test. Benzer akışları iki tarafa dağıtır.

**temporal**: Olay (saldırı patlaması) farkındalıklı kronolojik ayrım. Her gün saldırı akışları zamana göre sıralanır; aralarında 5 dakikadan uzun boşluk olan kümeler ayrı patlamadır. Her patlama, kendi saldırı akışlarının zamansal %60 ve %80 yüzdeliklerinden bölünür: öncesi train, arası val, sonrası test (test her zaman train'den sonradır). Her sınırdan sonra min(60 s, patlama süresinin %5'i) gap; patlamanın 60 s öncesi/sonrası gap. Patlama içindeki normal akışlar da aynı zaman sınırlarını izler. Patlama dışı (yalnız normal trafik) zaman 10 dakikalık bloklara bölünür ve bloklar 5'li döngüyle train,train,val,train,test atanır; bölüm değişen blok başındaki 60 s gap.

## Saldırı olayları (gün içi, etiketlerden türetilmiş)

| gün | olay | başlangıç | bitiş | etiketler |
|---|---|---|---|---|
| 2018-02-14 | 1 | 2018-02-14 10:33:32 | 2018-02-14 12:10:27 | FTP-BruteForce |
| 2018-02-14 | 2 | 2018-02-14 14:01:56 | 2018-02-14 15:32:30 | SSH-Bruteforce |
| 2018-02-15 | 1 | 2018-02-15 09:27:42 | 2018-02-15 09:31:12 | DoS attacks-GoldenEye |
| 2018-02-15 | 2 | 2018-02-15 09:37:48 | 2018-02-15 09:40:34 | DoS attacks-GoldenEye |
| 2018-02-15 | 3 | 2018-02-15 09:49:24 | 2018-02-15 09:57:10 | DoS attacks-GoldenEye |
| 2018-02-15 | 4 | 2018-02-15 11:00:12 | 2018-02-15 11:41:44 | DoS attacks-Slowloris |
| 2018-02-16 | 1 | 2018-02-16 10:12:14 | 2018-02-16 10:57:59 | DoS attacks-SlowHTTPTest |
| 2018-02-16 | 2 | 2018-02-16 13:45:27 | 2018-02-16 13:48:44 | DoS attacks-Hulk |
| 2018-02-20 | 1 | 2018-02-20 10:14:08 | 2018-02-20 11:16:47 | DDoS attacks-LOIC-HTTP |
| 2018-02-21 | 1 | 2018-02-21 10:08:53 | 2018-02-21 10:43:16 | DDOS attack-LOIC-UDP |
| 2018-02-21 | 2 | 2018-02-21 14:11:12 | 2018-02-21 14:33:28 | DDOS attack-HOIC |
| 2018-02-22 | 1 | 2018-02-22 10:13:44 | 2018-02-22 11:23:11 | Brute Force -Web, SQL Injection |
| 2018-02-22 | 2 | 2018-02-22 13:51:39 | 2018-02-22 14:28:40 | Brute Force -XSS, SQL Injection |
| 2018-02-22 | 3 | 2018-02-22 16:14:30 | 2018-02-22 16:27:51 | SQL Injection |
| 2018-02-23 | 1 | 2018-02-23 09:17:04 | 2018-02-23 09:17:04 | Brute Force -Web |
| 2018-02-23 | 2 | 2018-02-23 09:57:12 | 2018-02-23 09:57:12 | Brute Force -Web |
| 2018-02-23 | 3 | 2018-02-23 10:02:37 | 2018-02-23 11:02:58 | Brute Force -Web, SQL Injection |
| 2018-02-23 | 4 | 2018-02-23 13:01:04 | 2018-02-23 14:10:05 | Brute Force -XSS |
| 2018-02-23 | 5 | 2018-02-23 15:05:22 | 2018-02-23 15:17:24 | SQL Injection |
| 2018-02-28 | 1 | 2018-02-28 10:50:04 | 2018-02-28 12:04:53 | Infilteration |
| 2018-02-28 | 2 | 2018-02-28 13:42:04 | 2018-02-28 14:39:52 | Infilteration |
| 2018-03-01 | 1 | 2018-03-01 09:57:17 | 2018-03-01 10:54:52 | Infilteration |
| 2018-03-01 | 2 | 2018-03-01 14:00:45 | 2018-03-01 15:36:41 | Infilteration |
| 2018-03-02 | 1 | 2018-03-02 10:14:44 | 2018-03-02 10:14:44 | Bot |
| 2018-03-02 | 2 | 2018-03-02 10:20:30 | 2018-03-02 14:01:18 | Bot |
| 2018-03-02 | 3 | 2018-03-02 14:06:54 | 2018-03-02 15:53:32 | Bot |

## Ayrım `temporal`: etiket × bölüm (satır)

| etiket | train | val | test | gap |
|---|---|---|---|---|
| Benign | 15,974 | 5,563 | 5,855 | 2,608 |
| Infilteration | 717 | 230 | 202 | 51 |
| Brute Force -Web | 365 | 109 | 111 | 26 |
| DDoS attacks-LOIC-HTTP | 359 | 111 | 111 | 19 |
| DDOS attack-LOIC-UDP | 359 | 93 | 82 | 66 |
| DDOS attack-HOIC | 358 | 91 | 98 | 53 |
| DoS attacks-Hulk | 358 | 89 | 97 | 56 |
| Bot | 358 | 113 | 114 | 15 |
| DoS attacks-GoldenEye | 357 | 68 | 87 | 88 |
| SSH-Bruteforce | 357 | 114 | 112 | 13 |
| FTP-BruteForce | 355 | 106 | 110 | 21 |
| DoS attacks-Slowloris | 354 | 102 | 105 | 30 |
| DoS attacks-SlowHTTPTest | 344 | 90 | 108 | 33 |
| Brute Force -XSS | 136 | 39 | 41 | 14 |
| SQL Injection | 50 | 13 | 13 | 11 |
| **toplam** | 20,801 | 6,931 | 7,246 | 3,104 |

## Ayrım `random`: etiket × bölüm (satır)

| etiket | train | val | test | gap |
|---|---|---|---|---|
| Benign | 18,209 | 5,895 | 5,896 | 0 |
| Infilteration | 716 | 236 | 248 | 0 |
| DDoS attacks-LOIC-HTTP | 378 | 120 | 102 | 0 |
| Brute Force -Web | 375 | 117 | 119 | 0 |
| DDOS attack-HOIC | 369 | 111 | 120 | 0 |
| Bot | 369 | 133 | 98 | 0 |
| SSH-Bruteforce | 365 | 106 | 125 | 0 |
| DoS attacks-Slowloris | 362 | 113 | 116 | 0 |
| FTP-BruteForce | 360 | 106 | 126 | 0 |
| DoS attacks-GoldenEye | 358 | 113 | 129 | 0 |
| DDOS attack-LOIC-UDP | 357 | 104 | 139 | 0 |
| DoS attacks-Hulk | 345 | 132 | 123 | 0 |
| DoS attacks-SlowHTTPTest | 321 | 114 | 140 | 0 |
| Brute Force -XSS | 123 | 44 | 63 | 0 |
| SQL Injection | 52 | 17 | 18 | 0 |
| **toplam** | 23,059 | 7,461 | 7,562 | 0 |

## Sızıntı denetimleri

| denetim | ayrım | bölüm | satır | çakışan | oran % | ayrıntı |
|---|---|---|---|---|---|---|
| exact_feature_vector_in_train | random | test | 7,562 | 516 | 6.8200 | {"attack_rows": 1666, "benign_rows": 5896, "attack_overlap": 379, "benign_overlap": 137} |
| exact_feature_vector_in_train | random | val | 7,461 | 448 | 6.0000 | {"attack_rows": 1566, "benign_rows": 5895, "attack_overlap": 340, "benign_overlap": 108} |
| exact_feature_vector_in_train | temporal | test | 7,246 | 423 | 5.8400 | {"attack_rows": 1391, "benign_rows": 5855, "attack_overlap": 331, "benign_overlap": 92} |
| exact_feature_vector_in_train | temporal | val | 6,931 | 401 | 5.7900 | {"attack_rows": 1368, "benign_rows": 5563, "attack_overlap": 302, "benign_overlap": 99} |
| flow_id_unique | all | all | 38,082 | 0 | 0.0000 | {} |
| min_seconds_between_different_split_blocks | temporal | all | 326 | 14 | 4.2900 | {"min_gap_s": -276.000000, "median_gap_s": 78} |
| segment_purity | temporal | all | 417 | 0 | 0.0000 | {} |

- `exact_feature_vector_in_train`: val/test satırının tüm akış ölçümleri (zaman damgası hariç) eğitimdeki bir satırla birebir aynı. Bu tür kayıtlar zamansal ayrımda da kaçınılmazdır (ör. aynı kaba kuvvet isteği binlerce kez). Bu yüzden test sonuçları ayrıca **eğitimde görülmemiş vektörler** alt kümesinde raporlanır.
- `segment_purity`: bir zaman bloğu/olay parçası birden fazla bölüme düşmemeli (0 olmalı).
- `min_seconds_between_different_split_blocks`: farklı bölümlü komşu parçalar arasındaki boşluk.

