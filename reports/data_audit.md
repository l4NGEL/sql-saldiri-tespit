# Veri denetimi ve temizleme raporu

Kaynak veritabanı: `ids`. Üretim: `python -m ids report`.

## İçe aktarılan dosyalar

| dosya | gün | boyut (MB) | fiziksel satır | tekrar başlık | bozuk satır | yüklenen | süre (s) | satır/s |
|---|---|---|---|---|---|---|---|---|
| Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv | 2018-02-14 | 358 | 1,048,576 | 0 | 0 | 1,048,575 | 20.1000 | 52,183 |
| Thursday-15-02-2018_TrafficForML_CICFlowMeter.csv | 2018-02-15 | 376 | 1,048,576 | 0 | 0 | 1,048,575 | 27.4000 | 38,204 |
| Friday-16-02-2018_TrafficForML_CICFlowMeter.csv | 2018-02-16 | 334 | 1,048,576 | 1 | 0 | 1,048,574 | 27.2000 | 38,595 |
| Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv | 2018-02-20 | 4,055 | 7,948,749 | 0 | 0 | 7,948,748 | 898.7 | 8,845 |
| Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv | 2018-02-21 | 329 | 1,048,576 | 0 | 0 | 1,048,575 | 53.9000 | 19,453 |
| Thursday-22-02-2018_TrafficForML_CICFlowMeter.csv | 2018-02-22 | 383 | 1,048,576 | 0 | 0 | 1,048,575 | 73.9000 | 14,182 |
| Friday-23-02-2018_TrafficForML_CICFlowMeter.csv | 2018-02-23 | 383 | 1,048,576 | 0 | 0 | 1,048,575 | 64.9000 | 16,165 |
| Wednesday-28-02-2018_TrafficForML_CICFlowMeter.csv | 2018-02-28 | 209 | 613,105 | 33 | 0 | 613,071 | 19.7000 | 31,183 |
| Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv | 2018-03-01 | 108 | 331,126 | 25 | 0 | 331,100 | 6.7000 | 49,316 |
| Friday-02-03-2018_TrafficForML_CICFlowMeter.csv | 2018-03-02 | 352 | 1,048,576 | 0 | 0 | 1,048,575 | 56.0000 | 18,710 |

> 1.048.575 = Excel'in satır sınırı (1.048.576) − başlık. Bu değerde biten dosyalar resmi işlenmiş CSV'lerde kesilmiştir; kesilen akışlar bu projede geri getirilemez (bkz. README).

## Temizleme kuralları (tüm günler)

| adım | kural | işlem | etkilenen |
|---|---|---|---|
| 0 | ham satır (raw.flows) | input | 16,232,943 |
| 1 | zaman damgası boş / yakalama günü dışında | drop | 14 |
| 2 | 12 saatlik saat düzeltmesi (saat<8 -> +12 saat) | fix | 8,122,897 |
| 3 | zorunlu alan eksik | drop | 0 |
| 4 | negatif flow_duration | drop | 0 |
| 5 | Infinity/NaN/negatif ölçüm -> NULL (hücre sayısı) | fix | 191,522 |
| 6 | birebir tekrar eden kayıt | drop | 410,707 |
| 7 | etiket çelişkisi (aynı akış, farklı etiket) | drop | 13,212 |
| 9 | temiz satır (clean.flows) | output | 15,809,010 |

### Gün bazında

| gün | adım 0 | adım 1 | adım 2 | adım 3 | adım 4 | adım 5 | adım 6 | adım 7 | adım 9 |
|---|---|---|---|---|---|---|---|---|---|
| 2018-02-14 | 1,048,575 | 5 | 378,388 | 0 | 0 | 7,648 | 225,628 | 0 | 822,942 |
| 2018-02-15 | 1,048,575 | 0 | 389,349 | 0 | 0 | 16,054 | 2,421 | 0 | 1,046,154 |
| 2018-02-16 | 1,048,574 | 0 | 908,339 | 0 | 0 | 0 | 147,586 | 0 | 900,988 |
| 2018-02-20 | 7,948,748 | 0 | 3,597,671 | 0 | 0 | 118,906 | 2 | 0 | 7,948,746 |
| 2018-02-21 | 1,048,575 | 0 | 1,044,705 | 0 | 0 | 0 | 17,557 | 0 | 1,031,018 |
| 2018-02-22 | 1,048,575 | 9 | 431,207 | 0 | 0 | 11,220 | 3,278 | 0 | 1,045,288 |
| 2018-02-23 | 1,048,575 | 0 | 435,450 | 0 | 0 | 11,418 | 2,614 | 0 | 1,045,961 |
| 2018-02-28 | 613,071 | 0 | 270,452 | 0 | 0 | 12,338 | 6,089 | 13,202 | 593,780 |
| 2018-03-01 | 331,100 | 0 | 165,358 | 0 | 0 | 5,838 | 73 | 10 | 331,017 |
| 2018-03-02 | 1,048,575 | 0 | 501,978 | 0 | 0 | 8,100 | 5,459 | 0 | 1,043,116 |

Adım 0 = ham, 9 = temiz satır; 2 ve 5 düzeltmedir (satır düşürmez; 5 hücre sayar).

## Sütun sorunları (düşürme kurallarından geçen ham satırlarda)

| sütun | sorun | hücre |
|---|---|---|
| init_bwd_win_byts | negative | 8,255,535 |
| init_fwd_win_byts | negative | 4,432,594 |
| flow_pkts_s | infinite | 95,760 |
| flow_byts_s | nan | 59,721 |
| flow_byts_s | infinite | 36,039 |
| flow_iat_min | negative | 1 |
| fwd_iat_min | negative | 1 |

`init_*_win_byts = -1` CICFlowMeter'ın "gözlenmedi" işaretidir; korunur, düzeltme sayımına girmez.

## Tutarlılık denetimleri (bilgi amaçlı, satır düşürülmez)

| kural | satır |
|---|---|
| flow_duration = 0 (oranlar tanımsız) | 95,760 |
| flow_pkts_s != pkts/duration | 0 |
| fwd_len != pkts*mean | 0 |
| pkt_len_max < pkt_len_min | 0 |
| subflow_fwd_pkts != tot_fwd_pkts | 0 |

## Etiketlerin zaman aralığı (12 saat düzeltmesi sonrası)

| gün | etiket | ilk | son | ham satır |
|---|---|---|---|---|
| 2018-02-14 | Benign | 2018-02-14T08:28:20 | 2018-02-14T17:30:48 | 667,621 |
| 2018-02-14 | FTP-BruteForce | 2018-02-14T10:33:26 | 2018-02-14T12:10:31 | 193,360 |
| 2018-02-14 | SSH-Bruteforce | 2018-02-14T14:01:21 | 2018-02-14T15:32:30 | 187,589 |
| 2018-02-15 | Benign | 2018-02-15T08:23:27 | 2018-02-15T17:54:44 | 996,077 |
| 2018-02-15 | DoS attacks-GoldenEye | 2018-02-15T09:27:42 | 2018-02-15T10:02:59 | 41,508 |
| 2018-02-15 | DoS attacks-Slowloris | 2018-02-15T11:00:12 | 2018-02-15T11:42:01 | 10,990 |
| 2018-02-16 | Benign | 2018-02-16T08:26:55 | 2018-02-16T13:48:43 | 446,772 |
| 2018-02-16 | DoS attacks-SlowHTTPTest | 2018-02-16T10:12:14 | 2018-02-16T10:58:08 | 139,890 |
| 2018-02-16 | DoS attacks-Hulk | 2018-02-16T13:45:27 | 2018-02-16T13:48:44 | 461,912 |
| 2018-02-20 | Benign | 2018-02-20T08:00:00 | 2018-02-20T19:59:59 | 7,372,557 |
| 2018-02-20 | DDoS attacks-LOIC-HTTP | 2018-02-20T10:13:54 | 2018-02-20T13:29:15 | 576,191 |
| 2018-02-21 | Benign | 2018-02-21T08:32:54 | 2018-02-21T14:33:29 | 360,833 |
| 2018-02-21 | DDOS attack-LOIC-UDP | 2018-02-21T10:08:51 | 2018-02-21T10:43:16 | 1,730 |
| 2018-02-21 | DDOS attack-HOIC | 2018-02-21T14:11:08 | 2018-02-21T14:33:29 | 686,012 |
| 2018-02-22 | Benign | 2018-02-22T08:22:17 | 2018-02-22T17:30:23 | 1,048,204 |
| 2018-02-22 | Brute Force -Web | 2018-02-22T10:13:44 | 2018-02-22T11:23:11 | 249 |
| 2018-02-22 | SQL Injection | 2018-02-22T11:09:45 | 2018-02-22T16:27:51 | 34 |
| 2018-02-22 | Brute Force -XSS | 2018-02-22T13:51:39 | 2018-02-22T14:28:40 | 79 |
| 2018-02-23 | Benign | 2018-02-23T08:15:09 | 2018-02-23T17:30:46 | 1,048,009 |
| 2018-02-23 | Brute Force -Web | 2018-02-23T09:17:04 | 2018-02-23T11:02:58 | 362 |
| 2018-02-23 | SQL Injection | 2018-02-23T10:22:41 | 2018-02-23T15:17:24 | 53 |
| 2018-02-23 | Brute Force -XSS | 2018-02-23T13:01:04 | 2018-02-23T14:10:05 | 151 |
| 2018-02-28 | Benign | 2018-02-28T08:21:58 | 2018-02-28T17:50:14 | 544,200 |
| 2018-02-28 | Infilteration | 2018-02-28T10:50:00 | 2018-02-28T14:39:59 | 68,871 |
| 2018-03-01 | Benign | 2018-03-01T08:16:28 | 2018-03-01T17:45:28 | 238,037 |
| 2018-03-01 | Infilteration | 2018-03-01T09:57:00 | 2018-03-01T15:36:59 | 93,063 |
| 2018-03-02 | Benign | 2018-03-02T08:46:33 | 2018-03-02T17:30:18 | 762,384 |
| 2018-03-02 | Bot | 2018-03-02T10:13:28 | 2018-03-02T15:54:50 | 286,191 |

## Sınıf dağılımı: ham → temiz

| etiket | ham | temiz | temiz payı |
|---|---|---|---|
| Benign | 13,484,708 | 13,461,350 | 85.1500 |
| DDOS attack-HOIC | 686,012 | 668,461 | 4.2280 |
| DDoS attacks-LOIC-HTTP | 576,191 | 576,191 | 3.6450 |
| DoS attacks-Hulk | 461,912 | 434,873 | 2.7510 |
| Bot | 286,191 | 282,310 | 1.7860 |
| Infilteration | 161,934 | 155,291 | 0.9820 |
| SSH-Bruteforce | 187,589 | 117,322 | 0.7420 |
| DoS attacks-GoldenEye | 41,508 | 41,455 | 0.2620 |
| FTP-BruteForce | 193,360 | 39,352 | 0.2490 |
| DoS attacks-SlowHTTPTest | 139,890 | 19,462 | 0.1230 |
| DoS attacks-Slowloris | 10,990 | 10,285 | 0.0650 |
| DDOS attack-LOIC-UDP | 1,730 | 1,730 | 0.0110 |
| Brute Force -Web | 611 | 611 | 0.0040 |
| Brute Force -XSS | 230 | 230 | 0.0010 |
| SQL Injection | 87 | 87 | 0.0010 |

