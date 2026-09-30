"""CICFlowMeter-V3 CSV başlıkları <-> PostgreSQL sütun adları ve özellik politikası.

Bu modül tek doğruluk kaynağıdır: şema (sql/01_schema.sql), içe aktarma ve
model özellik listesi buradaki adlarla tutarlı olmalıdır (tests/test_columns.py denetler).
"""
from __future__ import annotations

# (CSV başlığı, SQL sütunu) — dosyadaki sırayla. Kimlik sütunları yalnızca 20-02 dosyasında var.
IDENTITY_COLUMNS = [
    ("Flow ID", "flow_key"),
    ("Src IP", "src_ip"),
    ("Src Port", "src_port"),
    ("Dst IP", "dst_ip"),
]

FLOW_COLUMNS = [
    ("Dst Port", "dst_port"),
    ("Protocol", "protocol"),
    ("Timestamp", "ts"),
    ("Flow Duration", "flow_duration"),
    ("Tot Fwd Pkts", "tot_fwd_pkts"),
    ("Tot Bwd Pkts", "tot_bwd_pkts"),
    ("TotLen Fwd Pkts", "totlen_fwd_pkts"),
    ("TotLen Bwd Pkts", "totlen_bwd_pkts"),
    ("Fwd Pkt Len Max", "fwd_pkt_len_max"),
    ("Fwd Pkt Len Min", "fwd_pkt_len_min"),
    ("Fwd Pkt Len Mean", "fwd_pkt_len_mean"),
    ("Fwd Pkt Len Std", "fwd_pkt_len_std"),
    ("Bwd Pkt Len Max", "bwd_pkt_len_max"),
    ("Bwd Pkt Len Min", "bwd_pkt_len_min"),
    ("Bwd Pkt Len Mean", "bwd_pkt_len_mean"),
    ("Bwd Pkt Len Std", "bwd_pkt_len_std"),
    ("Flow Byts/s", "flow_byts_s"),
    ("Flow Pkts/s", "flow_pkts_s"),
    ("Flow IAT Mean", "flow_iat_mean"),
    ("Flow IAT Std", "flow_iat_std"),
    ("Flow IAT Max", "flow_iat_max"),
    ("Flow IAT Min", "flow_iat_min"),
    ("Fwd IAT Tot", "fwd_iat_tot"),
    ("Fwd IAT Mean", "fwd_iat_mean"),
    ("Fwd IAT Std", "fwd_iat_std"),
    ("Fwd IAT Max", "fwd_iat_max"),
    ("Fwd IAT Min", "fwd_iat_min"),
    ("Bwd IAT Tot", "bwd_iat_tot"),
    ("Bwd IAT Mean", "bwd_iat_mean"),
    ("Bwd IAT Std", "bwd_iat_std"),
    ("Bwd IAT Max", "bwd_iat_max"),
    ("Bwd IAT Min", "bwd_iat_min"),
    ("Fwd PSH Flags", "fwd_psh_flags"),
    ("Bwd PSH Flags", "bwd_psh_flags"),
    ("Fwd URG Flags", "fwd_urg_flags"),
    ("Bwd URG Flags", "bwd_urg_flags"),
    ("Fwd Header Len", "fwd_header_len"),
    ("Bwd Header Len", "bwd_header_len"),
    ("Fwd Pkts/s", "fwd_pkts_s"),
    ("Bwd Pkts/s", "bwd_pkts_s"),
    ("Pkt Len Min", "pkt_len_min"),
    ("Pkt Len Max", "pkt_len_max"),
    ("Pkt Len Mean", "pkt_len_mean"),
    ("Pkt Len Std", "pkt_len_std"),
    ("Pkt Len Var", "pkt_len_var"),
    ("FIN Flag Cnt", "fin_flag_cnt"),
    ("SYN Flag Cnt", "syn_flag_cnt"),
    ("RST Flag Cnt", "rst_flag_cnt"),
    ("PSH Flag Cnt", "psh_flag_cnt"),
    ("ACK Flag Cnt", "ack_flag_cnt"),
    ("URG Flag Cnt", "urg_flag_cnt"),
    ("CWE Flag Count", "cwe_flag_count"),
    ("ECE Flag Cnt", "ece_flag_cnt"),
    ("Down/Up Ratio", "down_up_ratio"),
    ("Pkt Size Avg", "pkt_size_avg"),
    ("Fwd Seg Size Avg", "fwd_seg_size_avg"),
    ("Bwd Seg Size Avg", "bwd_seg_size_avg"),
    ("Fwd Byts/b Avg", "fwd_byts_b_avg"),
    ("Fwd Pkts/b Avg", "fwd_pkts_b_avg"),
    ("Fwd Blk Rate Avg", "fwd_blk_rate_avg"),
    ("Bwd Byts/b Avg", "bwd_byts_b_avg"),
    ("Bwd Pkts/b Avg", "bwd_pkts_b_avg"),
    ("Bwd Blk Rate Avg", "bwd_blk_rate_avg"),
    ("Subflow Fwd Pkts", "subflow_fwd_pkts"),
    ("Subflow Fwd Byts", "subflow_fwd_byts"),
    ("Subflow Bwd Pkts", "subflow_bwd_pkts"),
    ("Subflow Bwd Byts", "subflow_bwd_byts"),
    ("Init Fwd Win Byts", "init_fwd_win_byts"),
    ("Init Bwd Win Byts", "init_bwd_win_byts"),
    ("Fwd Act Data Pkts", "fwd_act_data_pkts"),
    ("Fwd Seg Size Min", "fwd_seg_size_min"),
    ("Active Mean", "active_mean"),
    ("Active Std", "active_std"),
    ("Active Max", "active_max"),
    ("Active Min", "active_min"),
    ("Idle Mean", "idle_mean"),
    ("Idle Std", "idle_std"),
    ("Idle Max", "idle_max"),
    ("Idle Min", "idle_min"),
    ("Label", "label"),
]

CSV_TO_SQL = dict(IDENTITY_COLUMNS + FLOW_COLUMNS)

# Akış istatistikleri (dst_port, protocol, ts, label dışındaki sayısal alanlar).
NUMERIC_FLOW_COLUMNS = [s for _, s in FLOW_COLUMNS if s not in ("dst_port", "protocol", "ts", "label")]

# ---- Özellik politikası -------------------------------------------------------------
# Modele ASLA girmeyecek alanlar ve gerekçeleri. tests/test_leakage.py bu listeyi
# eğitimde kullanılan özellik listesine karşı denetler.
FORBIDDEN_FEATURES = {
    "label": "hedef değişkenin kendisi",
    "is_attack": "hedef değişkenin türevi",
    "ts": "mutlak zaman damgası; saldırı saat aralığını ezberletir (senaryo sızıntısı)",
    "end_ts": "mutlak zaman damgası",
    "capture_day": "hangi gün/dosyadan geldiği = senaryo kimliği",
    "source_file": "dosya adı saldırı senaryosunu ele verir",
    "line_no": "dosyadaki sıra; toplama sürecinin izi",
    "flow_id": "satır kimliği",
    "flow_key": "IP/port içeren kimlik",
    "src_ip": "saldırgan IP'si test ağına özgü; yalnızca 20-02 dosyasında var",
    "dst_ip": "kurban IP'si test ağına özgü; yalnızca 20-02 dosyasında var",
    "src_port": "geçici (ephemeral) port; genellenebilir bilgi taşımaz",
    "fv_hash": "sızıntı denetimi için özet; özellik değil",
    "split_temporal": "ayrım etiketi",
    "split_rand": "ayrım etiketi",
    "segment_id": "zaman bloğu / olay parçası kimliği",
}

# Canlıda elde edilebilir ama bu veri setinde test ağına özgü "kısayol" olma riski taşıyan
# alanlar. Ana modelde kullanılır; ablasyon deneyinde çıkarılarak bağımlılık ölçülür.
SHORTCUT_RISK_FEATURES = ["dst_port", "init_fwd_win_byts", "init_bwd_win_byts"]

# SQL'de (sql/20_features.sql) üretilen özellikler.
DERIVED_FEATURES = [
    "duration_s", "fwd_bytes_per_pkt", "bwd_bytes_per_pkt", "bwd_fwd_byte_ratio", "bwd_fwd_pkt_ratio",
    "fwd_payload_share", "log_total_bytes", "flow_iat_cv", "active_idle_ratio", "no_response",
    "zero_duration", "well_known_port",
]
WINDOW_FEATURES = [
    "w10_port_n", "w60_port_n", "w60_all_n", "w60_port_share", "w60_port_mean_fwd_pkts",
    "w60_port_mean_duration_s", "w60_port_noresp_share", "w60_port_rst_share",
]
# Aday model özellikleri (sabit sütunlar eğitim bölümünde ayrıca elenir).
CANDIDATE_FEATURES = ["dst_port", "protocol"] + NUMERIC_FLOW_COLUMNS + DERIVED_FEATURES + WINDOW_FEATURES
# Dışa aktarımda taşınan ama özellik OLMAYAN sütunlar (değerlendirme/gruplama için).
META_COLUMNS = ["flow_id", "capture_day", "label", "is_attack", "split_temporal", "split_rand",
                "fv_seen_in_train_temporal", "fv_seen_in_train_random"]
