# Deney sonuçları

Kaynak: `reports/results/*_ids_sample.json` (gerçekten çalıştırılmış deneyler).

## Ortam

- CPU: Intel(R) Core(TM) i9-9880H CPU @ 2.30GHz (16 mantıksal çekirdek), RAM: 31.9 GB
- GPU: NVIDIA GeForce RTX 2080 (kullanılmadı; eğitim CPU'da)
- OS: Windows-10-10.0.19045-SP0, Python 3.10.8
- Sürümler: {'scikit-learn': '1.7.2', 'lightgbm': '4.7.0', 'polars': '1.44.2', 'pyarrow': '25.0.1', 'numpy': '2.2.6', 'psycopg': '3.3.6'}
- Tohum: 20180214

## Ana deney (zamansal ayrım)

| bölüm | satır | saldırı | saldırı % |
|---|---|---|---|
| train | 20,801 | 4,827 | 23.2056 |
| val | 6,931 | 1,368 | 19.7374 |
| test | 7,246 | 1,391 | 19.1968 |

Eşik: doğrulamada F1'i en büyükleyen eşik. En iyi model (doğrulama PR-AUC): **lightgbm**.

| model | bölüm | satır | PR-AUC | precision | recall | F1 | YA/1000 normal | accuracy | eşik |
|---|---|---|---|---|---|---|---|---|---|
| majority | val | 6,931 | 0.1974 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.8026 | — |
| majority | test | 7,246 | 0.1920 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.8080 | — |
| rule_w60_port_n | val | 6,931 | 0.7349 | 0.7540 | 0.6477 | 0.6968 | 51.9504 | 0.8888 | 5.0000 |
| rule_w60_port_n | test | 7,246 | 0.7586 | 0.7900 | 0.6707 | 0.7255 | 42.3570 | 0.9026 | 5.0000 |
| rule_w60_port_n | test_unseen_feature_vectors | 6,823 | 0.7268 | 0.7418 | 0.6396 | 0.6869 | 40.9509 | 0.9094 | 5.0000 |
| logreg | val | 6,931 | 0.8995 | 0.9587 | 0.7807 | 0.8606 | 8.2689 | 0.9501 | 0.7967 |
| logreg | test | 7,246 | 0.9214 | 0.9493 | 0.7944 | 0.8650 | 10.0769 | 0.9524 | 0.7967 |
| logreg | test_unseen_feature_vectors | 6,823 | 0.8919 | 0.9412 | 0.7547 | 0.8377 | 8.6760 | 0.9546 | 0.7967 |
| lightgbm | val | 6,931 | 0.9336 | 1.0000 | 0.8246 | 0.9038 | 0.0000 | 0.9654 | 0.8780 |
| lightgbm | test | 7,246 | 0.9559 | 1.0000 | 0.8347 | 0.9099 | 0.0000 | 0.9683 | 0.8780 |
| lightgbm | test_unseen_feature_vectors | 6,823 | 0.9335 | 1.0000 | 0.7849 | 0.8795 | 0.0000 | 0.9666 | 0.8780 |

### lightgbm: test karışıklık matrisi (eşik = 0.878050)

|  | tahmin BENIGN | tahmin ATTACK |
|---|---|---|
| gerçek BENIGN | 5,855 | 0 |
| gerçek ATTACK | 230 | 1,161 |

### lightgbm: farklı eşiklerde saldırı yakalama ve yanlış alarm yükü (eşikler doğrulamada seçildi)

| çalışma noktası | eşik | test recall | test precision | test YA/1000 normal | test FP | val YA/1000 |
|---|---|---|---|---|---|---|
| best_f1_val | 0.8780 | 0.8347 | 1.0000 | 0.0000 | 0 | 0.0000 |
| fa<=0.1/1000_val | 0.8499 | 0.8382 | 0.9991 | 0.1708 | 1 | 0.0000 |
| fa<=1/1000_val | 0.8418 | 0.8404 | 0.9974 | 0.5124 | 3 | 0.8988 |
| fa<=10/1000_val | 0.5955 | 0.8720 | 0.9338 | 14.6883 | 86 | 9.8868 |

### lightgbm: saldırı türü bazında test (eşik = en iyi F1)

| etiket | test satırı | alarm | oran |
|---|---|---|---|
| Benign | 5,855 | 0 | 0.0000 |
| Bot | 114 | 103 | 0.9035 |
| Brute Force -Web | 111 | 105 | 0.9459 |
| Brute Force -XSS | 41 | 36 | 0.8780 |
| DDOS attack-HOIC | 98 | 98 | 1.0000 |
| DDOS attack-LOIC-UDP | 82 | 82 | 1.0000 |
| DDoS attacks-LOIC-HTTP | 111 | 111 | 1.0000 |
| DoS attacks-GoldenEye | 87 | 87 | 1.0000 |
| DoS attacks-Hulk | 97 | 97 | 1.0000 |
| DoS attacks-SlowHTTPTest | 108 | 108 | 1.0000 |
| DoS attacks-Slowloris | 105 | 100 | 0.9524 |
| FTP-BruteForce | 110 | 110 | 1.0000 |
| Infilteration | 202 | 3 | 0.0149 |
| SQL Injection | 13 | 9 | 0.6923 |
| SSH-Bruteforce | 112 | 112 | 1.0000 |

Benign satırı için oran = yanlış alarm oranı; saldırı satırları için yakalama (recall).

### lightgbm: eğitimde birebir görülmemiş özellik vektörleri (test alt kümesi)

| etiket | satır | alarm | oran |
|---|---|---|---|
| Benign | 5,763 | 0 | 0.0000 |
| Bot | 87 | 76 | 0.8736 |
| Brute Force -Web | 92 | 86 | 0.9348 |
| Brute Force -XSS | 41 | 36 | 0.8780 |
| DDOS attack-HOIC | 98 | 98 | 1.0000 |
| DDOS attack-LOIC-UDP | 82 | 82 | 1.0000 |
| DDoS attacks-LOIC-HTTP | 111 | 111 | 1.0000 |
| DoS attacks-GoldenEye | 87 | 87 | 1.0000 |
| DoS attacks-Hulk | 95 | 95 | 1.0000 |
| DoS attacks-SlowHTTPTest | 2 | 2 | 1.0000 |
| DoS attacks-Slowloris | 104 | 99 | 0.9519 |
| FTP-BruteForce | 1 | 1 | 1.0000 |
| Infilteration | 201 | 3 | 0.0149 |
| SQL Injection | 12 | 9 | 0.7500 |
| SSH-Bruteforce | 47 | 47 | 1.0000 |

### Süre ve gecikme

| ölçüm | değer |
|---|---|
| LightGBM eğitim (s) | 2.6185 |
| Lojistik regresyon eğitim (s) | 0.9422 |
| tek akış, model p50 (ms) | 0.0944 |
| tek akış, model p95 (ms) | 0.1634 |
| tek akış, model p99 (ms) | 0.2761 |
| toplu puanlama (akış/s) | 260,703.7 |

## Rastgele satır ayrımı vs zamansal ayrım (LightGBM, aynı eğitim boyutu)

| ayrım | test kümesi | satır | PR-AUC | precision | recall | F1 | YA/1000 |
|---|---|---|---|---|---|---|---|
| temporal | test | 7,246 | 0.9559 | 1.0000 | 0.8347 | 0.9099 | 0.0000 |
| temporal | test_unseen_feature_vectors | 6,823 | 0.9335 | 1.0000 | 0.7849 | 0.8795 | 0.0000 |
| random | test | 7,562 | 0.9566 | 0.9848 | 0.8571 | 0.9166 | 3.7313 |
| random | test_unseen_feature_vectors | 7,046 | 0.9370 | 0.9795 | 0.8174 | 0.8911 | 3.8201 |

## Ablasyon (LightGBM, zamansal ayrım, test)

| varyant | özellik | PR-AUC | precision | recall | F1 | YA/1000 | recall (görülmemiş) |
|---|---|---|---|---|---|---|---|
| all_features | 90 | 0.9559 | 1.0000 | 0.8347 | 0.9099 | 0.0000 | 0.7849 |
| no_shortcut_risk (dst_port, init_win) | 87 | 0.9501 | 0.9915 | 0.8347 | 0.9063 | 1.7079 | 0.7877 |
| no_window_features | 82 | 0.9502 | 0.9957 | 0.8411 | 0.9119 | 0.8540 | 0.7925 |
| cicflowmeter_only (SQL özellikleri yok) | 70 | 0.9504 | 0.9924 | 0.8447 | 0.9126 | 1.5371 | 0.7972 |

## Çok sınıflı deney (saldırı türü, LightGBM, zamansal ayrım, test)

Macro-F1 = 0.9202

| sınıf | test satırı | precision | recall | F1 |
|---|---|---|---|---|
| Benign | 5,855 | 0.9708 | 0.9588 | 0.9648 |
| Bot | 114 | 1.0000 | 0.9298 | 0.9636 |
| Brute Force -Web | 111 | 0.9646 | 0.9820 | 0.9732 |
| Brute Force -XSS | 41 | 0.9444 | 0.8293 | 0.8831 |
| DDOS attack-HOIC | 98 | 1.0000 | 1.0000 | 1.0000 |
| DDOS attack-LOIC-UDP | 82 | 1.0000 | 0.9024 | 0.9487 |
| DDoS attacks-LOIC-HTTP | 111 | 1.0000 | 0.9910 | 0.9955 |
| DoS attacks-GoldenEye | 87 | 0.9886 | 1.0000 | 0.9943 |
| DoS attacks-Hulk | 97 | 0.9604 | 1.0000 | 0.9798 |
| DoS attacks-SlowHTTPTest | 108 | 0.9818 | 1.0000 | 0.9908 |
| DoS attacks-Slowloris | 105 | 1.0000 | 0.9143 | 0.9552 |
| FTP-BruteForce | 110 | 1.0000 | 0.9818 | 0.9908 |
| Infilteration | 202 | 0.2067 | 0.3069 | 0.2470 |
| SQL Injection | 13 | 1.0000 | 0.8462 | 0.9167 |
| SSH-Bruteforce | 112 | 1.0000 | 1.0000 | 1.0000 |

Karışıklık matrisi (satır = gerçek, sütun = tahmin; sınıf sırası yukarıdaki gibi):

| gerçek \ tahmin | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0: Benign | 5,614 | 0 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 238 | 0 | 0 |
| 1: Bot | 8 | 106 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2: Brute Force -Web | 2 | 0 | 109 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 3: Brute Force -XSS | 4 | 0 | 3 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 4: DDOS attack-HOIC | 0 | 0 | 0 | 0 | 98 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 5: DDOS attack-LOIC-UDP | 8 | 0 | 0 | 0 | 0 | 74 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 6: DDoS attacks-LOIC-HTTP | 1 | 0 | 0 | 0 | 0 | 0 | 110 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 7: DoS attacks-GoldenEye | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 87 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 8: DoS attacks-Hulk | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 97 | 0 | 0 | 0 | 0 | 0 | 0 |
| 9: DoS attacks-SlowHTTPTest | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 108 | 0 | 0 | 0 | 0 | 0 |
| 10: DoS attacks-Slowloris | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 4 | 0 | 96 | 0 | 0 | 0 | 0 |
| 11: FTP-BruteForce | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 108 | 0 | 0 | 0 |
| 12: Infilteration | 140 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 62 | 0 | 0 |
| 13: SQL Injection | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 11 | 0 |
| 14: SSH-Bruteforce | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 112 |

## Zorlayıcı test: gün dışarıda bırakma (leave-one-day-out, LightGBM)

Eşik, kalan günlerin doğrulama bölümünde seçildi; dışarıda bırakılan gün hiç görülmedi.

| test günü | saldırı türleri | eğitimde de olanlar | satır | PR-AUC | precision | recall | YA/1000 | tür bazında recall |
|---|---|---|---|---|---|---|---|---|
| 2018-02-14 | FTP-BruteForce, SSH-Bruteforce | hiçbiri | 4,188 | 0.9985 | 1.0000 | 0.6498 | 0.0000 | FTP-BruteForce: 0.816; SSH-Bruteforce: 0.485 |
| 2018-02-15 | DoS attacks-GoldenEye, DoS attacks-Slowloris | hiçbiri | 4,191 | 0.9855 | 0.9813 | 0.6616 | 5.0000 | DoS attacks-GoldenEye: 0.948; DoS attacks-Slowloris: 0.371 |
| 2018-02-16 | DoS attacks-Hulk, DoS attacks-SlowHTTPTest | hiçbiri | 4,175 | 1.0000 | 1.0000 | 0.9974 | 0.0000 | DoS attacks-Hulk: 0.995; DoS attacks-SlowHTTPTest: 1.000 |
| 2018-02-20 | DDoS attacks-LOIC-HTTP | hiçbiri | 3,600 | 0.9619 | 0.9710 | 0.5017 | 3.0000 | DDoS attacks-LOIC-HTTP: 0.502 |
| 2018-02-21 | DDOS attack-HOIC, DDOS attack-LOIC-UDP | hiçbiri | 4,200 | 0.9943 | 1.0000 | 0.1225 | 0.0000 | DDOS attack-HOIC: 0.245; DDOS attack-LOIC-UDP: 0.000 |
| 2018-02-22 | Brute Force -Web, Brute Force -XSS, SQL Injection | Brute Force -Web, Brute Force -XSS, SQL Injection | 3,362 | 0.9957 | 0.9970 | 0.9254 | 0.3333 | Brute Force -Web: 0.964; Brute Force -XSS: 0.886; SQL Injection: 0.735 |
| 2018-02-23 | Brute Force -Web, Brute Force -XSS, SQL Injection | Brute Force -Web, Brute Force -XSS, SQL Injection | 3,566 | 0.7846 | 0.9923 | 0.6837 | 1.0000 | Brute Force -Web: 0.569; Brute Force -XSS: 0.947; SQL Injection: 0.717 |
| 2018-02-28 | Infilteration | Infilteration | 3,600 | 0.1604 | 0.0599 | 0.0167 | 52.3333 | Infilteration: 0.017 |
| 2018-03-01 | Infilteration | Infilteration | 3,600 | 0.1675 | 0.0435 | 0.0017 | 7.3333 | Infilteration: 0.002 |
| 2018-03-02 | Bot | hiçbiri | 3,600 | 0.8842 | 1.0000 | 0.2450 | 0.0000 | Bot: 0.245 |

