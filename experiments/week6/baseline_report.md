# Tuần 6 — Kết quả baseline (threshold vs EWMA)

- Dataset: `data/uniflash_v01.csv` (2610 window sau khi loại transition)
- Feature dùng: `packet_rate` | chia theo run_id, test_frac=0.30, seed=42
- Run train: S1_B0_seed0, S1_B0_seed1, S1_B0_seed2, S1_B0_seed3, S2_B0_seed0, S2_B0_seed2, S2_B0_seed3, S3_B0_seed0, S3_B0_seed1, S3_B0_seed3, S4_B0_seed0, S4_B0_seed2, S5_B0_seed0, S5_B0_seed3, S6_B0_seed0, S6_B0_seed1, S6_B0_seed2
- Run test : S2_B0_seed1, S3_B0_seed2, S4_B0_seed1, S4_B0_seed3, S5_B0_seed1, S5_B0_seed2, S6_B0_seed3

| Detector | Recall DDoS | Precision | F1 | FPR normal | **Flash-FPR** |
| --- | --- | --- | --- | --- | --- |
| Static threshold (B1) | 1.000 | 0.769 | 0.870 | 0.017 | **0.708** |
| EWMA (adaptive) | 1.000 | 0.628 | 0.772 | 0.137 | **0.938** |

Ngưỡng tĩnh fit được: **515.4 pkt/s** (phân vị 99 × 1.20).

**Đọc kết quả:** Flash-FPR cao = baseline báo nhầm flash crowd thành tấn công. Đây là điểm yếu tuần 7 (máy học) phải khắc phục: giữ Recall DDoS cao mà Flash-FPR thấp.
