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

**Lệnh (chạy tự động cả kịch bản, mỗi lệnh ~2–2,5 phút):**
```bash
$ make run SCENARIO=configs/scenarios/S2.yaml   # Flash only
$ make run SCENARIO=configs/scenarios/S3.yaml   # SYN flood
$ make run SCENARIO=configs/scenarios/S4.yaml   # UDP flood
$ cat logs/ground_truth.json
```

**Công cụ (đã đổi so với bản đầu):**
- SYN flood và UDP flood đều dùng **hping3**, bọc bằng `timeout <giây>` để tấn
  công dừng đúng hết pha. (iperf3 bị bỏ cho UDP: một `iperf3 -s` chỉ nhận 1
  client một lúc nên 3 host tấn công cùng lúc không chạy được.)
- Server là `traffic/web_server.py` (listen backlog 128), không phải
  `python3 -m http.server` (backlog chỉ 5, quá mong manh).
- Probe chạy **open-loop**: bắn đúng 5 request/giây, không chờ request trước.
- Mỗi host hợp lệ ghi log từng request vào `logs/legit/<host>_p<pha>.csv`.

**Kết quả mong đợi:** `ground_truth.json` ghi các pha + `attack_ips` + `t0`
(epoch); `logs/probe.csv` có cột `wall`; tỉ lệ `ok` gần 0 trong pha tấn công
S3/S4, gần 1 với S2.

> **Kết quả đã đo (B0, không phòng thủ):** LSR trong pha tấn công 1,5% (S3) và
> 2,9% (S4); Flash Crowd S2 vẫn được phục vụ 100%. Hình: `figures/tuan05/`.

**Tự kiểm tra:** vì sao Flash generator phải nhận response hợp lệ (không chỉ
gửi)? Vì sao probe closed-loop làm LSR bị thổi phồng? (xem
`docs/NHAT_KY_SUA_LOI_tuan4_11.md`, lỗi B6.)

**Sản phẩm:** 4 loại traffic chạy lặp được; `docs/safety_checklist.md` ký đủ.

**An toàn:** mọi script gọi `traffic/safety.py` — đích phải là IP lab private.

**Lỗi thường gặp:**
- `hping3 not found` → `sudo apt-get install hping3`.
- probe toàn `ok=0` cả ở S1 → mạng không thông: kiểm tra ARP tĩnh trong
  `mininet/topology.json` (chạy lại `make topo`).

---

## Tuần 6 — Dataset, feature, threshold/EWMA (E5)

**Mục tiêu:** từ nhiều run tạo dataset có nhãn; chạy baseline threshold + EWMA.

**Lệnh:**
```bash
$ make collect        # S1..S6 × B0 × seed 0..3 = 24 run, ~60 phút, cần sudo
$ make dataset        # gom results/dataset_raw/* -> data/uniflash_v01.csv
$ make week6          # threshold + EWMA -> experiments/week6/baseline_report.md
```

**Gán nhãn:** `ml/build_dataset.py` lấy nhãn từ `ground_truth.json` theo thời
điểm `wall − t0` (cột `wall` do detector ghi). Không dùng `elapsed`, vì detector
khởi động lệch vài giây so với scenario. Window sát ranh giới pha được đánh dấu
`transition=1` và loại khi train. Thứ tự ưu tiên khi chồng pha: ddos > flash > normal.

> **Kết quả đã đo:** 2 754 window (2 610 sau khi loại transition). Threshold
> (515 gói/s) Flash-FPR **0,708**; EWMA **0,938**; cả hai Recall = 1.
> Flash Crowd có packet_rate trung vị 1 343 gói/s, cao hơn DDoS (1 247).
> Hình: `figures/tuan06/`.

**Tự kiểm tra:** data leakage xảy ra thế nào với window liền kề? Vì sao nhãn
phải lấy từ ground truth, không từ threshold đang đánh giá? Vì sao seed thu dữ
liệu (0–3) phải khác seed đánh giá (10–14)?

**Sản phẩm:** `data/uniflash_v01.csv`, `data/DATA_DICTIONARY.md`,
`experiments/week6/baseline_report.md`.

---

## Tuần 7 — ML baseline (E6) · CHECKPOINT 3

**Mục tiêu:** train LR/RF, so với threshold/EWMA, chọn model MVP.

**Lệnh:**
```bash
$ make week7          # = python3 ml/train_eval.py --data data/uniflash_v01.csv --out experiments/week7
$ cat experiments/week7/model_report.md
```

**Cách đánh giá:** GroupKFold 5 fold **theo run_id**, dự đoán out-of-fold (mỗi
window được dự đoán bởi model chưa thấy run của nó). Model triển khai
(`models/rf.pkl`) được train lại trên toàn bộ dataset sau khi đánh giá.

> **Kết quả đã đo:** RandomForest Recall 0,998, Flash-FPR **0,010**; LR ngang
> RF; threshold 0,761, EWMA 0,949. Feature quan trọng nhất: `syn_ack_ratio`
> (0,35). Hình: `figures/tuan07/`.

**Tự kiểm tra:** vì sao Flash-FPR quan trọng hơn accuracy tổng? LR ngang RF
nói lên điều gì về dữ liệu lab? (gợi ý: gần như tách tuyến tính theo
syn_ack_ratio — một hạn chế cần nêu.)

**Sản phẩm:** `experiments/week7/{model_compare.csv, model_report.md,
cv_folds.csv, rf_confusion_by_label.csv, feature_importance.json}`, `models/rf.pkl`.

**Lỗi thường gặp:** accuracy ≈ 100% → nghi leakage; kiểm tra đã chia theo `run_id`.
`Bỏ qua XGBoost` là bình thường (XGBoost tùy chọn).

---

## Tuần 8 — Tích hợp online (E7)

**Mục tiêu:** chạy model online, đo detection latency và CPU controller.

**Lệnh:**
```bash
# terminal 1: chạy scenario có attack
$ make run SCENARIO=configs/scenarios/S5.yaml
# terminal 2 (ngay khi terminal 1 in "[run_net] server HTTP:80 ..."):
$ sudo -E python3 controller/detector.py \
    --p4info build/telemetry.p4.p4info.txtpb --bmv2 build/telemetry.json \
    --model models/rf.pkl --mitigation none --out logs/online_s5.csv
```

**Kết quả mong đợi:** detector in `ok` trong pha Flash (30–50s) và `DDoS` trong
pha tấn công (50–110s). `realtime.csv` có `pred`, `infer_ms`, `cpu_pct`, `wall`.

> **Kết quả đã đo (ma trận):** trễ phát hiện 1,0–1,7 s; suy luận ~16 ms/window;
> CPU detector ~2,2%. Hình: `figures/tuan08/`.

**Tự kiểm tra:** detection latency đo từ đâu tới đâu? Polling nhanh hơn có
trade-off gì? Vì sao threshold "phát hiện" S5 nhanh hơn (0,6 s)? (gợi ý: nó đã
báo động sẵn từ pha Flash — đó là báo nhầm, không phải phát hiện nhanh.)

**Lỗi thường gặp:** feature online khác offline → đảm bảo cùng dùng
`features.compute_features` (detector đã làm vậy).

---

## Tuần 9 — Mitigation + LSR (E8) · CHECKPOINT 4

**Mục tiêu:** controller áp rule lên P4, đo LSR, giảm hại người dùng hợp lệ.

**Ba chế độ mitigation (`--mitigation`):**
- `none`: chỉ ghi log (B0).
- `coarse`: rate-limit THÔ mọi gói SYN/UDP chung hạn mức 300 gói/s (B1, B2).
- `targeted`: chặn THEO CỔNG VÀO có hành vi tấn công (B3). Cổng bị nghi khi
  SYN ≥ 50/s và ACK/(SYN+1) < 0,5, hoặc UDP ≥ 100/s. L1 = meter 50 gói/s cho
  cổng đó, L2 = drop. `--feedback` đọc LSR từ `logs/probe.csv` để leo/nới mức.

**Lệnh:**
```bash
# terminal 1
$ make run SCENARIO=configs/scenarios/S5.yaml
# terminal 2 (B3)
$ sudo -E python3 controller/detector.py \
    --p4info build/telemetry.p4.p4info.txtpb --bmv2 build/telemetry.json \
    --model models/rf.pkl --mitigation targeted --feedback --out logs/mitig_s5.csv
```
Muốn có đủ log để tính metric một run, chạy qua `run_matrix.py` thay vì tay:
```bash
$ sudo env "PATH=$PATH" python3 experiments/run_matrix.py \
    --scenarios S5 --baselines B3 --seeds 99 --out results/demo
$ python3 analysis/compute_metrics.py --run results/demo/S5_B3_seed99
```

**Kết quả mong đợi:** detector lên `L1-ratelimit` rồi `L2-drop`, in
`chặn:a1,a2,a3`; không host h1–h8 nào bị chặn.

> **Kết quả đã đo:** rule đầu tiên sau 2,1–2,5 s; trên mọi run B3 không host hợp
> lệ nào bị chặn. Dịch vụ hồi phục không tức thời: các kết nối half-open trên
> server cần vài giây mới hết. Hình: `figures/tuan09/`.

**Tự kiểm tra:** vì sao chặn theo cổng vào chứ không theo IP nguồn? Vì sao
counter đếm TRƯỚC bảng lọc? Rate-limit 50 gói/s mỗi cổng có đủ cứu server
trước SYN flood không? (không — backlog vẫn bị lấp dần, nên cần L2.)

**Lỗi thường gặp:** rule không có hiệu lực → xem bảng:
`echo "table_dump MyIngress.port_filter" | simple_switch_CLI`.

---

## Tuần 10 — Thực nghiệm chính (E9) · CHECKPOINT 5

**Mục tiêu:** chạy ma trận S×B×seed, thu metric có khoảng tin cậy.

**Lệnh:**
```bash
$ make matrix                                  # S1..S6 × B0..B3 × seed 10..12, ~3 giờ
$ make matrix SCNS="S3 S4 S5" SEEDS="13 14"   # thêm n=5 cho kịch bản tấn công, ~1 giờ
$ make analyze                                 # summary.csv + stats.csv + RESULTS.md
```
`run_matrix.py --resume` bỏ qua run đã xong; run hỏng có file `FAILED` và được
chạy lại ở lần resume sau.

**Quan trọng — chống máy ngủ:** tắt chế độ ngủ của **máy thật** (VMware/laptop)
trước khi chạy dài. Hai lần máy thật suspend máy ảo đã làm hỏng 2 run;
`systemd-inhibit` trong máy ảo không chặn được việc này.

> **Kết quả đã đo:** LSR trong pha tấn công của B3: 98,7% (S3), 99,8% (S4),
> 57,9% (S5), so với 1,5–2,9% (B0) và 19–37% (B1/B2). 18/18 so sánh B3 với
> baseline khác tách hoàn toàn; Welch-Holm p < 0,001. Xem `results/RESULTS.md`.

**Tự kiểm tra:** B0–B3 khác nhau ở biến nào? Vì sao đơn vị lặp là run chứ không
phải window? Vì sao Mann-Whitney sau Holm không xuống dưới 0,05 dù hai nhóm tách
hoàn toàn? (n=5 → p nhỏ nhất 0,0079, nhân 9 phép so sánh.)

**Sản phẩm:** `results/summary.csv`, `results/stats.csv`, `results/RESULTS.md`.

---

## Tuần 11 — Phân tích, báo cáo, demo

**Mục tiêu:** biến số liệu thành kết luận có bằng chứng; hoàn thiện repo + demo.

**Lệnh:**
```bash
$ make figures        # figures/fig*.png + figures/tuan04..tuan11/ + figures/README.md
```

**Kết quả mong đợi:** 22 hình theo tuần kèm chú thích trong `figures/README.md`;
mỗi RQ có một hình/bảng trả lời (bảng tóm tắt ở `docs/BAO_CAO_KET_QUA.md`).

**Tự kiểm tra (câu hỏi hội đồng):** xem `docs/HUONG_DAN_ON_TAP.md`.

**Sản phẩm nộp:** báo cáo theo mẫu trường (kết quả lấy từ
`docs/BAO_CAO_KET_QUA.md`), slide, video demo, repo.

**Kịch bản demo (~5 phút, chạy B3 ở S5 như tuần 9):** Flash bắt đầu → detector
vẫn `ok` → tấn công bắt đầu → `DDoS` → `L2-drop chặn:a1,a2,a3` → tấn công dừng
→ rule tự gỡ về L0. Rồi mở `figures/tuan11/timeline_S5_all.png` để so với B0–B2.

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
| 9 | `mitigation/policy.py`, `mitigator.py`, `p4/telemetry.p4` (port_filter) | rule thật + LSR |
| 10 | `experiments/run_matrix.py`, `analysis/aggregate.py` | ma trận + CI95 + kiểm định |
| 11 | `analysis/make_figures.py`, `weekly_figures.py` | hình theo tuần + báo cáo |
