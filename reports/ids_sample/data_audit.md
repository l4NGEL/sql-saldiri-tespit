# Veri denetimi ve temizleme raporu

Kaynak veritabanı: `ids_sample`. Üretim: `python -m ids report`.

## İçe aktarılan dosyalar

| dosya | gün | boyut (MB) | fiziksel satır | tekrar başlık | bozuk satır | yüklenen | süre (s) | satır/s |
|---|---|---|---|---|---|---|---|---|
| Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv.gz | 2018-02-14 | 0 | 4,201 | 0 | 0 | 4,200 | 0.1000 | 44,948 |
| Thursday-15-02-2018_TrafficForML_CICFlowMeter.csv.gz | 2018-02-15 | 0 | 4,201 | 0 | 0 | 4,200 | 0.1000 | 56,796 |
| Friday-16-02-2018_TrafficForML_CICFlowMeter.csv.gz | 2018-02-16 | 0 | 4,201 | 0 | 0 | 4,200 | 0.1000 | 54,348 |
| Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv.gz | 2018-02-20 | 0 | 3,601 | 0 | 0 | 3,600 | 0.1000 | 44,711 |
| Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv.gz | 2018-02-21 | 0 | 4,201 | 0 | 0 | 4,200 | 0.1000 | 57,033 |
| Thursday-22-02-2018_TrafficForML_CICFlowMeter.csv.gz | 2018-02-22 | 0 | 3,363 | 0 | 0 | 3,362 | 0.1000 | 43,443 |
| Friday-23-02-2018_TrafficForML_CICFlowMeter.csv.gz | 2018-02-23 | 0 | 3,567 | 0 | 0 | 3,566 | 0.1000 | 56,513 |
| Wednesday-28-02-2018_TrafficForML_CICFlowMeter.csv.gz | 2018-02-28 | 0 | 3,601 | 0 | 0 | 3,600 | 0.1000 | 55,072 |
| Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv.gz | 2018-03-01 | 0 | 3,601 | 0 | 0 | 3,600 | 0.1000 | 57,815 |
| Friday-02-03-2018_TrafficForML_CICFlowMeter.csv.gz | 2018-03-02 | 0 | 3,601 | 0 | 0 | 3,600 | 0.1000 | 56,221 |

> 1.048.575 = Excel'in satır sınırı (1.048.576) − başlık. Bu değerde biten dosyalar resmi işlenmiş CSV'lerde kesilmiştir; kesilen akışlar bu projede geri getirilemez (bkz. README).

## Temizleme kuralları (tüm günler)

| adım | kural | işlem | etkilenen |
|---|---|---|---|
| 0 | ham satır (raw.flows) | input | 38,128 |
| 1 | zaman damgası boş / yakalama günü dışında | drop | 0 |
| 2 | 12 saatlik saat düzeltmesi (saat<8 -> +12 saat) | fix | 19,063 |
| 3 | zorunlu alan eksik | drop | 0 |
| 4 | negatif flow_duration | drop | 0 |
| 5 | Infinity/NaN/negatif ölçüm -> NULL (hücre sayısı) | fix | 406 |
| 6 | birebir tekrar eden kayıt | drop | 46 |
| 7 | etiket çelişkisi (aynı akış, farklı etiket) | drop | 0 |
| 9 | temiz satır (clean.flows) | output | 38,082 |

### Gün bazında

| gün | adım 0 | adım 1 | adım 2 | adım 3 | adım 4 | adım 5 | adım 6 | adım 7 | adım 9 |
|---|---|---|---|---|---|---|---|---|---|
| 2018-02-14 | 4,200 | 0 | 1,443 | 0 | 0 | 36 | 12 | 0 | 4,188 |
| 2018-02-15 | 4,200 | 0 | 1,179 | 0 | 0 | 58 | 9 | 0 | 4,191 |
| 2018-02-16 | 4,200 | 0 | 3,596 | 0 | 0 | 0 | 25 | 0 | 4,175 |
| 2018-02-20 | 3,600 | 0 | 1,434 | 0 | 0 | 52 | 0 | 0 | 3,600 |
| 2018-02-21 | 4,200 | 0 | 3,587 | 0 | 0 | 0 | 0 | 0 | 4,200 |
| 2018-02-22 | 3,362 | 0 | 1,330 | 0 | 0 | 36 | 0 | 0 | 3,362 |
| 2018-02-23 | 3,566 | 0 | 1,433 | 0 | 0 | 42 | 0 | 0 | 3,566 |
| 2018-02-28 | 3,600 | 0 | 1,613 | 0 | 0 | 66 | 0 | 0 | 3,600 |
| 2018-03-01 | 3,600 | 0 | 1,770 | 0 | 0 | 86 | 0 | 0 | 3,600 |
| 2018-03-02 | 3,600 | 0 | 1,678 | 0 | 0 | 30 | 0 | 0 | 3,600 |

Adım 0 = ham, 9 = temiz satır; 2 ve 5 düzeltmedir (satır düşürmez; 5 hücre sayar).

## Sütun sorunları (düşürme kurallarından geçen ham satırlarda)

| sütun | sorun | hücre |
|---|---|---|
| init_bwd_win_byts | negative | 16,288 |
| init_fwd_win_byts | negative | 9,170 |
| flow_pkts_s | infinite | 203 |
| flow_byts_s | nan | 126 |
| flow_byts_s | infinite | 77 |

`init_*_win_byts = -1` CICFlowMeter'ın "gözlenmedi" işaretidir; korunur, düzeltme sayımına girmez.

## Tutarlılık denetimleri (bilgi amaçlı, satır düşürülmez)

| kural | satır |
|---|---|
| flow_duration = 0 (oranlar tanımsız) | 203 |
| flow_pkts_s != pkts/duration | 0 |
| fwd_len != pkts*mean | 0 |
| pkt_len_max < pkt_len_min | 0 |
| subflow_fwd_pkts != tot_fwd_pkts | 0 |

## Etiketlerin zaman aralığı (12 saat düzeltmesi sonrası)

| gün | etiket | ilk | son | ham satır |
|---|---|---|---|---|
| 2018-02-14 | Benign | 2018-02-14T08:28:29 | 2018-02-14T17:30:11 | 3,000 |
| 2018-02-14 | FTP-BruteForce | 2018-02-14T10:33:32 | 2018-02-14T12:10:27 | 600 |
| 2018-02-14 | SSH-Bruteforce | 2018-02-14T14:01:56 | 2018-02-14T15:32:30 | 600 |
| 2018-02-15 | Benign | 2018-02-15T08:24:19 | 2018-02-15T17:50:20 | 3,000 |
| 2018-02-15 | DoS attacks-GoldenEye | 2018-02-15T09:27:42 | 2018-02-15T09:57:10 | 600 |
| 2018-02-15 | DoS attacks-Slowloris | 2018-02-15T11:00:12 | 2018-02-15T11:41:44 | 600 |
| 2018-02-16 | Benign | 2018-02-16T09:32:09 | 2018-02-16T13:48:40 | 3,000 |
| 2018-02-16 | DoS attacks-SlowHTTPTest | 2018-02-16T10:12:14 | 2018-02-16T10:57:59 | 600 |
| 2018-02-16 | DoS attacks-Hulk | 2018-02-16T13:45:27 | 2018-02-16T13:48:44 | 600 |
| 2018-02-20 | Benign | 2018-02-20T08:28:19 | 2018-02-20T19:32:33 | 3,000 |
| 2018-02-20 | DDoS attacks-LOIC-HTTP | 2018-02-20T10:14:08 | 2018-02-20T11:16:47 | 600 |
| 2018-02-21 | Benign | 2018-02-21T08:45:22 | 2018-02-21T14:33:29 | 3,000 |
| 2018-02-21 | DDOS attack-LOIC-UDP | 2018-02-21T10:08:53 | 2018-02-21T10:43:16 | 600 |
| 2018-02-21 | DDOS attack-HOIC | 2018-02-21T14:11:12 | 2018-02-21T14:33:28 | 600 |
| 2018-02-22 | Benign | 2018-02-22T08:22:19 | 2018-02-22T17:29:48 | 3,000 |
| 2018-02-22 | Brute Force -Web | 2018-02-22T10:13:44 | 2018-02-22T11:23:11 | 249 |
| 2018-02-22 | SQL Injection | 2018-02-22T11:09:45 | 2018-02-22T16:27:51 | 34 |
| 2018-02-22 | Brute Force -XSS | 2018-02-22T13:51:39 | 2018-02-22T14:28:40 | 79 |
| 2018-02-23 | Benign | 2018-02-23T08:15:18 | 2018-02-23T17:29:42 | 3,000 |
| 2018-02-23 | Brute Force -Web | 2018-02-23T09:17:04 | 2018-02-23T11:02:58 | 362 |
| 2018-02-23 | SQL Injection | 2018-02-23T10:22:41 | 2018-02-23T15:17:24 | 53 |
| 2018-02-23 | Brute Force -XSS | 2018-02-23T13:01:04 | 2018-02-23T14:10:05 | 151 |
| 2018-02-28 | Benign | 2018-02-28T08:22:08 | 2018-02-28T17:49:21 | 3,000 |
| 2018-02-28 | Infilteration | 2018-02-28T10:50:04 | 2018-02-28T14:39:52 | 600 |
| 2018-03-01 | Benign | 2018-03-01T08:16:40 | 2018-03-01T17:30:30 | 3,000 |
| 2018-03-01 | Infilteration | 2018-03-01T09:57:17 | 2018-03-01T15:36:41 | 600 |
| 2018-03-02 | Benign | 2018-03-02T08:46:46 | 2018-03-02T17:29:32 | 3,000 |
| 2018-03-02 | Bot | 2018-03-02T10:14:44 | 2018-03-02T15:53:32 | 600 |

## Sınıf dağılımı: ham → temiz

| etiket | ham | temiz | temiz payı |
|---|---|---|---|
| Benign | 30,000 | 30,000 | 78.7770 |
| Infilteration | 1,200 | 1,200 | 3.1510 |
| Brute Force -Web | 611 | 611 | 1.6040 |
| DDOS attack-HOIC | 600 | 600 | 1.5760 |
| DDOS attack-LOIC-UDP | 600 | 600 | 1.5760 |
| DoS attacks-GoldenEye | 600 | 600 | 1.5760 |
| DoS attacks-Hulk | 600 | 600 | 1.5760 |
| DDoS attacks-LOIC-HTTP | 600 | 600 | 1.5760 |
| Bot | 600 | 600 | 1.5760 |
| SSH-Bruteforce | 600 | 596 | 1.5650 |
| FTP-BruteForce | 600 | 592 | 1.5550 |
| DoS attacks-Slowloris | 600 | 591 | 1.5520 |
| DoS attacks-SlowHTTPTest | 600 | 575 | 1.5100 |
| Brute Force -XSS | 230 | 230 | 0.6040 |
| SQL Injection | 87 | 87 | 0.2280 |

