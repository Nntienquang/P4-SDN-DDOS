# Tuần 7 — So sánh phương pháp phát hiện (GroupKFold theo run)

- Dataset: `data/uniflash_v01.csv` — 2610 window, 24 run, nhãn: {'normal': 1724, 'ddos': 593, 'flash': 293}
- Đánh giá: dự đoán out-of-fold, 5 fold, mỗi run chỉ ở 1 fold test (không rò rỉ giữa các window cùng run). ± = độ lệch chuẩn giữa fold.

| Phương pháp | Precision | Recall | F1 | FPR | **Flash-FPR** | Flash-FPR (S5) |
| --- | --- | --- | --- | --- | --- | --- |
| StaticThreshold | 0.700 | 0.944 ± 0.132 | 0.804 ± 0.146 | 0.119 | **0.761** ± 0.073 | 0.586 |
| EWMA | 0.525 | 1.000 ± 0.000 | 0.689 ± 0.127 | 0.266 | **0.949** ± 0.019 | 0.908 |
| LogisticRegression | 0.990 | 0.998 ± 0.002 | 0.994 ± 0.004 | 0.003 | **0.010** ± 0.010 | 0.035 |
| RandomForest | 0.990 | 0.998 ± 0.003 | 0.994 ± 0.005 | 0.003 | **0.010** ± 0.010 | 0.035 |

Ma trận nhầm lẫn RandomForest theo nhãn chi tiết:

```
dự đoán (1=DDoS)     0    1
nhãn thật                  
ddos                 1  592
flash              290    3
normal            1721    3
```

Feature quan trọng nhất (RF): syn_ack_ratio=0.35, packet_rate=0.20, source_entropy=0.12, byte_rate=0.10
