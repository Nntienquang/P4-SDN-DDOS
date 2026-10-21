# Sổ tay thực hành 11 tuần — sdn-p4-ddos

Mỗi tuần: **mục tiêu → lệnh chạy → kết quả mong đợi → cách tự kiểm tra →
lỗi thường gặp**. Code đã có sẵn trong repo; nhiệm vụ của nhóm là chạy, hiểu,
sửa và thu dữ liệu thật. Luân phiên Driver–Reviewer–Tester mỗi task.

**Quy ước:** lệnh bắt đầu bằng `$` chạy trên máy/VM; lệnh trong `mininet>` chạy
trong Mininet CLI; `h1 <cmd>` nghĩa là chạy `<cmd>` trên host h1.

> **Cập nhật theo góp ý giảng viên (bản 2):** đã bổ sung vào code — Jain's
> fairness index + Gini (`metrics/service_metrics.py`), bootstrap CI cho LSR và
> hiệu chỉnh đa so sánh Holm–Bonferroni (`analysis/aggregate.py`), growth_slope
> tính theo 3 window gần nhất (`controller/features.py`). Thêm việc: **đo năng
> lực BMv2 ngay tuần 3** (throughput/pps/latency + CPU/RAM của tiến trình BMv2),
> và một mục **"Threats to Validity"** trong báo cáo cuối.

Trước khi đụng testbed, ai cũng nên chạy được phần offline (không cần P4):
```bash
$ pip install -r requirements.txt
$ make test          # phải thấy: TẤT CẢ 27 kiểm tra PASS
$ make offline-demo  # phải in bảng so sánh model; EWMA có flash_fpr cao
```
Hiểu được vì sao EWMA/threshold có `flash_fpr` cao còn RF thì không — đó chính
là câu chuyện của đề tài (RQ2).

---

## Tuần 1 — Networking, Linux, SDN (E0)

**Mục tiêu:** quan sát được traffic, phân biệt Flash/DDoS ở mức khái niệm, chạy
Mininet mặc định.

**Lệnh:**
```bash
$ sudo mn --test pingall                 # Mininet cơ bản
$ sudo tcpdump -i any -w docs/w1_tcp.pcap 'tcp port 80' &
$ curl http://example-trong-lab/         # hoặc curl localhost nếu có server
# mở docs/w1_tcp.pcap bằng Wireshark, lọc: tcp.flags.syn==1
```

**Kết quả mong đợi:** `pingall` 0% dropped; pcap thấy đủ SYN → SYN-ACK → ACK.

**Tự kiểm tra (mỗi người trả lời không nhìn tài liệu):**
- Packet khác flow thế nào? Vì sao SYN/ACK ratio hữu ích nhưng không đủ?
- Flash Crowd khác DDoS ở mục đích và hành vi nào?

**Sản phẩm:** `docs/w1_tcp.pcap`, `docs/sdn_basics.png`, `docs/traffic_comparison.md`,
bắt đầu `docs/glossary.md` và literature matrix.

**Lỗi thường gặp:** `sudo mn -c` nếu Mininet treo từ lần trước.

---

## Tuần 2 — Mininet topology + đo đạc

**Mục tiêu:** chỉnh được topology qua config, đo năng lực nền của server.

**Lệnh:**
```bash
$ nano configs/topology.yaml      # chỉnh n_legit, n_attack, băng thông
$ python3 mininet/build_topo.py   # sinh topology.json + s1-runtime.json
$ python3 -c "import json;print(len(json.load(open('mininet/topology.json'))['hosts']),'hosts')"
```

**Kết quả mong đợi:** in ra số host khớp config (vd 13 hosts cho 8+3+probe+srv).

**Tự kiểm tra:** đổi `n_legit` thành 12 rồi build lại — số host có tăng không?
Vì sao Mininet không đại diện cho line-rate phần cứng?

**Sản phẩm:** `mininet/topology.json`, `configs/topology.yaml` đã chỉnh, số đo
throughput/`wrk` nền (ghi vào `experiments/week2_baseline.md`).

> Chưa có P4 ở tuần này — dùng switch mặc định của Mininet để làm quen topology.

---

## Tuần 3 — P4 + BMv2 forwarding (E1) · CHECKPOINT 1

**Mục tiêu:** biên dịch `telemetry.p4`, ping qua P4 switch.

**Lệnh:**
```bash
$ export P4_UTILS=$HOME/tutorials/utils
$ make build                      # p4c biên dịch -> build/telemetry.json + .p4info.txtpb
$ make run                        # dựng Mininet + BMv2, vào CLI
mininet> h1 ping -c3 srv
mininet> probe ping -c3 srv
```

**Kết quả mong đợi:** `make build` không lỗi; trong CLI, `h1 ping srv` thành công
(sau khi `make run` đã nạp forwarding từ s1-runtime.json).

**Tự kiểm tra:** mở `build/telemetry.json` — có thấy table `ipv4_lpm` không?
Đọc `p4/telemetry.p4`, chỉ ra parser → ingress → egress → deparser.

**Sản phẩm:** `docs/p4_pipeline.md`, pcap chứng minh forward, số đo năng lực BMv2.

**Lỗi thường gặp:**
- `p4c: command not found` → chưa cài toolchain; dùng P4 tutorial VM.
- `cannot bind port 50051` → còn switch cũ; `make clean` rồi chạy lại.
- p4c báo lỗi cú pháp theo phiên bản → sửa nhỏ theo thông báo; ghi lại vào
  `env/versions.txt` phiên bản p4c đang dùng.

---

## Tuần 4 — Counter + P4Runtime (E2) · CHECKPOINT 2

**Mục tiêu:** đọc counter real-time từ controller Python.

**Lệnh:** (terminal 1 giữ `make run`; terminal 2:)
```bash
$ sudo -E python3 controller/detector.py \
    --p4info build/telemetry.p4.p4info.txtpb \
    --bmv2 build/telemetry.json --poll 1.0 --no-mitigation \
    --out logs/realtime.csv
# terminal 3, trong mininet CLI: tạo traffic để thấy counter động
mininet> h1 curl -s srv >/dev/null
```

**Kết quả mong đợi:** detector in mỗi giây một dòng `pr=... syn/ack=... src=...`;
`logs/realtime.csv` có cột `packet_rate`, `byte_rate` tăng khi có traffic.

**Tự kiểm tra:** counter là tích lũy — vì sao phải lấy delta mới ra rate? Mở
`controller/features.py` xem công thức. Register đọc được không, hay rơi về
proxy số cổng (xem cảnh báo `[warn] đọc register lỗi`)?

**Sản phẩm:** `logs/realtime.csv` có timestamp + rate; ảnh biểu đồ packet_rate.

**Lỗi thường gặp:** đọc register lỗi → dùng fallback `simple_switch_CLI`; nếu
vẫn không được, `source_count` dùng proxy số cổng (ghi rõ trong báo cáo).

---

## Tuần 5 — Sinh traffic Normal/Flash/SYN/UDP (E3, E4)

**Mục tiêu:** tạo 4 loại traffic trong lab, có config và ground truth.

**Lệnh (chạy tự động cả kịch bản):**
```bash
$ make run SCENARIO=configs/scenarios/S2.yaml   # Flash only
$ make run SCENARIO=configs/scenarios/S3.yaml   # SYN flood
$ make run SCENARIO=configs/scenarios/S4.yaml   # UDP flood
$ cat logs/ground_truth.json
```

**Kết quả mong đợi:** `ground_truth.json` ghi các pha + `attack_ips`; log probe
(`logs/probe.csv`) cho thấy success rate giảm khi attack (với S3/S4) nhưng vẫn
cao với S2 (Flash hợp lệ).

**Tự kiểm tra:** vì sao Flash generator phải nhận response hợp lệ (không chỉ gửi)?
Mở `traffic/legit.py` xem ramp-up; mở `traffic/attack_lab.py` xem rate có trần.

**Sản phẩm:** 4 loại traffic chạy lặp được; `docs/threat_model.md`;
`docs/safety_checklist.md` ký đủ 3 người.

**An toàn:** mọi script gọi `traffic/safety.py` — đích phải là IP lab private.

**Lỗi thường gặp:** `hping3/iperf3 not found` → `sudo apt-get install hping3 iperf3`.

---

## Tuần 6 — Dataset, feature, threshold/EWMA (E5)

**Mục tiêu:** từ nhiều run tạo dataset có nhãn; chạy baseline threshold + EWMA.

**Lệnh:**
```bash
# chạy nhiều run mỗi scenario để có đủ window (ví dụ seed 0..4)
$ for s in 0 1 2 3 4; do \
    make run SCENARIO=configs/scenarios/S1.yaml; \
    cp logs/realtime.csv data/S1_seed$s.csv; done
# (ghép realtime + ground_truth thành dataset có nhãn — script gợi ý ở dưới)
```

**Kết quả mong đợi:** `data/uniflash_v01.csv` với cột theo `DATA_DICTIONARY.md`;
biểu đồ phân phối feature theo lớp cho thấy `syn_ack_ratio`, `source_entropy`
tách Flash khỏi DDoS.

**Tự kiểm tra:** data leakage xảy ra thế nào với window liền kề? Vì sao nhãn phải
lấy từ ground truth, không từ threshold đang đánh giá?

**Sản phẩm:** `data/uniflash_v01.csv`, `data/DATA_DICTIONARY.md`, Flash-FPR của B1.

> Ghép realtime.csv + ground_truth.json thành dataset có nhãn: dùng logic
> `label_at()` trong `analysis/compute_metrics.py` (gán nhãn theo pha). Nhóm
> viết một script nhỏ `ml/build_dataset.py` theo mẫu đó (bài tập tuần này).

---

## Tuần 7 — ML baseline (E6) · CHECKPOINT 3

**Mục tiêu:** train LR/RF/XGB, so với threshold/EWMA, chọn model MVP.

**Lệnh:**
```bash
$ python3 ml/train_eval.py --data data/uniflash_v01.csv --out experiments/week7
$ cat experiments/week7/model_compare.csv
```

**Kết quả mong đợi:** bảng Precision/Recall/F1/FPR/**Flash-FPR**; model lưu ở
`models/rf.pkl`, `models/lr.pkl`. Kỳ vọng: threshold/EWMA có Flash-FPR cao, RF
thấp hơn hẳn — bằng chứng cho RQ1, RQ2.

**Tự kiểm tra:** vì sao Flash-FPR quan trọng hơn accuracy tổng? Nếu XGBoost chỉ
hơn RF 0.3% nhưng nặng hơn nhiều, chọn gì cho online? (xem feature_importance.json)

**Sản phẩm:** `experiments/week7/model_compare.csv`, confusion/importance,
model `.pkl`, lý do chọn model + **khóa danh sách feature**.

**Lỗi thường gặp:** accuracy ≈ 100% → nghi leakage; kiểm tra có chia theo
`run_id` không (dataset.py đã làm, nhưng xác nhận dataset có cột run_id đa dạng).

---

## Tuần 8 — Tích hợp online (E7)

**Mục tiêu:** chạy model online, đo detection latency và CPU controller.

**Lệnh:**
```bash
# terminal 1: chạy scenario có attack
$ make run SCENARIO=configs/scenarios/S3.yaml
# terminal 2: detector dùng model, KHÔNG mitigation (chỉ phát hiện)
$ sudo -E python3 controller/detector.py \
    --p4info build/telemetry.p4.p4info.txtpb --bmv2 build/telemetry.json \
    --model models/rf.pkl --no-mitigation --out logs/realtime.csv
```

**Kết quả mong đợi:** detector in `DDoS` đúng trong pha attack; `logs/realtime.csv`
có cột `pred`, `cpu_pct`. So `realtime.csv` với `ground_truth.json` để tính
detection latency.

**Tự kiểm tra:** detection latency đo từ đâu tới đâu? Polling nhanh hơn (0.5s)
có trade-off gì về CPU? (chạy lại với `--poll 0.5` và `--poll 2.0`, so sánh)

**Sản phẩm:** `experiments/week8_latency.csv`, `experiments/week8_resource.csv`,
`analysis/polling_tradeoff.md`.

**Lỗi thường gặp:** feature online khác offline → đảm bảo cùng dùng
`features.compute_features` (detector đã làm vậy).

---

## Tuần 9 — Mitigation + LSR (E8) · CHECKPOINT 4

**Mục tiêu:** controller áp rule lên P4, đo LSR, giảm hại người dùng hợp lệ.

**Lệnh:**
```bash
# terminal 1: scenario chính
$ make run SCENARIO=configs/scenarios/S5.yaml
# terminal 2: detector có mitigation đầy đủ (B3)
$ sudo -E python3 controller/detector.py \
    --p4info build/telemetry.p4.p4info.txtpb --bmv2 build/telemetry.json \
    --model models/rf.pkl --feedback --out logs/realtime.csv
# sau khi xong, tính metric của run:
$ cp logs/{probe.csv,ground_truth.json} results/raw/S5_B3_seed0/ 2>/dev/null; \
  mkdir -p results/raw/S5_B3_seed0; cp logs/realtime.csv results/raw/S5_B3_seed0/
$ python3 analysis/compute_metrics.py --run results/raw/S5_B3_seed0
```

**Kết quả mong đợi:** detector lên mức L1/L2 trong pha attack; traffic attack tới
server giảm; **LSR vẫn cao** (người dùng Flash vẫn truy cập được). `compute_metrics`
in `lsr`, `ldr`, `detection_latency`.

**Tự kiểm tra:** LSR khác Recall thế nào? Vì sao temporary drop (có TTL) tốt hơn
chặn vĩnh viễn? Mở `mitigation/policy.py` xem hysteresis và cơ chế chặn theo
nguồn vs theo loại traffic.

**Sản phẩm:** `mitigation` chạy; log LSR/latency; sơ đồ state machine L0–L2.

**Lỗi thường gặp:** rule không có hiệu lực → kiểm tra `src_filter` entry ghi
thành công (xem `logs/p4runtime_s1.txt`).

---

## Tuần 10 — Thực nghiệm chính (E9) · CHECKPOINT 5

**Mục tiêu:** chạy ma trận S×B×seed, thu metric có khoảng tin cậy.

**Lệnh:**
```bash
$ sudo -E python3 experiments/run_matrix.py \
    --scenarios S1 S2 S3 S4 S5 --baselines B0 B1 B2 B3 --seeds 0 1 2 3 4
$ python3 analysis/aggregate.py --raw results/raw --out results/summary.csv
$ python3 analysis/aggregate.py --raw results/raw --compare S5 lsr B1 B3
```

**Kết quả mong đợi:** `results/summary.csv` có mean ± CI95 mỗi (scenario,baseline);
kiểm định in `p < 0.05` nếu B3 giữ LSR tốt hơn B1 trên S5 — đây là kết quả
trung tâm trả lời RQ4.

**Tự kiểm tra:** B0–B3 khác nhau ở biến nào? Vì sao phải chạy lặp? Một hệ F1 cao
hơn nhưng LSR thấp hơn có chắc tốt hơn không?

**Sản phẩm:** `results/summary.csv`, bảng raw, config/seed/version mỗi run.

**Lỗi thường gặp:** ma trận chạy lâu → chạy qua đêm; giảm `--seeds` hoặc bỏ S6
nếu thiếu thời gian (ghi rõ số run thật).

---

## Tuần 11 — Phân tích, báo cáo, demo

**Mục tiêu:** biến số liệu thành kết luận có bằng chứng; hoàn thiện repo + demo.

**Lệnh:**
```bash
$ python3 analysis/make_figures.py --summary results/summary.csv --scn S5
$ python3 analysis/make_figures.py --summary results/summary.csv --scn S3
# dashboard đơn giản: đọc results/summary.csv bằng Streamlit/Plotly (tùy chọn)
```

**Kết quả mong đợi:** `figures/lsr_by_baseline_S5.png`, `figures/tradeoff_S5.png`.
Mỗi RQ có một hình/bảng trả lời.

**Tự kiểm tra (câu hỏi hội đồng):** tại sao không dùng CDN/WAF? BMv2 chậm thì kết
quả có ý nghĩa không? Novelty thật sự là gì so với Jaqen/Euclid/SDN-DAD?
(gợi ý trả lời ở mục 20 của đề cương và README).

**Sản phẩm nộp:** báo cáo theo dàn ý (mục 4.2 tài liệu checklist), slide 10–12′,
video demo, repo có README + `env/versions.txt` + `results/`.

**Kịch bản demo:** Normal → Flash (không chặn) → Attack (chặn) → Flash+Attack
→ mitigation → so LSR với B1.

---

## Phụ lục — bản đồ file ↔ Definition of Done

| Tuần | File chính trong repo | Definition of Done |
| --- | --- | --- |
| 1 | (Mininet mặc định) | pingall + pcap + bảng so sánh |
| 2 | `configs/topology.yaml`, `mininet/build_topo.py` | topology build được, có config |
| 3 | `p4/telemetry.p4`, `Makefile` | ping qua P4 switch |
| 4 | `controller/read_stats.py`, `detector.py` | đọc counter real-time, CSV có rate |
| 5 | `traffic/*`, `configs/scenarios/*` | 4 traffic + ground_truth + safety |
| 6 | `controller/features.py`, `baseline/detectors.py` | dataset + Flash-FPR của B1 |
| 7 | `ml/train_eval.py` | bảng so sánh model, chọn model MVP |
| 8 | `controller/detector.py` (model) | online + detection latency + CPU |
| 9 | `mitigation/policy.py`, `mitigator.py` | rule thật + LSR |
| 10 | `experiments/run_matrix.py` | ma trận + CI95 |
| 11 | `analysis/*` | hình theo 4 trục + báo cáo |
