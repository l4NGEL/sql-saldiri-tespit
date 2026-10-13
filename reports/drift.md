# Dağılım kayması (drift) raporu

Referans: zamansal eğitim bölümü; LODO analizinde dışarıda bırakılan gün hariç. Bölmeler: tüm günlerin eğitim bölümünün ondalıkları (approxQuantile, göreli hata 1e-3). PSI eşikleri: > 0,10 orta, > 0,25 belirgin.

## Görülmemiş gün: drift ve gerçek performans

| Gün | Saldırılar | Ağırlıklı PSI (tüm) | Ağırlıklı PSI (yalnız normal) | PSI > 0,25 özellik | LODO PR-AUC | LODO yakalama | En çok kayan özellikler |
|---|---|---|---|---|---|---|---|
| 2018-02-14 | FTP-BruteForce, SSH-Bruteforce | 0,727 | 0,577 | 9/90 | 0,704 | 0,302 | w60_all_n, w60_port_n, w10_port_n |
| 2018-02-15 | DoS attacks-GoldenEye, DoS attacks-Slowloris | 0,590 | 0,533 | 5/90 | 0,366 | 0,207 | w60_all_n, w60_port_n, w10_port_n |
| 2018-02-16 | DoS attacks-Hulk, DoS attacks-SlowHTTPTest | 4,319 | 6,412 | 78/90 | 1,000 | 0,979 | init_fwd_win_byts, w60_all_n, fwd_header_len |
| 2018-02-20 | DDoS attacks-LOIC-HTTP | 1,247 | 1,324 | 9/90 | 0,902 | 0,500 | w60_all_n, w60_port_n, w10_port_n |
| 2018-02-21 | DDOS attack-HOIC, DDOS attack-LOIC-UDP | 4,829 | 6,227 | 80/90 | 1,000 | 0,594 | init_fwd_win_byts, fwd_iat_tot, fwd_iat_max |
| 2018-02-22 | Brute Force -Web, Brute Force -XSS, SQL Injection | 0,729 | 0,576 | 7/90 | 0,344 | 0,265 | w60_all_n, w60_port_n, w60_port_rst_share |
| 2018-02-23 | Brute Force -Web, Brute Force -XSS, SQL Injection | 0,794 | 0,620 | 8/90 | 0,309 | 0,242 | w60_all_n, w60_port_n, w60_port_rst_share |
| 2018-02-28 | Infilteration | 0,853 | 0,876 | 10/90 | 0,096 | 0,081 | w60_all_n, w60_port_n, w10_port_n |
| 2018-03-01 | Infilteration | 0,980 | 0,908 | 12/90 | 0,358 | 0,003 | w60_all_n, w60_port_n, w10_port_n |
| 2018-03-02 | Bot | 0,721 | 0,625 | 16/90 | 0,701 | 0,009 | w60_all_n, w60_port_n, w10_port_n |

Spearman sıra korelasyonu (N = 10 gün; küçük örneklem, p değerleri yol göstericidir):

| Sinyal ~ hedef | rho | p |
|---|---|---|
| all_flows.mean_psi ~ lodo.pr_auc | 0,75 | 0,013 |
| all_flows.mean_psi ~ lodo.recall | 0,47 | 0,174 |
| benign_only.mean_psi ~ lodo.pr_auc | 0,43 | 0,214 |
| benign_only.mean_psi ~ lodo.recall | 0,39 | 0,260 |
| all_flows.weighted_psi ~ lodo.pr_auc | 0,43 | 0,214 |
| all_flows.weighted_psi ~ lodo.recall | 0,54 | 0,108 |
| benign_only.weighted_psi ~ lodo.pr_auc | 0,56 | 0,090 |
| benign_only.weighted_psi ~ lodo.recall | 0,42 | 0,229 |
| lodo.prevalence ~ all_flows.weighted_psi | 0,55 | 0,098 |

## Ana model izleme (test bölümü, gün bazında)

Eşik 0,758. Referans: aynı günün doğrulama bölümü skorları (zamanca testten hemen önce).

| Gün | Test akışı | Skor PSI (val → test) | Alarm oranı val → test | Saldırı payı val → test | Yakalama | Yanlış alarm / 1000 normal |
|---|---|---|---|---|---|---|
| 2018-02-14 | 131,818 | 0,005 | 0,201 → 0,225 | 0,201 → 0,225 | 1,000 | 0,15 |
| 2018-02-15 | 167,168 | 0,004 | 0,043 → 0,047 | 0,043 → 0,047 | 0,987 | 0,03 |
| 2018-02-16 | 133,369 | 0,018 | 0,500 → 0,533 | 0,500 → 0,533 | 1,000 | 0,00 |
| 2018-02-20 | 1,410,306 | 0,010 | 0,076 → 0,075 | 0,076 → 0,075 | 1,000 | 0,02 |
| 2018-02-21 | 230,179 | 4,925 | 0,493 → 0,482 | 0,493 → 0,483 | 0,999 | 0,01 |
| 2018-02-22 | 213,245 | 0,002 | 0,000 → 0,000 | 0,000 → 0,000 | 0,492 | 0,01 |
| 2018-02-23 | 183,272 | 0,006 | 0,000 → 0,000 | 0,001 → 0,001 | 0,350 | 0,04 |
| 2018-02-28 | 117,581 | 0,061 | 0,019 → 0,037 | 0,133 → 0,097 | 0,089 | 31,63 |
| 2018-03-01 | 56,696 | 0,051 | 0,053 → 0,117 | 0,295 → 0,284 | 0,381 | 12,76 |
| 2018-03-02 | 160,927 | 0,058 | 0,255 → 0,326 | 0,255 → 0,348 | 0,937 | 0,20 |
