# RUNBOOK Tuần 4 → 11 — chạy từng bước + kiến thức

> Sổ tay "cầm tay chỉ việc" cho nửa sau đề tài. Mỗi tuần: **mục tiêu → kiến thức
> cần → lệnh copy-paste → kết quả mong đợi → chụp gì → checkpoint → nếu lỗi**.
> Dùng chung với `docs/HANDBOOK_newbie_de_hieu.md` (giải thích thuật ngữ từ số 0).
>
> 🟢 = chạy trên **máy ảo P4**. 🔴 = máy thật/laptop. Tất cả lệnh chạy trong
> thư mục `~/P4-SDN-DDOS`, môi trường `(p4dev-python-venv)` đang bật.

> **Cập nhật 03/11/2026 — đọc trước:** testbed đã được sửa nhiều lỗi khiến kết
> quả cũ không dùng được (xem `docs/NHAT_KY_SUA_LOI_tuan4_11.md`). Cách chạy
> nhanh nhất cho tuần 5→11 giờ là các lệnh `make` dưới đây; phần hướng dẫn chi
> tiết từng tuần bên dưới vẫn đúng về kiến thức, chỉ khác tên tham số detector.
>
> | Tuần | Lệnh | Thời gian | Kết quả |
> | --- | --- | --- | --- |
> | 5–6 thu dữ liệu | `make collect` | ~60 phút | `results/dataset_raw/S*_B0_seed{0..3}` |
> | 6 dataset + baseline | `make dataset && make week6` | vài giây | `data/uniflash_v01.csv`, `experiments/week6/baseline_report.md` |
> | 7 train | `make week7` | ~1 phút | `models/rf.pkl`, `experiments/week7/model_report.md` |
> | 8–10 ma trận online | `make matrix` (+ `make matrix SCNS="S3 S4 S5" SEEDS="13 14"`) | ~4 giờ | `results/raw/*` |
> | 10 thống kê | `make analyze` | vài giây | `results/summary.csv`, `results/stats.csv`, `results/RESULTS.md` |
> | 11 hình | `make figures` | vài giây | `figures/fig*.png` |
>
> Tham số detector mới: `--mitigation none|coarse|targeted` và `--feedback`.
> `--no-mitigation` vẫn dùng được (= `none`). Baseline:
> B0 = không phòng thủ · B1 = threshold + rate-limit thô SYN/UDP ·
> B2 = RandomForest + rate-limit thô · B3 = RandomForest + chặn theo cổng vào + feedback LSR.
> Kết quả + báo cáo: `docs/BAO_CAO_KET_QUA.md`.

## 0. Hai dạng lệnh — nhớ kỹ để khỏi lỗi môi trường

Trong đề tài có 2 loại script:

**(A) Cần quyền root + thư viện trong venv** (dựng mạng, chạy ma trận) — dùng:
```bash
sudo env "PATH=$PATH" python3 <script> ...
```
> Vì sao: `sudo` thường xoá PATH của venv → Python mất `mininet`, `grpc`. Thêm
> `env "PATH=$PATH"` giữ lại PATH của venv cho cả tiến trình con. Đây là lý do
> trước đây gặp lỗi `No module named 'mininet.log'`.
> `make run` đã xử lý sẵn; chỉ khi chạy tay script mới cần dạng này.

**(B) Không cần root** (đọc counter, train, phân tích) — chạy thẳng:
```bash
python3 <script> ...
```

**Mỗi lần mở máy ảo, chạy 2 dòng chuẩn bị:**
```bash
cd ~/P4-SDN-DDOS
export P4_UTILS=$HOME/tutorials/utils
```

---

# TUẦN 4 — Controller đọc counter real-time (CHECKPOINT 2)

**Mục tiêu:** viết chương trình điều khiển (controller) đứng ngoài, **đọc số đếm
gói từ switch P4 mỗi giây**, biến thành tốc độ (packet_rate...) và ghi ra CSV.

**Kiến thức cần nắm:**
- **Controller** = "bộ não" chạy trên máy, KHÔNG nằm trong switch. Nó nối tới
  switch qua **P4Runtime** (cổng gRPC `127.0.0.1:50051`).
- **Counter tích luỹ:** switch chỉ đếm cộng dồn (vd tổng 10.000 gói). Muốn biết
  "bao nhiêu gói/giây" phải lấy **hiệu 2 lần đọc** chia cho thời gian. Đây là việc
  controller làm trong `controller/features.py`.
- **poll:** chu kỳ đọc (ở đây 1 giây/lần). Đọc dày → phát hiện sớm nhưng tốn CPU.
- File `controller/detector.py` làm vòng lặp: đọc → tính feature → (chưa chặn) →
  ghi CSV.

**Chạy (🟢 cần 2 cửa sổ Terminal):**

*Terminal A — dựng mạng, giữ nguyên:*
```bash
cd ~/P4-SDN-DDOS
make run
```
Chờ tới khi thấy dấu nhắc `mininet>`. **Để yên cửa sổ này.**

*Terminal B — chạy controller đọc counter (không cần sudo):*
```bash
cd ~/P4-SDN-DDOS
export P4_UTILS=$HOME/tutorials/utils
python3 controller/detector.py \
  --p4info build/telemetry.p4.p4info.txtpb \
  --bmv2   build/telemetry.json \
  --poll 1.0 --no-mitigation \
  --out logs/realtime.csv
```

*Quay lại Terminal A — tạo traffic để thấy số nhảy:*
```
mininet> h1 ping -c 20 srv
mininet> h1 curl -s -o /dev/null http://10.0.0.100/
```

**Kết quả mong đợi / chụp gì:**
- Terminal B in mỗi giây một dòng, ví dụ:
  ```
  t=   5.0 pr=    42.0 syn/ack= 0.98 src=  2.0 -> ok   [L0_MONITOR]
  ```
  Khi bạn ping/curl ở Terminal A, cột `pr=` (packet_rate) **tăng lên** rồi lắng xuống.
- File `logs/realtime.csv` có cột `packet_rate`, `syn_ack_ratio`, ...
- **Chụp:** Terminal B lúc số đang nhảy + mở `logs/realtime.csv` (`head logs/realtime.csv`).

**✅ CHECKPOINT 2:** controller đọc được số liệu switch theo thời gian thực và ghi
CSV. Dừng Terminal B bằng **Ctrl+C**, Terminal A gõ `exit`.

**Nếu lỗi:**
- `No module named 'p4runtime_lib'` → chưa `export P4_UTILS=$HOME/tutorials/utils`.
- `failed to connect ... 50051` → Terminal A chưa lên `mininet>`, chờ thêm 8–10s.
- Số `pr=` luôn = 0 → bạn chưa tạo traffic ở Terminal A (ping/curl).

---

# TUẦN 5 — Sinh 4 loại traffic có nhãn trong lab

**Mục tiêu:** chạy được 4 "kịch bản" traffic: Normal, Flash Crowd, SYN flood,
UDP flood — mỗi lần tự ghi `ground_truth.json` (nhãn thật).

**Kiến thức cần nắm:**
- **scenario (kịch bản):** file `configs/scenarios/S*.yaml` mô tả "pha nào chạy
  lúc nào, trên host nào". `run_net.py` đọc nó, tự bơm traffic, tự ghi nhãn.
  - S1 = normal, S2 = flash, S3 = syn flood, S4 = udp flood, S5 = flash + ddos.
- **probe:** một "người dùng mẫu" chạy suốt để đo dịch vụ còn sống không (→ LSR),
  tự ghi `logs/probe.csv`.
- **ground_truth.json:** nhãn thật + danh sách IP tấn công, do generator ghi,
  KHÔNG suy từ detector → dùng để chấm điểm công bằng.
- **An toàn:** mọi traffic tấn công chỉ chạy trong Mininet cô lập; `traffic/
  safety.py` chặn IP ngoài dải lab. Ký `docs/safety_checklist.md` trước khi chạy.

**Chạy (🟢 — mỗi scenario là một lệnh, chạy lần lượt):**
```bash
cd ~/P4-SDN-DDOS
make run SCENARIO=configs/scenarios/S1.yaml   # normal
make run SCENARIO=configs/scenarios/S2.yaml   # flash
make run SCENARIO=configs/scenarios/S3.yaml   # syn flood
make run SCENARIO=configs/scenarios/S4.yaml   # udp flood
make run SCENARIO=configs/scenarios/S5.yaml   # flash + ddos
```
Mỗi lệnh tự chạy ~2 phút rồi thoát, in `[scenario:Sx] xong -> logs/ground_truth.json`.

**Mẹo máy yếu:** chạy **từng scenario một**, đóng Wireshark/Firefox khi chạy. Nếu
muốn nhanh, rút `duration` trong file yaml xuống 60–90 (giây).

**Kết quả mong đợi / chụp gì:**
- Sau mỗi lần: `cat logs/ground_truth.json` thấy đúng các pha.
- `tail logs/probe.csv` — cột `ok`: S1/S2 nhiều `True` (dịch vụ sống), S3/S4 nhiều
  `False` (bị tấn công làm rớt).
- **Chụp:** dòng kết thúc scenario + vài dòng `probe.csv` của một scenario tấn công.

**✅ Dấu hiệu xong:** chạy trơn cả 5 scenario, mỗi loại ra `ground_truth.json` +
`probe.csv`. Hiểu được vì sao success rate tụt khi S3/S4 mà vẫn cao khi S2 (flash).

**Nếu lỗi:**
- `hping3: not found` → `sudo apt install -y hping3`.
- Scenario chạy nhưng probe toàn `False` cả ở S1 → server chưa lên; chạy lại,
  chờ mạng ổn trước khi bơm traffic (đã có sẵn delay trong code).

---

# TUẦN 6 — Dataset có nhãn + baseline threshold/EWMA

> Tuần 6 đã có hướng dẫn chi tiết trong `HANDBOOK_newbie_de_hieu.md`. Tóm tắt lệnh:

**Thu dữ liệu + gán nhãn:** cần chạy scenario **cùng lúc có detector** để vừa có
`realtime.csv` (feature) vừa có `ground_truth.json` (nhãn). Cách gọn nhất:

*Terminal A:* `make run SCENARIO=configs/scenarios/S2.yaml`
*Terminal B* (ngay khi mạng lên):
```bash
python3 controller/detector.py --p4info build/telemetry.p4.p4info.txtpb \
  --bmv2 build/telemetry.json --poll 1.0 --no-mitigation --out logs/realtime.csv
```
Khi A xong → Ctrl+C B → gom ngay vào dataset:
```bash
python3 ml/build_dataset.py --runs logs --run-id run1_S2 \
    --out data/uniflash_v01.csv --append
```
Lặp cho S1/S3/S4/S5 (đổi `--run-id`). **Cần có cả flash lẫn ddos** mới đo Flash-FPR.

**Đánh giá baseline (chạy đâu cũng được, kể cả 🔴 laptop):**
```bash
make week6      # = python3 baseline/eval_baseline.py --data data/uniflash_v01.csv --out experiments/week6
```

**Kết quả mong đợi:** `experiments/week6/baseline_report.md` có bảng với cột
**Flash-FPR cao** cho threshold & EWMA. **Chụp** bảng đó.

**✅ Dấu hiệu xong:** `data/uniflash_v01.csv` đủ nhãn + có con số Flash-FPR.

---

# TUẦN 7 — Máy học phân biệt Flash vs DDoS (CHECKPOINT 3)

**Mục tiêu:** train Random Forest / Logistic Regression trên dataset, so với
baseline, **chứng minh ML giảm Flash-FPR** mà vẫn bắt được tấn công.

**Kiến thức cần nắm:**
- **Machine Learning:** cho máy xem nhiều ví dụ có nhãn → nó học quy luật đoán.
- **Chia theo run_id (chống data leakage):** các window cùng một lần chạy rất
  giống nhau; nếu trộn ngẫu nhiên, model "học thuộc" run → điểm ảo. `ml/dataset.py`
  chia theo `run_id` bằng GroupShuffleSplit.
- **Precision / Recall / F1 / FPR / Flash-FPR:** xem lại glossary. Với đề tài,
  **Flash-FPR thấp** quan trọng hơn accuracy tổng.

**Chạy (🟢 hoặc 🔴 — chỉ xử lý CSV, không cần testbed):**
```bash
cd ~/P4-SDN-DDOS
python3 ml/train_eval.py --data data/uniflash_v01.csv --out experiments/week7
cat experiments/week7/model_compare.csv
```
→ Lưu model vào `models/rf.pkl`, `models/lr.pkl`. In bảng so sánh các phương pháp.

**Kết quả mong đợi / chụp gì:**
- Bảng `model_compare.csv`: RandomForest có **Flash-FPR thấp hơn hẳn** threshold/EWMA,
  Recall DDoS vẫn cao.
- **Chụp:** bảng so sánh + báo "đã lưu model -> models/*.pkl".

**✅ CHECKPOINT 3:** có bảng so sánh, chọn RandomForest, khoá bộ feature. Đây là
"trái tim" khoa học của đề tài.

**Nếu lỗi:**
- `No module named sklearn` → `pip install -r requirements.txt`.
- `Bỏ qua XGBoost` → bình thường (XGBoost tuỳ chọn): `pip install xgboost` nếu muốn.
- Flash-FPR của RF vẫn cao → dataset flash quá ít; thu thêm scenario S2.

---

# TUẦN 8 — Phát hiện ONLINE bằng model

**Mục tiêu:** cho model vừa train chạy **thời gian thực** khi đang bị tấn công;
đo **độ trễ phát hiện** (detection latency) và CPU.

**Kiến thức cần nắm:**
- **online vs offline:** online = quyết định ngay trong lúc traffic chảy (khác
  train/eval là đọc file có sẵn).
- **detection latency:** từ lúc tấn công bắt đầu → lúc model kêu "DDoS" lần đầu.
- Cùng hàm `compute_features()` với lúc train → không lệch phân phối.

**Chạy (🟢 2 Terminal):**

*Terminal A:* `make run SCENARIO=configs/scenarios/S3.yaml` (có pha tấn công)
*Terminal B* (ngay khi mạng lên):
```bash
python3 controller/detector.py --p4info build/telemetry.p4.p4info.txtpb \
  --bmv2 build/telemetry.json --model models/rf.pkl \
  --poll 1.0 --no-mitigation --out logs/online_s3.csv
```

**Kết quả mong đợi / chụp gì:**
- Terminal B in `-> ok` trong pha normal, chuyển sang `-> DDoS` khi tấn công bắt đầu.
- **Chụp:** đoạn chuyển từ `ok` sang `DDoS` (thấy rõ model bắt được).

**✅ Dấu hiệu xong:** model chạy real-time, phát hiện đúng pha tấn công, ghi log.

**Nếu lỗi:** `model không tồn tại` → chạy Tuần 7 trước để sinh `models/rf.pkl`.

---

# TUẦN 9 — Chặn mà không hại người thật (CHECKPOINT 4)

**Mục tiêu:** controller **thật sự chặn** tấn công (bật `--feedback`), rồi đo
**LSR** — người dùng hợp lệ có còn dùng được dịch vụ không.

**Kiến thức cần nắm:**
- **Mitigation nhiều tầng:** L0 theo dõi → L1 giới hạn tốc độ → L2 chặn tạm (có
  thời hạn TTL). Xem `mitigation/policy.py`.
- **LSR (Legitimate Success Rate):** % request người thật thành công. **Thước đo
  quan trọng nhất** của đề tài — chặn tấn công mà LSR vẫn cao mới là giỏi.
- **hysteresis:** chỉ đổi mức sau vài window → tránh bật/tắt liên tục.
- **IP giả mạo:** khi không tin được IP nguồn → chặn theo **loại traffic** thay vì
  theo từng IP.

**Chạy (🟢 2 Terminal):**

*Terminal A:* `make run SCENARIO=configs/scenarios/S5.yaml` (flash + ddos — ca khó nhất)
*Terminal B* (ngay khi mạng lên):
```bash
python3 controller/detector.py --p4info build/telemetry.p4.p4info.txtpb \
  --bmv2 build/telemetry.json --model models/rf.pkl \
  --poll 1.0 --mitigation targeted --feedback --out logs/mitig_s5.csv
```

**Kết quả mong đợi / chụp gì:**
- Terminal B hiện mức nhảy lên `L1_RATELIMIT` / `L2_BLOCK` khi tấn công, rồi hạ
  xuống khi dịu.
- `tail logs/probe.csv` — tỉ lệ `ok=True` **vẫn cao** dù đang bị tấn công (nhờ chặn
  đúng kẻ xấu, tha người thật).
- **Chụp:** Terminal B lúc lên mức chặn + `probe.csv` cho thấy LSR còn cao.

**✅ CHECKPOINT 4:** hệ thống chặn được tấn công **và** giữ LSR cao. Đây là bằng
chứng chính cho câu hỏi nghiên cứu "giảm thiểu tác động tới người dùng hợp lệ".

**Nếu lỗi:** mức chặn không bao giờ lên → model chưa báo DDoS; kiểm tra lại Tuần 8.

---

# TUẦN 10 — Thí nghiệm chính + thống kê (CHECKPOINT 5)

**Mục tiêu:** chạy **ma trận** Scenario × Baseline × seed (lặp nhiều lần), tính số
trung bình **có khoảng tin cậy** để kết luận chắc chắn, không phải may rủi.

**Kiến thức cần nắm:**
- **Baseline B0–B3:** B0 không phòng thủ, B1 threshold, B2 model, B3 model+feedback.
  So sánh để thấy đóng góp từng tầng.
- **Lặp nhiều seed:** mỗi cấu hình chạy ≥3–5 lần vì có ngẫu nhiên.
- **CI 95% + kiểm định (Mann-Whitney, bootstrap, Holm):** chứng minh "B3 tốt hơn
  B1" là thật (p < 0.05), không do tình cờ.

**Chạy (🟢 — chạy lâu, nên để qua giờ nghỉ; máy yếu thì giảm seed/scenario):**
```bash
cd ~/P4-SDN-DDOS
export P4_UTILS=$HOME/tutorials/utils
# Bản đầy đủ (lâu):
sudo env "PATH=$PATH" python3 experiments/run_matrix.py \
  --scenarios S1 S2 S3 S4 S5 --baselines B0 B1 B2 B3 --seeds 0 1 2

# Bản nhẹ cho máy yếu (chạy trước để kiểm tra, ~ ít phút):
sudo env "PATH=$PATH" python3 experiments/run_matrix.py \
  --scenarios S5 --baselines B1 B3 --seeds 0 1
```
Rồi tổng hợp + kiểm định (không cần root):
```bash
python3 analysis/aggregate.py --raw results/raw --out results/summary.csv
python3 analysis/aggregate.py --raw results/raw --compare S5 lsr B1 B3
```

**Kết quả mong đợi / chụp gì:**
- `results/summary.csv`: mỗi dòng là mean ± CI95 của một (scenario, baseline).
- Lệnh `--compare` in `p < 0.05` nếu B3 giữ LSR tốt hơn B1 có ý nghĩa thống kê.
- **Chụp:** `summary.csv` và dòng kết luận kiểm định.

**✅ CHECKPOINT 5:** có bảng số liệu tổng hợp + kiểm định → đủ bằng chứng viết báo cáo.

**Nếu lỗi:**
- `No module named 'mininet'` khi chạy run_matrix → đã dùng đúng dạng
  `sudo env "PATH=$PATH" python3` chưa? (xem mục 0).
- Một vài run lỗi → không sao, aggregate bỏ qua run hỏng; chạy bù vài seed.
- Quá lâu/treo → giảm xuống 1 scenario, 2 baseline, 2 seed như bản nhẹ ở trên.

---

# TUẦN 11 — Phân tích, hình vẽ, báo cáo, demo

**Mục tiêu:** biến số liệu thành **hình + kết luận có bằng chứng**; dựng kịch bản demo.

**Kiến thức cần nắm:**
- **claim–evidence:** mỗi câu kết luận trỏ tới một bảng/hình cụ thể.
- **Threats to Validity:** nêu hạn chế (BMv2 là switch phần mềm, traffic lab, chỉ
  2 loại tấn công) → làm bài trung thực, đáng tin hơn.

**Chạy (🟢/🔴 — chỉ xử lý số liệu):**
```bash
# Xem metric của 1 run cụ thể (để hiểu/đối chiếu):
python3 analysis/compute_metrics.py --run results/raw/S5_B3_seed0

# Vẽ hình cho báo cáo:
python3 analysis/make_figures.py --summary results/summary.csv --scn S5 --outdir figures
```

**Kết quả mong đợi / chụp gì:**
- Thư mục `figures/` có biểu đồ (LSR theo baseline, v.v.).
- **Chụp/đính:** các hình trong `figures/` vào báo cáo.

**Kịch bản demo (trình bày):**
1. Normal (S1) → dịch vụ chạy mượt.
2. Flash (S2) → tải cao nhưng hệ thống **không chặn nhầm** (LSR cao).
3. Attack (S3/S4) → hệ thống **chặn**, tấn công giảm.
4. Flash + Attack (S5) với B3 → chặn kẻ xấu, giữ người thật (LSR cao).
5. So LSR giữa B0 (không phòng thủ) và B3 → thấy rõ giá trị đề tài.

**✅ Hoàn tất đề tài:** có hình, bảng, kết luận, demo. Soát `docs/HANDBOOK.md` mục
"nộp" cho đủ sản phẩm.

---

# PHỤ LỤC — Bảng tra nhanh "tuần nào chạy gì"

| Tuần | Lệnh chính | Checkpoint | Cần gì trước đó |
| --- | --- | --- | --- |
| 4 | `make run` + `detector.py --no-mitigation` | CP2 đọc counter | P4 build xong (T3) |
| 5 | `make run SCENARIO=S1..S5` | 5 scenario chạy được | T4 |
| 6 | `build_dataset.py` + `make week6` | dataset + Flash-FPR | T5 |
| 7 | `train_eval.py` | CP3 model thắng baseline | dataset (T6) |
| 8 | `detector.py --model rf.pkl --no-mitigation` | phát hiện online | model (T7) |
| 9 | `detector.py --model rf.pkl --feedback` | CP4 chặn + LSR cao | model (T7) |
| 10 | `run_matrix.py` + `aggregate.py` | CP5 số liệu + kiểm định | model (T7) |
| 11 | `make_figures.py` + demo | báo cáo + demo | summary (T10) |

**Quy tắc vàng khi gặp lỗi:** đọc **dòng cuối** thông báo lỗi; phần lớn là
**thiếu công cụ** (`apt install`) hoặc **sai môi trường** (xem mục 0). Kẹt quá 1
buổi → chụp màn hình gửi hỏi, đừng mò cả ngày.
