# Deney sonuçları

Kaynak: `reports/results/*_ids.json` (gerçekten çalıştırılmış deneyler).

## Ortam

- CPU: Intel(R) Core(TM) i9-9880H CPU @ 2.30GHz (16 mantıksal çekirdek), RAM: 31.9 GB
- GPU: NVIDIA GeForce RTX 2080 (kullanılmadı; eğitim CPU'da)
- OS: Windows-10-10.0.19045-SP0, Python 3.10.8
- Sürümler: {'scikit-learn': '1.7.2', 'lightgbm': '4.7.0', 'polars': '1.44.2', 'pyarrow': '25.0.1', 'numpy': '2.2.6', 'psycopg': '3.3.6'}
- Tohum: 20180214

## Ana deney (zamansal ayrım)

| bölüm | satır | saldırı | saldırı % |
|---|---|---|---|
| train | 4,046,891 | 1,407,148 | 34.7711 |
| val | 2,828,534 | 406,400 | 14.3679 |
| test | 2,804,561 | 409,306 | 14.5943 |

Eşik: doğrulamada F1'i en büyükleyen eşik. En iyi model (doğrulama PR-AUC): **lightgbm**.

| model | bölüm | satır | PR-AUC | precision | recall | F1 | YA/1000 normal | accuracy | eşik |
|---|---|---|---|---|---|---|---|---|---|
| majority | val | 2,828,534 | 0.1437 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.8563 | — |
| majority | test | 2,804,561 | 0.1459 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.8541 | — |
| rule_w60_port_n | val | 2,828,534 | 0.7481 | 0.9098 | 0.6885 | 0.7839 | 11.4473 | 0.9454 | 9,357.0 |
| rule_w60_port_n | test | 2,804,561 | 0.7647 | 0.9536 | 0.6855 | 0.7976 | 5.7009 | 0.9492 | 9,357.0 |
| rule_w60_port_n | test_unseen_feature_vectors | 2,059,298 | 0.6674 | 0.9239 | 0.6047 | 0.7310 | 5.4472 | 0.9561 | 9,357.0 |
| logreg | val | 2,828,534 | 0.9672 | 0.9731 | 0.9257 | 0.9488 | 4.2917 | 0.9857 | 0.8609 |
| logreg | test | 2,804,561 | 0.9537 | 0.9643 | 0.9193 | 0.9413 | 5.8090 | 0.9833 | 0.8609 |
| logreg | test_unseen_feature_vectors | 2,059,298 | 0.9141 | 0.9454 | 0.8656 | 0.9038 | 5.4633 | 0.9818 | 0.8609 |
| lightgbm | val | 2,828,534 | 0.9929 | 0.9965 | 0.9368 | 0.9657 | 0.5590 | 0.9904 | 0.7580 |
| lightgbm | test | 2,804,561 | 0.9903 | 0.9898 | 0.9409 | 0.9648 | 1.6499 | 0.9900 | 0.7580 |
| lightgbm | test_unseen_feature_vectors | 2,059,298 | 0.9782 | 0.9810 | 0.9036 | 0.9407 | 1.9134 | 0.9888 | 0.7580 |

### lightgbm: test karışıklık matrisi (eşik = 0.758028)

|  | tahmin BENIGN | tahmin ATTACK |
|---|---|---|
| gerçek BENIGN | 2,391,303 | 3,952 |
| gerçek ATTACK | 24,177 | 385,129 |

### lightgbm: farklı eşiklerde saldırı yakalama ve yanlış alarm yükü (eşikler doğrulamada seçildi)

| çalışma noktası | eşik | test recall | test precision | test YA/1000 normal | test FP | val YA/1000 |
|---|---|---|---|---|---|---|
| best_f1_val | 0.7580 | 0.9409 | 0.9898 | 1.6499 | 3,952 | 0.5590 |
| fa<=0.1/1000_val | 0.8755 | 0.9304 | 0.9962 | 0.6079 | 1,456 | 0.0999 |
| fa<=1/1000_val | 0.7037 | 0.9437 | 0.9860 | 2.2870 | 5,478 | 0.9999 |
| fa<=10/1000_val | 0.5039 | 0.9563 | 0.9272 | 12.8358 | 30,745 | 9.9999 |

### lightgbm: saldırı türü bazında test (eşik = en iyi F1)

| etiket | test satırı | alarm | oran |
|---|---|---|---|
| Benign | 2,395,255 | 3,952 | 0.0016 |
| Bot | 55,932 | 52,430 | 0.9374 |
| Brute Force -Web | 111 | 44 | 0.3964 |
| Brute Force -XSS | 41 | 21 | 0.5122 |
| DDOS attack-HOIC | 110,733 | 110,676 | 0.9995 |
| DDOS attack-LOIC-UDP | 330 | 330 | 1.0000 |
| DDoS attacks-LOIC-HTTP | 105,983 | 105,964 | 0.9998 |
| DoS attacks-GoldenEye | 6,027 | 6,027 | 1.0000 |
| DoS attacks-Hulk | 67,624 | 67,624 | 1.0000 |
| DoS attacks-SlowHTTPTest | 3,469 | 3,469 | 1.0000 |
| DoS attacks-Slowloris | 1,858 | 1,753 | 0.9435 |
| FTP-BruteForce | 7,471 | 7,471 | 1.0000 |
| Infilteration | 27,543 | 7,147 | 0.2595 |
| SQL Injection | 13 | 2 | 0.1538 |
| SSH-Bruteforce | 22,171 | 22,171 | 1.0000 |

Benign satırı için oran = yanlış alarm oranı; saldırı satırları için yakalama (recall).

### lightgbm: eğitimde birebir görülmemiş özellik vektörleri (test alt kümesi)

| etiket | satır | alarm | oran |
|---|---|---|---|
| Benign | 1,856,371 | 3,552 | 0.0019 |
| Bot | 28,680 | 25,178 | 0.8779 |
| Brute Force -Web | 92 | 38 | 0.4130 |
| Brute Force -XSS | 41 | 21 | 0.5122 |
| DDOS attack-HOIC | 3,316 | 3,286 | 0.9910 |
| DDOS attack-LOIC-UDP | 330 | 330 | 1.0000 |
| DDoS attacks-LOIC-HTTP | 105,821 | 105,802 | 0.9998 |
| DoS attacks-GoldenEye | 6,016 | 6,016 | 1.0000 |
| DoS attacks-Hulk | 17,334 | 17,334 | 1.0000 |
| DoS attacks-Slowloris | 1,838 | 1,733 | 0.9429 |
| FTP-BruteForce | 3 | 3 | 1.0000 |
| Infilteration | 21,624 | 5,810 | 0.2687 |
| SQL Injection | 12 | 2 | 0.1667 |
| SSH-Bruteforce | 17,820 | 17,820 | 1.0000 |

### Süre ve gecikme

| ölçüm | değer |
|---|---|
| LightGBM eğitim (s) | 132.7 |
| Lojistik regresyon eğitim (s) | 182.8 |
| tek akış, model p50 (ms) | 0.0764 |
| tek akış, model p95 (ms) | 0.1533 |
| tek akış, model p99 (ms) | 0.2134 |
| toplu puanlama (akış/s) | 259,861.2 |

## Rastgele satır ayrımı vs zamansal ayrım (LightGBM, aynı eğitim boyutu)

| ayrım | test kümesi | satır | PR-AUC | precision | recall | F1 | YA/1000 |
|---|---|---|---|---|---|---|---|
| temporal | test | 2,804,561 | 0.9902 | 0.9899 | 0.9419 | 0.9653 | 1.6445 |
| temporal | test_unseen_feature_vectors | 2,059,298 | 0.9781 | 0.9811 | 0.9053 | 0.9417 | 1.9021 |
| random | test | 3,159,729 | 0.9970 | 0.9842 | 0.9595 | 0.9717 | 2.6830 |
| random | test_unseen_feature_vectors | 2,325,150 | 0.9942 | 0.9758 | 0.9429 | 0.9591 | 2.8754 |

## Ablasyon (LightGBM, zamansal ayrım, test)

| varyant | özellik | PR-AUC | precision | recall | F1 | YA/1000 | recall (görülmemiş) |
|---|---|---|---|---|---|---|---|
| all_features | 90 | 0.9901 | 0.9891 | 0.9421 | 0.9650 | 1.7718 | 0.9057 |
| no_shortcut_risk (dst_port, init_win) | 87 | 0.9899 | 0.9910 | 0.9401 | 0.9648 | 1.4666 | 0.9016 |
| no_window_features | 82 | 0.9723 | 0.9945 | 0.9266 | 0.9594 | 0.8734 | 0.8804 |
| cicflowmeter_only (SQL özellikleri yok) | 70 | 0.9727 | 0.9960 | 0.9256 | 0.9595 | 0.6312 | 0.8785 |

## Çok sınıflı deney (saldırı türü, LightGBM, zamansal ayrım, test)

Macro-F1 = 0.8407

| sınıf | test satırı | precision | recall | F1 |
|---|---|---|---|---|
| Benign | 2,395,255 | 0.9976 | 0.9357 | 0.9657 |
| Bot | 55,932 | 1.0000 | 0.9227 | 0.9598 |
| Brute Force -Web | 111 | 0.2656 | 0.9189 | 0.4121 |
| Brute Force -XSS | 41 | 0.6667 | 0.8780 | 0.7579 |
| DDOS attack-HOIC | 110,733 | 1.0000 | 0.9996 | 0.9998 |
| DDOS attack-LOIC-UDP | 330 | 1.0000 | 0.9394 | 0.9688 |
| DDoS attacks-LOIC-HTTP | 105,983 | 0.9997 | 0.9998 | 0.9998 |
| DoS attacks-GoldenEye | 6,027 | 0.9998 | 0.9998 | 0.9998 |
| DoS attacks-Hulk | 67,624 | 1.0000 | 1.0000 | 1.0000 |
| DoS attacks-SlowHTTPTest | 3,469 | 1.0000 | 1.0000 | 1.0000 |
| DoS attacks-Slowloris | 1,858 | 0.9971 | 0.9187 | 0.9563 |
| FTP-BruteForce | 7,471 | 1.0000 | 0.9351 | 0.9665 |
| Infilteration | 27,543 | 0.1401 | 0.9205 | 0.2432 |
| SQL Injection | 13 | 0.5000 | 0.3077 | 0.3810 |
| SSH-Bruteforce | 22,171 | 1.0000 | 1.0000 | 1.0000 |

Karışıklık matrisi (satır = gerçek, sütun = tahmin; sınıf sırası yukarıdaki gibi):

| gerçek \ tahmin | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0: Benign | 2,241,208 | 0 | 277 | 16 | 0 | 0 | 29 | 1 | 0 | 0 | 5 | 0 | 153,716 | 3 | 0 |
| 1: Bot | 2,407 | 51,609 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1,916 | 0 | 0 |
| 2: Brute Force -Web | 8 | 0 | 102 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| 3: Brute Force -XSS | 5 | 0 | 0 | 36 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 4: DDOS attack-HOIC | 42 | 0 | 0 | 0 | 110,691 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 5: DDOS attack-LOIC-UDP | 20 | 0 | 0 | 0 | 0 | 310 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 6: DDoS attacks-LOIC-HTTP | 17 | 0 | 0 | 0 | 0 | 0 | 105,966 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 7: DoS attacks-GoldenEye | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 6,026 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 8: DoS attacks-Hulk | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 67,624 | 0 | 0 | 0 | 0 | 0 | 0 |
| 9: DoS attacks-SlowHTTPTest | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3,469 | 0 | 0 | 0 | 0 | 0 |
| 10: DoS attacks-Slowloris | 151 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1,707 | 0 | 0 | 0 | 0 |
| 11: FTP-BruteForce | 485 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6,986 | 0 | 0 | 0 |
| 12: Infilteration | 2,189 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 25,354 | 0 | 0 |
| 13: SQL Injection | 2 | 0 | 5 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 |
| 14: SSH-Bruteforce | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 22,171 |

## Zorlayıcı test: gün dışarıda bırakma (leave-one-day-out, LightGBM)

Eşik, kalan günlerin doğrulama bölümünde seçildi; dışarıda bırakılan gün hiç görülmedi.

| test günü | saldırı türleri | eğitimde de olanlar | satır | PR-AUC | precision | recall | YA/1000 | tür bazında recall |
|---|---|---|---|---|---|---|---|---|
| 2018-02-14 | FTP-BruteForce, SSH-Bruteforce | hiçbiri | 822,942 | 0.7036 | 0.9985 | 0.3024 | 0.1036 | FTP-BruteForce: 0.962; SSH-Bruteforce: 0.081 |
| 2018-02-15 | DoS attacks-GoldenEye, DoS attacks-Slowloris | hiçbiri | 1,046,154 | 0.3663 | 0.9658 | 0.2072 | 0.3821 | DoS attacks-GoldenEye: 0.255; DoS attacks-Slowloris: 0.015 |
| 2018-02-16 | DoS attacks-Hulk, DoS attacks-SlowHTTPTest | hiçbiri | 900,988 | 1.0000 | 1.0000 | 0.9789 | 0.0000 | DoS attacks-Hulk: 0.978; DoS attacks-SlowHTTPTest: 1.000 |
| 2018-02-20 | DDoS attacks-LOIC-HTTP | hiçbiri | 7,948,746 | 0.9024 | 0.8340 | 0.5000 | 7.7774 | DDoS attacks-LOIC-HTTP: 0.500 |
| 2018-02-21 | DDOS attack-HOIC, DDOS attack-LOIC-UDP | hiçbiri | 1,031,018 | 1.0000 | 1.0000 | 0.5942 | 0.0000 | DDOS attack-HOIC: 0.596; DDOS attack-LOIC-UDP: 0.000 |
| 2018-02-22 | Brute Force -Web, Brute Force -XSS, SQL Injection | Brute Force -Web, Brute Force -XSS, SQL Injection | 1,045,288 | 0.3443 | 0.8972 | 0.2652 | 0.0105 | Brute Force -Web: 0.237; Brute Force -XSS: 0.456; SQL Injection: 0.029 |
| 2018-02-23 | Brute Force -Web, Brute Force -XSS, SQL Injection | Brute Force -Web, Brute Force -XSS, SQL Injection | 1,045,961 | 0.3095 | 0.9448 | 0.2420 | 0.0077 | Brute Force -Web: 0.182; Brute Force -XSS: 0.470; SQL Injection: 0.000 |
| 2018-02-28 | Infilteration | Infilteration | 593,780 | 0.0959 | 0.1035 | 0.0805 | 81.6953 | Infilteration: 0.081 |
| 2018-03-01 | Infilteration | Infilteration | 331,017 | 0.3578 | 0.7563 | 0.0026 | 0.3236 | Infilteration: 0.003 |
| 2018-03-02 | Bot | hiçbiri | 1,043,116 | 0.7006 | 0.7746 | 0.0088 | 0.9543 | Bot: 0.009 |

