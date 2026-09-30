# Ayrım tasarımı ve sızıntı denetimleri

**random**: Karşılaştırma amaçlı rastgele satır ayrımı: hash(flow_id) mod 100 -> <60 train, <80 val, diğer test. Benzer akışları iki tarafa dağıtır.

**temporal**: Olay (saldırı patlaması) farkındalıklı kronolojik ayrım. Her gün saldırı akışları zamana göre sıralanır; aralarında 5 dakikadan uzun boşluk olan kümeler ayrı patlamadır. Her patlama, kendi saldırı akışlarının zamansal %60 ve %80 yüzdeliklerinden bölünür: öncesi train, arası val, sonrası test (test her zaman train'den sonradır). Her sınırdan sonra min(60 s, patlama süresinin %5'i) gap; patlamanın 60 s öncesi/sonrası gap. Patlama içindeki normal akışlar da aynı zaman sınırlarını izler. Patlama dışı (yalnız normal trafik) zaman 10 dakikalık bloklara bölünür ve bloklar 5'li döngüyle train,train,val,train,test atanır; bölüm değişen blok başındaki 60 s gap.

## Saldırı olayları (gün içi, etiketlerden türetilmiş)

| gün | olay | başlangıç | bitiş | etiketler |
|---|---|---|---|---|
| 2018-02-14 | 1 | 2018-02-14 10:33:26 | 2018-02-14 12:10:31 | FTP-BruteForce |
| 2018-02-14 | 2 | 2018-02-14 14:01:21 | 2018-02-14 15:32:30 | SSH-Bruteforce |
| 2018-02-15 | 1 | 2018-02-15 09:27:42 | 2018-02-15 09:31:12 | DoS attacks-GoldenEye |
| 2018-02-15 | 2 | 2018-02-15 09:37:44 | 2018-02-15 09:40:34 | DoS attacks-GoldenEye |
| 2018-02-15 | 3 | 2018-02-15 09:49:24 | 2018-02-15 09:57:10 | DoS attacks-GoldenEye |
| 2018-02-15 | 4 | 2018-02-15 10:02:59 | 2018-02-15 10:02:59 | DoS attacks-GoldenEye |
| 2018-02-15 | 5 | 2018-02-15 11:00:12 | 2018-02-15 11:42:01 | DoS attacks-Slowloris |
| 2018-02-16 | 1 | 2018-02-16 10:12:14 | 2018-02-16 10:58:08 | DoS attacks-SlowHTTPTest |
| 2018-02-16 | 2 | 2018-02-16 13:45:27 | 2018-02-16 13:48:44 | DoS attacks-Hulk |
| 2018-02-20 | 1 | 2018-02-20 10:13:54 | 2018-02-20 11:16:48 | DDoS attacks-LOIC-HTTP |
| 2018-02-20 | 2 | 2018-02-20 13:14:17 | 2018-02-20 13:29:15 | DDoS attacks-LOIC-HTTP |
| 2018-02-21 | 1 | 2018-02-21 10:08:51 | 2018-02-21 10:43:16 | DDOS attack-LOIC-UDP |
| 2018-02-21 | 2 | 2018-02-21 14:11:08 | 2018-02-21 14:33:29 | DDOS attack-HOIC |
| 2018-02-22 | 1 | 2018-02-22 10:13:44 | 2018-02-22 11:23:11 | Brute Force -Web, SQL Injection |
| 2018-02-22 | 2 | 2018-02-22 13:51:39 | 2018-02-22 14:28:40 | Brute Force -XSS, SQL Injection |
| 2018-02-22 | 3 | 2018-02-22 16:14:30 | 2018-02-22 16:27:51 | SQL Injection |
| 2018-02-23 | 1 | 2018-02-23 09:17:04 | 2018-02-23 09:17:04 | Brute Force -Web |
| 2018-02-23 | 2 | 2018-02-23 09:57:12 | 2018-02-23 09:57:12 | Brute Force -Web |
| 2018-02-23 | 3 | 2018-02-23 10:02:37 | 2018-02-23 11:02:58 | Brute Force -Web, SQL Injection |
| 2018-02-23 | 4 | 2018-02-23 13:01:04 | 2018-02-23 14:10:05 | Brute Force -XSS |
| 2018-02-23 | 5 | 2018-02-23 15:05:22 | 2018-02-23 15:17:24 | SQL Injection |
| 2018-02-28 | 1 | 2018-02-28 10:50:00 | 2018-02-28 12:04:59 | Infilteration |
| 2018-02-28 | 2 | 2018-02-28 13:42:00 | 2018-02-28 14:39:59 | Infilteration |
| 2018-03-01 | 1 | 2018-03-01 09:57:00 | 2018-03-01 10:54:59 | Infilteration |
| 2018-03-01 | 2 | 2018-03-01 14:00:00 | 2018-03-01 15:36:59 | Infilteration |
| 2018-03-02 | 1 | 2018-03-02 10:13:28 | 2018-03-02 15:54:50 | Bot |

## Ayrım `temporal`: etiket × bölüm (satır)

| etiket | train | val | test | gap |
|---|---|---|---|---|
| Benign | 7,539,130 | 2,422,134 | 2,395,255 | 1,104,831 |
| DDOS attack-HOIC | 400,857 | 110,409 | 110,733 | 46,462 |
| DDoS attacks-LOIC-HTTP | 345,611 | 106,019 | 105,983 | 18,578 |
| DoS attacks-Hulk | 260,111 | 63,744 | 67,624 | 43,394 |
| Bot | 169,383 | 55,935 | 55,932 | 1,060 |
| Infilteration | 93,145 | 28,993 | 27,543 | 5,610 |
| SSH-Bruteforce | 70,385 | 22,167 | 22,171 | 2,599 |
| DoS attacks-GoldenEye | 24,619 | 5,886 | 6,027 | 4,923 |
| FTP-BruteForce | 23,606 | 7,493 | 7,471 | 782 |
| DoS attacks-SlowHTTPTest | 11,676 | 3,478 | 3,469 | 839 |
| DoS attacks-Slowloris | 6,167 | 1,833 | 1,858 | 427 |
| DDOS attack-LOIC-UDP | 1,037 | 282 | 330 | 81 |
| Brute Force -Web | 365 | 109 | 111 | 26 |
| Brute Force -XSS | 136 | 39 | 41 | 14 |
| SQL Injection | 50 | 13 | 13 | 11 |
| **toplam** | 8,946,278 | 2,828,534 | 2,804,561 | 1,229,637 |

## Ayrım `random`: etiket × bölüm (satır)

| etiket | train | val | test | gap |
|---|---|---|---|---|
| Benign | 8,079,105 | 2,692,340 | 2,689,905 | 0 |
| DDOS attack-HOIC | 400,677 | 133,156 | 134,628 | 0 |
| DDoS attacks-LOIC-HTTP | 346,275 | 114,856 | 115,060 | 0 |
| DoS attacks-Hulk | 261,288 | 87,061 | 86,524 | 0 |
| Bot | 169,584 | 56,305 | 56,421 | 0 |
| Infilteration | 93,101 | 31,127 | 31,063 | 0 |
| SSH-Bruteforce | 70,447 | 23,448 | 23,427 | 0 |
| DoS attacks-GoldenEye | 24,893 | 8,245 | 8,317 | 0 |
| FTP-BruteForce | 23,733 | 7,790 | 7,829 | 0 |
| DoS attacks-SlowHTTPTest | 11,693 | 3,878 | 3,891 | 0 |
| DoS attacks-Slowloris | 6,182 | 2,003 | 2,100 | 0 |
| DDOS attack-LOIC-UDP | 1,072 | 308 | 350 | 0 |
| Brute Force -Web | 356 | 120 | 135 | 0 |
| Brute Force -XSS | 131 | 41 | 58 | 0 |
| SQL Injection | 48 | 18 | 21 | 0 |
| **toplam** | 9,488,585 | 3,160,696 | 3,159,729 | 0 |

## Sızıntı denetimleri

| denetim | ayrım | bölüm | satır | çakışan | oran % | ayrıntı |
|---|---|---|---|---|---|---|
| exact_feature_vector_in_train | random | test | 3,159,729 | 834,579 | 26.4100 | {"attack_rows": 469824, "benign_rows": 2689905, "attack_overlap": 215335, "benign_overlap": 619244} |
| exact_feature_vector_in_train | random | val | 3,160,696 | 833,795 | 26.3800 | {"attack_rows": 468356, "benign_rows": 2692340, "attack_overlap": 214362, "benign_overlap": 619433} |
| exact_feature_vector_in_train | temporal | test | 2,804,561 | 745,263 | 26.5700 | {"attack_rows": 409306, "benign_rows": 2395255, "attack_overlap": 206379, "benign_overlap": 538884} |
| exact_feature_vector_in_train | temporal | val | 2,828,534 | 747,347 | 26.4200 | {"attack_rows": 406400, "benign_rows": 2422134, "attack_overlap": 206390, "benign_overlap": 540957} |
| flow_id_unique | all | all | 15,809,010 | 0 | 0.0000 | {} |
| min_seconds_between_different_split_blocks | temporal | all | 369 | 16 | 4.3400 | {"min_gap_s": -420.000000, "median_gap_s": 61} |
| segment_purity | temporal | all | 468 | 0 | 0.0000 | {} |

- `exact_feature_vector_in_train`: val/test satırının tüm akış ölçümleri (zaman damgası hariç) eğitimdeki bir satırla birebir aynı. Bu tür kayıtlar zamansal ayrımda da kaçınılmazdır (ör. aynı kaba kuvvet isteği binlerce kez). Bu yüzden test sonuçları ayrıca **eğitimde görülmemiş vektörler** alt kümesinde raporlanır.
- `segment_purity`: bir zaman bloğu/olay parçası birden fazla bölüme düşmemeli (0 olmalı).
- `min_seconds_between_different_split_blocks`: farklı bölümlü komşu parçalar arasındaki boşluk.

