"""Arayüzde gösterilecek özellik adları ve kaynakları (açıklama panelinde kullanılır)."""
from __future__ import annotations

from .columns import DERIVED_FEATURES, WINDOW_FEATURES

LABELS = {
    "dst_port": "hedef port",
    "protocol": "protokol",
    "flow_duration": "akış süresi (µs)",
    "tot_fwd_pkts": "ileri yön paket sayısı",
    "tot_bwd_pkts": "geri yön paket sayısı",
    "totlen_fwd_pkts": "ileri yön toplam bayt",
    "totlen_bwd_pkts": "geri yön toplam bayt",
    "fwd_pkt_len_max": "ileri paket boyu, en büyük",
    "fwd_pkt_len_mean": "ileri paket boyu, ortalama",
    "bwd_pkt_len_max": "geri paket boyu, en büyük",
    "bwd_pkt_len_mean": "geri paket boyu, ortalama",
    "flow_byts_s": "akış hızı (bayt/s)",
    "flow_pkts_s": "akış hızı (paket/s)",
    "flow_iat_mean": "paketler arası süre, ortalama",
    "flow_iat_max": "paketler arası süre, en büyük",
    "flow_iat_min": "paketler arası süre, en küçük",
    "fwd_iat_tot": "ileri paketler arası süre, toplam",
    "fwd_iat_min": "ileri paketler arası süre, en küçük",
    "bwd_iat_min": "geri paketler arası süre, en küçük",
    "fwd_header_len": "ileri başlık baytı",
    "bwd_header_len": "geri başlık baytı",
    "fwd_pkts_s": "ileri paket/s",
    "bwd_pkts_s": "geri paket/s",
    "pkt_len_max": "paket boyu, en büyük",
    "pkt_len_mean": "paket boyu, ortalama",
    "fin_flag_cnt": "FIN bayrağı",
    "syn_flag_cnt": "SYN bayrağı",
    "rst_flag_cnt": "RST bayrağı",
    "psh_flag_cnt": "PSH bayrağı",
    "ack_flag_cnt": "ACK bayrağı",
    "urg_flag_cnt": "URG bayrağı",
    "down_up_ratio": "indirme/yükleme oranı",
    "pkt_size_avg": "ortalama paket boyu",
    "init_fwd_win_byts": "ilk TCP penceresi (ileri)",
    "init_bwd_win_byts": "ilk TCP penceresi (geri)",
    "fwd_act_data_pkts": "veri taşıyan ileri paket",
    "fwd_seg_size_min": "ileri segment boyu, en küçük",
    "idle_mean": "boşta kalma, ortalama",
    "active_mean": "aktif süre, ortalama",
    # SQL satır düzeyi
    "duration_s": "akış süresi (s)",
    "fwd_bytes_per_pkt": "ileri bayt / paket",
    "bwd_bytes_per_pkt": "geri bayt / paket",
    "bwd_fwd_byte_ratio": "geri / ileri bayt oranı",
    "bwd_fwd_pkt_ratio": "geri / ileri paket oranı",
    "fwd_payload_share": "ileri yük payı",
    "log_total_bytes": "log(toplam bayt)",
    "flow_iat_cv": "paket aralığı değişkenliği",
    "active_idle_ratio": "aktif / boşta oranı",
    "no_response": "yanıtsız akış",
    "zero_duration": "sıfır süreli akış",
    "well_known_port": "iyi bilinen port (<1024)",
    # SQL zaman penceresi
    "w10_port_n": "aynı porta son 10 s'de biten akış",
    "w60_port_n": "aynı porta son 60 s'de biten akış",
    "w60_all_n": "tüm portlara son 60 s'de biten akış",
    "w60_port_share": "portun son 60 s'deki payı",
    "w60_port_mean_fwd_pkts": "porttaki akışların ort. ileri paketi (60 s)",
    "w60_port_mean_duration_s": "porttaki akışların ort. süresi (60 s)",
    "w60_port_noresp_share": "porttaki yanıtsız akış payı (60 s)",
    "w60_port_rst_share": "porttaki RST payı (60 s)",
}


def label(name: str) -> str:
    return LABELS.get(name, name)


def source(name: str) -> str:
    if name in WINDOW_FEATURES:
        return "SQL pencere"
    if name in DERIVED_FEATURES:
        return "SQL türetilmiş"
    return "CICFlowMeter"
