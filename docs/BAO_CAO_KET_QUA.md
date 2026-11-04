# Báo cáo kết quả — Phòng thủ DDoS thích ứng trên SDN/P4 có phân biệt Flash Crowd

> Tổng hợp tuần 4 → 11. Số liệu đo trên testbed Mininet + BMv2 (P4 tutorial VM
> Ubuntu 24.04, 4 vCPU, 7.8 GB RAM), thực hiện ngày 03/11/2026. Mọi con số
> trong file này sinh tự động từ log và có thể tái lập bằng các lệnh ở mục 7.
> Bảng đầy đủ: [`results/RESULTS.md`](../results/RESULTS.md). Hình theo tuần:
> [`figures/README.md`](../figures/README.md). Lỗi đã sửa:
> [`NHAT_KY_SUA_LOI_tuan4_11.md`](NHAT_KY_SUA_LOI_tuan4_11.md).

## 1. Tóm tắt

| Câu hỏi nghiên cứu | Kết quả | Bằng chứng |
| --- | --- | --- |
| **RQ1** Đọc telemetry từ data plane P4 theo thời gian thực có khả thi? | Có. Controller đọc counter qua P4Runtime mỗi ~1.13s; CPU detector ≈ 2% | Hình 4.1, 4.2; Bảng C |
| **RQ2** Phát hiện theo volume (threshold/EWMA) có báo nhầm Flash Crowd? | Có, rất nặng: Flash-FPR 0.76 (threshold) và 0.95 (EWMA) offline; 0.98 online ở S2 | Hình 6.1, 6.3; Bảng 7.1; Bảng B |
| **RQ3** ML dùng feature hành vi có giảm báo nhầm mà vẫn bắt được tấn công? | Có: RandomForest Flash-FPR 0.010 offline, **0.0** online ở S2 và S5; Recall 1.0 | Hình 7.1, 8.1; Bảng 7.1, B, C |
| **RQ4** Mitigation chọn lọc có giữ dịch vụ cho người dùng hợp lệ? | Có. LSR trong pha tấn công: **98.7% / 99.8% / 57.9%** (S3/S4/S5) so với 1.5–2.9% khi không phòng thủ và 19–37% khi rate-limit thô. Với IP nguồn giả mạo: **89.6%** so với ~2% | Hình 10.1, 10.2, 11.1; Bảng A, D; mục 7.4 |

**Phát hiện quan trọng nhất:** chỉ cải thiện bộ phát hiện (B1 → B2) **không** cải
thiện trải nghiệm người dùng khi bị tấn công: LSR của B2 ≈ B1 ở cả S3, S4, S5
(Bảng A). Phần lớn lợi ích đến từ việc **chặn đúng nguồn** (B2 → B3): LSR tăng
thêm +0.39 đến +0.74. Phát hiện tốt là điều kiện cần (không báo nhầm, ở Bảng B);
mitigation chọn lọc mới là điều kiện đủ để giữ dịch vụ.

## 2. Hệ thống và thiết kế thí nghiệm

**Testbed.** 1 switch BMv2 (`simple_switch_grpc`), 13 host: `srv` (web server,
backlog 128), `probe` (đo LSR, 5 req/s open-loop), `h1–h8` (người dùng hợp lệ),
`a1–a3` (tấn công, chỉ trong lab). Link server 10 Mbps là nút cổ chai.

**Data plane (`p4/telemetry.p4`).** Counter toàn cục và theo cổng vào
(total/SYN/ACK/UDP), bitmap ước lượng số nguồn, 3 bảng mitigation:
`port_filter` (theo cổng vào), `src_filter` (theo src IP), `proto_filter` (theo
loại gói); meter đơn vị gói.

**Feature (8, theo window ~1s):** packet_rate, byte_rate, syn_rate, udp_rate,
syn_ack_ratio, source_count, source_entropy, growth_slope.

**Kịch bản:** S1 Normal · S2 Flash Crowd · S3 SYN flood · S4 UDP flood · S5 Flash
+ SYN + UDP đồng thời · S6 tải nền thay đổi. Cường độ biến thiên ±30% theo seed.

**Baseline:**

| | Phát hiện | Mitigation |
| --- | --- | --- |
| B0 | — | không |
| B1 | static threshold packet_rate (học 10 window đầu) | rate-limit thô SYN/UDP, hạn mức chung 300 pps |
| B2 | RandomForest | rate-limit thô (như B1) |
| B3 | RandomForest | chặn theo cổng vào (L1 50 pps/cổng → L2 drop) + feedback LSR |

**Dữ liệu tách bạch:** dataset train lấy từ **seed 0–3** (24 run, chỉ B0); ma trận
đánh giá dùng **seed 10–14** chưa từng thấy (96 run: S1, S2, S6 × 3 seed; S3, S4, S5
× 5 seed; × 4 baseline). Thí nghiệm bổ sung S3S (SYN flood với IP nguồn giả
mạo, mục 7.4): 12 run. Tổng: 132 run hợp lệ, khoảng 5,5 giờ chạy thực tế.

## 3. Tuần 4–5 — Telemetry real-time và traffic có nhãn

- Controller đọc 2 counter (wildcard) và 1 register mỗi chu kỳ; chu kỳ thực tế
  trung vị 1.13s (Hình 4.2). Khi SYN flood bắt đầu, syn_rate tăng vọt và
  ACK/(SYN+1) tụt từ ~9 về ~0.3 trong 1–2 window (Hình 4.1).
- Bốn loại traffic tái lập được. **Flash Crowd (S2) có packet_rate trung vị 1 343
  pps, cao hơn DDoS (1 247 pps)** (Hình 5.1, 6.1). Đây chính là tình huống
  đề tài đặt ra: volume không phân biệt được người thật với tấn công.
- Khi không phòng thủ, tấn công làm dịch vụ sập: LSR trong pha tấn công chỉ còn
  1.5% (S3) và 2.9% (S4) (Hình 5.2; Bảng A, dòng B0).

## 4. Tuần 6 — Dataset và baseline

Dataset `data/uniflash_v01.csv`: **2 754 window** từ 24 run (2 610 sau khi loại
window sát ranh giới pha): 1 724 normal, 293 flash, 593 ddos (Hình 6.2).

| Detector (chia theo run) | Recall DDoS | Precision | FPR normal | **Flash-FPR** |
| --- | --- | --- | --- | --- |
| Static threshold (515 pps) | 1.000 | 0.769 | 0.017 | **0.708** |
| EWMA | 1.000 | 0.628 | 0.137 | **0.938** |

Nguồn: `experiments/week6/baseline_report.md`, Hình 6.3. Ngưỡng tĩnh nằm dưới cả
phân bố Flash lẫn DDoS (Hình 6.1).

## 5. Tuần 7 — Máy học phân biệt Flash vs DDoS (Bảng 7.1)

Đánh giá **out-of-fold, GroupKFold 5 fold theo run_id** (không có run nào vừa ở
train vừa ở test):

| Phương pháp | Precision | Recall | F1 | FPR | **Flash-FPR** | Flash-FPR (S5) |
| --- | --- | --- | --- | --- | --- | --- |
| StaticThreshold | 0.700 | 0.944 | 0.804 | 0.119 | **0.761** | 0.586 |
| EWMA | 0.525 | 1.000 | 0.689 | 0.266 | **0.949** | 0.908 |
| LogisticRegression | 0.990 | 0.998 | 0.994 | 0.003 | **0.010** | 0.034 |
| RandomForest | 0.990 | 0.998 | 0.994 | 0.003 | **0.010** | 0.034 |

- RandomForest được chọn để triển khai. Ma trận nhầm lẫn: 290/293 window Flash
  được giữ là lành tính, 592/593 window DDoS bị bắt (Hình 7.3).
- Feature quan trọng nhất: **syn_ack_ratio (0.35)**, packet_rate (0.20),
  source_entropy (0.12) (Hình 7.2). Model dựa vào *hành vi* (hoàn tất handshake).
- LR đạt ngang RF: bài toán trên testbed này gần như tách tuyến tính theo
  syn_ack_ratio. Đây là một giới hạn, xem mục 8.

## 6. Tuần 8–9 — Phát hiện online và mitigation

- **Online:** RandomForest báo DDoS sau 1.0–1.7s kể từ lúc tấn công bắt đầu (Bảng
  C), và im lặng suốt pha Flash ở S5. Threshold báo động từ khi Flash bắt đầu
  (Hình 8.1). Thời gian suy luận ~16 ms/window, CPU detector ~2.2%.
- **Mitigation chọn lọc (B3):** rule đầu tiên được ghi sau 2.1–2.5s kể từ lúc tấn
  công bắt đầu (Bảng C), lên L2 drop sau thêm 1–2 window, chặn đúng **a1, a2, a3**.
  Trên toàn bộ run B3, **không host hợp lệ nào (h1–h8) bị chặn** (Hình 9.2).
- **Hồi phục không tức thời:** ở S3/S4, dịch vụ gần như trở về 100% sau khi chặn.
  Ở S5, B3 chỉ giữ được ~58% vì Flash Crowd đồng thời đã làm server quá tải
  (ngay cả khi không có tấn công, chỉ ~40% request Flash thành công ở S5-B0)
  (Hình 9.1).

## 7. Tuần 10–11 — Thí nghiệm chính và thống kê

### 7.1 Trục User — giữ dịch vụ khi bị tấn công (Bảng A, Hình 10.1, 10.2)

LSR probe **trong pha tấn công**, mean ± CI95 (n = 5 run):

| | S3 SYN flood | S4 UDP flood | S5 Flash+DDoS |
| --- | --- | --- | --- |
| B0 | 1.5% ± 0.5 | 2.9% ± 1.1 | 1.6% ± 0.8 |
| B1 | 35.9% ± 5.8 | 21.9% ± 5.1 | 20.7% ± 5.1 |
| B2 | 37.2% ± 3.1 | 25.8% ± 4.1 | 19.2% ± 3.9 |
| **B3** | **98.7% ± 0.7** | **99.8% ± 0.6** | **57.9% ± 10.2** |

Thước đo độc lập với feedback, là tỉ lệ thành công của **mọi client h1–h8**
(không đưa vào vòng phản hồi của B3), cho cùng kết luận: B3 đạt 94.7% / 100% /
51.1% so với 17–36% của B1/B2.

### 7.2 Báo nhầm và Flash Crowd (Bảng B, Hình 10.3, 10.4)

| | S2 Flash-FPR | S5 Flash-FPR | S6 FPR (nền đổi) | S5 user Flash OK |
| --- | --- | --- | --- | --- |
| B1 | **98.0%** | **92.5%** | **35.7%** | 49.3% |
| B2 | 0.0% | 0.9% | 0.0% | 48.9% |
| B3 | 0.0% | 0.0% | 0.0% | **70.7%** |

- Threshold học ngưỡng từ tải lúc đầu nên báo nhầm cả khi **tải nền tăng tự
  nhiên** (S6), không chỉ khi có Flash Crowd.
- Ở S2, báo nhầm của B1 **không gây hại**: Flash Crowd chỉ tạo ~120 SYN/s, dưới hạn
  mức chung 300 pps (user Flash OK = 100%). Thiệt hại xuất hiện khi báo nhầm
  trùng với tấn công (S5), lúc người dùng thật và attacker phải chia chung hạn mức.
- S1 (Normal): mọi baseline có FPR = 0, LSR = 100%.

### 7.3 Kiểm định (Bảng D, `results/stats.csv`)

Đơn vị lặp = run. Với LSR trong pha tấn công và tỉ lệ thành công của client hợp
lệ, **B3 tốt hơn B0, B1 và B2 ở cả 3 kịch bản tấn công**:
- Hai nhóm **tách hoàn toàn**: mọi run B3 tốt hơn mọi run của baseline kia.
- Welch t-test hiệu chỉnh Holm: **p < 0.001** cho cả 18 so sánh.
- CI95 bootstrap của hiệu không chứa 0, ví dụ S5 B3−B2: +0.39 [0.32, 0.46].

Mann-Whitney sau hiệu chỉnh Holm chỉ đạt p = 0.07. Đó là giới hạn toán học với
n = 5 mỗi nhóm (p nhỏ nhất có thể có = 0.0079; nhân 9 phép so sánh), chứ không
phải dấu hiệu thiếu khác biệt. Muốn MW đạt p < 0.05 sau Holm cần n ≥ 7 run mỗi
nhóm.

### 7.4 Thí nghiệm bổ sung — IP nguồn giả mạo (S3S)

Kiểm chứng lập luận "chặn theo cổng vào vẫn đúng khi IP nguồn không tin được".
S3S giống S3 nhưng 3 host tấn công dùng `hping3 --rand-source`: mỗi gói SYN mang
một IP nguồn ngẫu nhiên. Phản hồi tới các IP giả bị switch drop (không có route),
nên mọi traffic vẫn nằm trong Mininet. Chạy B0–B3 × seed 10–12 (n = 3).

| | LSR pha tấn công | Client hợp lệ OK | Trễ mitigation |
| --- | --- | --- | --- |
| B0 | 1.7% ± 2.9 | 3.2% ± 2.3 | — |
| B1 | 2.1% ± 2.4 | 5.3% ± 2.6 | 2.6 s |
| B2 | 2.1% ± 1.0 | 4.5% ± 3.6 | 3.3 s |
| **B3** | **89.6% ± 28.4** (76.3 / 96.0 / 96.3) | **86.1% ± 24.4** | 3.1 s |

- **Bộ phát hiện vẫn đúng** dù gặp dữ liệu chưa từng thấy lúc train: số nguồn ước
  lượng nhảy lên ~580–955 (S3 thường: ~8), nhưng RandomForest vẫn đạt Recall 1.0
  và FPR 0, chỉ chậm hơn 0.6–0.9 s (trễ phát hiện 1.9–2.0 s so với 1.0–1.5 s ở S3).
- **B3 vẫn chặn đúng a1, a2, a3** ở cả 3 run, không chặn host hợp lệ nào: cổng
  vào không bị ảnh hưởng bởi việc giả mạo IP.
- **Rate-limit thô (B1, B2) mất tác dụng hoàn toàn** khi IP bị giả mạo: chỉ ~2%,
  so với ~36% ở S3 thường. Giải thích khả dĩ (chưa đo trực tiếp): với IP giả,
  SYN-ACK của server không tới được ai nên không có RST trả về; các kết nối
  half-open tồn đọng tới hết timeout, nên hàng đợi của server bị lấp đầy ngay cả
  với 300 SYN/s lọt qua hạn mức.
- Kiểm định (họ Holm riêng cho thí nghiệm bổ sung): B3 tách hoàn toàn khỏi
  B0/B1/B2 ở cả 6 so sánh; Welch-Holm p ≤ 0.016. Với n = 3, Mann-Whitney không
  thể xuống dưới 0.10.
- Một run (seed 10) chỉ đạt 76%, nên khoảng tin cậy rộng. Cần thêm seed để thu hẹp.

## 8. Threats to Validity

**Nội tại**
- *BMv2 là switch phần mềm:* xử lý tối đa ~1.5–2k gói/s trên VM. Cường độ tấn
  công ở mức vài nghìn pps, không phải line-rate. Kết quả về **độ chính xác** và
  **tính chọn lọc** có thể chuyển sang phần cứng; kết quả về **thông lượng/độ trễ**
  thì không.
- *Probe vừa là tín hiệu feedback vừa là thước đo LSR* cho B3. Để giảm thiên lệch,
  báo cáo thêm `user_sr_attack` (client h1–h8 không được feed back); kết luận
  không đổi.
- *Rò rỉ seed:* train (seed 0–3) và đánh giá (seed 10–14) dùng cùng file kịch bản,
  chỉ khác cường độ ±30%. Model chưa được thử với kiểu tấn công hoặc topology mới.
- *Máy ảo bị suspend 2 lần* giữa thí nghiệm (do máy chủ). 2 run bị ảnh hưởng đã
  được phát hiện qua khoảng trống trong log, loại bỏ và chạy lại.

**Ngoại tại**
- *Giả mạo IP mới thử với SYN flood, 3 run* (mục 7.4); chưa thử UDP flood giả
  mạo, cũng chưa thử kẻ tấn công giả mạo **MAC** hoặc nhiều host sau cùng một cổng.
- *Chặn theo cổng vào giả định mỗi cổng ≈ một host* (switch biên). Ở switch lõi,
  một cổng gom nhiều người dùng; chặn cổng sẽ gây hại tập thể, cần kết hợp IP
  hoặc flow.
- *Chỉ 2 loại tấn công volumetric* (SYN, UDP). Chưa thử tấn công tầng ứng dụng
  (HTTP flood hoàn tất handshake), loại sẽ đánh lừa feature syn_ack_ratio.
- *Flash Crowd mô phỏng:* client Python, think time mũ, ramp tam giác; chưa dùng
  trace thật.
- *LR ≈ RF:* dữ liệu lab tách gần tuyến tính, nên chưa chứng minh được lợi ích của
  model phi tuyến.

**Cấu trúc**
- LSR đo với timeout 2s; request OK nhưng > 1s vẫn tính là thành công (`lsr_sla`
  trong summary đo riêng với SLA 1s).

## 9. Tái lập

```bash
cd ~/P4-SDN-DDOS && export P4_UTILS=$HOME/tutorials/utils
make test                     # 67 unit test
make collect                  # tuần 5–6: 24 run B0, ~60 phút
make dataset week6            # tuần 6
make week7                    # tuần 7: train + models/rf.pkl
make matrix                   # tuần 8–10: 72 run, ~3 giờ
make matrix SCNS="S3 S4 S5" SEEDS="13 14"   # thêm n cho S3–S5, ~1 giờ
make matrix SCNS="S3S"                      # bổ sung IP giả mạo, ~30 phút
make analyze figures          # tuần 10–11: bảng + kiểm định + hình
```

**Trước khi chạy dài:** tắt chế độ ngủ của **máy thật** (VMware/laptop), vì
`systemd-inhibit` trong máy ảo không chặn được việc host suspend.

## 10. Danh mục hình

Xem [`figures/README.md`](../figures/README.md), có chú thích gợi ý cho từng hình.
Đánh số trong file này: Hình *T.k* = hình thứ *k* của tuần *T* trong README đó.
