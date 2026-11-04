# Sổ tay thực hành 11 tuần — BẢN HOÀN THIỆN CHO NGƯỜI MỚI

> Viết cho người **chưa biết gì về mạng/P4**. Mọi thuật ngữ đều giải thích bằng
> lời thường ngày. Làm từ từ, hiểu tới đâu làm tới đó. Gặp từ lạ → tra **Bảng
> thuật ngữ** ở cuối. Gặp lỗi → xem **Phụ lục: Lỗi thường gặp & cách sửa**.

## Đọc trước (3 phút)

**Đề tài làm gì?** Dựng một mạng giả trong máy ảo, cho "người dùng thật" và "kẻ
tấn công" cùng gửi dữ liệu tới một web server. Hệ thống của nhóm đứng giữa, quan
sát, **phân biệt người thật với tấn công**, rồi chặn kẻ tấn công mà **không chặn
nhầm người thật**.

**Ký hiệu:**
- `$ lệnh` = gõ vào **Terminal** (cửa sổ dòng lệnh).
- `mininet>` = gõ khi đang ở trong Mininet.
- 🟢 = làm trong máy ảo. 🔴 = làm ở máy thật (VMware).

**4 quy tắc sống còn cho newbie:**
1. Một tuần xong khi **chạy ra kết quả**, không phải khi "đã đọc hiểu".
2. Gặp từ lạ → tra Bảng thuật ngữ. Gặp lỗi → tra Phụ lục lỗi.
3. Kẹt quá 1 buổi → hỏi ngay, đừng mò cả ngày.
4. Mỗi việc xong → **chụp màn hình** lưu cho báo cáo, và ghi 1 dòng vào
   `experiments/LOG.md`.

---

# PHẦN 0 — CHUẨN BỊ MÔI TRƯỜNG (BẮT BUỘC, làm trước mọi tuần)

> ⚠️ Đây là phần newbie hay vấp nhất. Đọc kỹ, làm đúng để khỏi mất cả ngày.

## 0.1. Dùng MÁY ẢO P4 CÓ SẴN — đừng tự biên dịch

**KHÔNG tự cài p4c/BMv2 trên Ubuntu mới (nhất là 26.04)** — sẽ lỗi liên miên
(bản vá hỏng, phiên bản lệch), mất cả buổi. Thay vào đó tải máy ảo đã cài sẵn
**p4c + BMv2 + Mininet** trên Ubuntu 24.04:

**Bước 1 — Tải máy ảo** (🔴 trình duyệt máy thật), chọn theo máy:
- Windows / Intel / AMD: máy ảo P4 bản **x86_64**
- Mac chip Apple (M1/M2/M3): bản **aarch64**

(Link lấy ở: repo `jafingerhut/p4-guide` → `bin/README-install-troubleshooting.md`,
bảng "VM images". Hoặc hỏi người đã tải trong nhóm gửi lại. File ~5GB.)

**Bước 2 — Import vào VMware** (🔴 máy thật): File → Open → chọn file `.ova` →
Import. Đăng nhập: user **`p4`** / mật khẩu **`p4`**.

**Bước 3 — Tăng tài nguyên** (🔴 VMware → Edit settings): RAM **8GB**, CPU **4**,
ổ **≥60GB** (nếu máy thật đủ).

**⚠️ KHI MÁY ẢO HỎI NÂNG CẤP LÊN 26.04 → BẤM "Don't Upgrade".** Nâng là hỏng P4.
Tắt nhắc nhở cho đỡ phiền:
```bash
sudo sed -i 's/^Prompt=.*/Prompt=never/' /etc/update-manager/release-upgrades
```

## 0.2. Lấy code của nhóm về (🟢 máy ảo)
```bash
cd ~
git clone https://github.com/Nntienquang/P4-SDN-DDOS.git
cd P4-SDN-DDOS
```

## 0.3. Cài vài công cụ còn thiếu (🟢 máy ảo)

Máy ảo P4 có sẵn p4c/BMv2/Mininet nhưng **thiếu vài công cụ phụ**. Cài thêm:
```bash
sudo apt update
sudo apt install -y iperf3 hping3 wrk
```
- `iperf3` = đo tốc độ mạng (dùng tuần 3 đo năng lực BMv2).
- `hping3` = sinh gói SYN (dùng tuần 5 làm SYN flood trong lab).
- `wrk` = tạo tải HTTP (đo sức chứa server).

## 0.4. Khai báo Git + token (🟢 máy ảo, làm 1 lần mỗi máy)
```bash
git config --global user.name "Ten That Cua Minh"
git config --global user.email "email-github@gmail.com"
git config --global credential.helper store    # để khỏi nhập token mỗi lần
```
Khi `git push` hỏi: Username = tài khoản GitHub, Password = **Personal Access
Token** (chuỗi `ghp_...`, tạo ở GitHub → Settings → Developer settings → Personal
access tokens → tick `repo`). **KHÔNG dùng mật khẩu GitHub** — GitHub không nhận.

## 0.5. Lưu ý môi trường Python (QUAN TRỌNG)

Máy ảo P4 tự bật một **môi trường ảo Python** tên `(p4dev-python-venv)` (thấy ở
đầu dòng Terminal). Mininet, grpc, protobuf đều nằm trong đó. **Giữ nó bật**,
đừng `deactivate`. Code của nhóm (Makefile) đã xử lý để chạy đúng với venv này.

## 0.6. Chạy thử xác nhận môi trường OK
```bash
pip install -r requirements.txt    # thư viện cho phần phân tích (nếu thiếu)
make test                          # phải thấy: TẤT CẢ 38 kiểm tra PASS
```
Ra "67 PASS" = phần não hệ thống (phát hiện/chặn/đo) chạy đúng. Chưa cần hiểu sâu.

---

# TUẦN 1 — Làm quen mạng và nhìn thấy "gói tin"

**Làm gì:** tập **nhìn thấy** dữ liệu chạy trên mạng, dựng mạng giả nhỏ.

**Cần hiểu:**
- **Gói tin (packet):** dữ liệu đi theo từng "bưu kiện" nhỏ.
- **TCP:** quy tắc gửi dữ liệu có "bắt tay" trước: **SYN → SYN-ACK → ACK** (gõ
  cửa → ai đó? → tôi đây).
- **Mininet:** tạo "nhiều máy ảo" trong một máy để giả lập mạng.
- **Switch:** thiết bị nối máy và chuyển gói đến đúng nơi (như bưu cục).

**Làm từng bước:**
```bash
$ sudo mn --test pingall           # mạng giả cơ bản, các máy gọi nhau
```
→ `Results: 0% dropped (2/2 received)` = mạng thông.

Bắt tay TCP — mở **2 Terminal**:
```bash
# Terminal 1 (máy ghi âm mạng, ngồi chờ):
$ cd ~/P4-SDN-DDOS
$ sudo tcpdump -i any -w docs/w1_tcp.pcap 'tcp port 80'
# Terminal 2 (tạo dữ liệu để ghi):
$ cd /tmp && sudo python3 -m http.server 80 &
$ curl http://127.0.0.1/
# quay lại Terminal 1 -> Ctrl+C dừng ghi
$ tcpdump -n -r docs/w1_tcp.pcap 'tcp port 80' | head
```
→ Thấy `Flags [S]` (SYN), `[S.]` (SYN-ACK), `[.]` (ACK) = bắt tay 3 bước. Mở đẹp:
`wireshark docs/w1_tcp.pcap &`

**Dấu hiệu đã xong:** pingall 0% dropped; pcap thấy SYN/SYN-ACK/ACK; cả nhóm giải
thích được packet, bắt tay TCP.

---

# TUẦN 2 — Tự dựng mạng cho đề tài

**Làm gì:** dựng mạng đúng đề tài: nhiều người dùng + vài kẻ tấn công + server +
máy đo (probe).

**Cần hiểu:**
- **topology (sơ đồ mạng):** bản vẽ "máy nào nối máy nào".
- **File `configs/topology.yaml`:** chỉnh số máy, IP, tốc độ ở đây. Mọi máy cùng
  dải `10.0.0.x` (một mạng), cùng cắm vào 1 switch.
- **probe:** máy "người dùng mẫu" gửi request đều để đo dịch vụ còn dùng được
  không (chỉ số LSR).
- **nút cổ chai:** đường tới server để hẹp (10 Mbps) cố tình, để tấn công mới
  gây nghẽn được.

**Làm từng bước:**
```bash
$ nano configs/topology.yaml       # xem/chỉnh (mặc định đã ổn, không cần sửa)
$ python3 mininet/build_topo.py    # sinh mạng từ cấu hình
```
→ In `Đã sinh topology: 8 host hợp lệ, 3 host tấn công, 1 probe, 1 server.`

**Dấu hiệu đã xong:** build_topo.py chạy ra đúng số máy; hiểu vì sao mọi máy cùng
1 mạng và vì sao server để đường hẹp.

---

# TUẦN 3 — Lập trình switch bằng P4 (CHECKPOINT 1)

**Làm gì:** biên dịch chương trình P4, cho máy ping nhau **qua switch P4**.

**Cần hiểu:**
- **P4:** ngôn ngữ **lập trình cách switch xử lý gói** (đọc gì, chuyển đâu, đếm
  gì). Không phải ngôn ngữ viết app.
- **BMv2:** switch **phần mềm** để chạy thử P4 (chậm, chỉ để học).
- **Pipeline P4:** gói đi qua 4 chặng — **Parser** (đọc header) → **Ingress**
  (tra bảng, đếm counter, chặn) → **Egress** → **Deparser** (gói lại, gửi ra).
- **Counter:** bộ đếm gói/byte trong switch.
- **iperf3:** công cụ đo tốc độ mạng tối đa (như Speedtest cho mạng nội bộ).

**Làm từng bước:**
```bash
$ cd ~/P4-SDN-DDOS
$ make build        # biên dịch p4/telemetry.p4 -> phải thấy "OK: đã biên dịch P4"
$ make run          # dựng Mininet + switch P4, vào CLI (giữ venv bật!)
mininet> h1 ping -c3 srv
```
→ Ping ra **0% loss** = h1 nói chuyện được với server **qua switch P4** = ✅
**CHECKPOINT 1**.

**Kiểm tra thêm (web qua switch):**
```
mininet> h1 curl -s -o /dev/null -w "HTTP code: %{http_code}\n" http://10.0.0.100/
```
→ `HTTP code: 200` = web cũng chạy qua switch.

**Đo năng lực BMv2 (quan trọng — theo góp ý giảng viên):**
```
mininet> srv iperf3 -s -p 5201 &
mininet> h1 iperf3 -c 10.0.0.100 -p 5201 -t 10
```
→ Xem dòng cuối lấy con số **Mbps**. Ghi lại:
- ~9–10 Mbps → BMv2 theo kịp link (nút nghẽn là link, đúng thiết kế).
- Thấp hơn nhiều → **BMv2 là nút nghẽn**, phải chọn rate tấn công dưới mức này.

**Ghi phiên bản công cụ (máy mới nên ghi lại):**
```bash
$ { echo "=== $(date +%F) ==="; p4c --version; python3 --version; lsb_release -d; } >> env/versions.txt
```

**Sản phẩm tuần 3:** ping qua P4 (0% loss), HTTP 200, con số iperf3 BMv2,
`env/versions.txt`, và `docs/p4_pipeline.md` (giải thích pipeline — làm dần, cho
báo cáo Chương 2/3).

---

# TUẦN 4 — Đọc số liệu từ switch (CHECKPOINT 2)

**Làm gì:** viết controller **đọc counter** từ switch mỗi giây → biết traffic
nhiều/ít.

**Cần hiểu:**
- **Controller:** "bộ não" chạy trên máy, đọc số liệu và ra lệnh cho switch.
- **P4Runtime:** "đường dây" nối controller với switch.
- **rate (tốc độ):** counter là số **cộng dồn**, phải lấy **hiệu 2 lần đọc** mới
  ra tốc độ. VD giây này 1000, giây trước 800 → 200 gói/giây.

**Làm từng bước:** (Terminal 1 giữ `make run`; Terminal 2:)
```bash
$ sudo -E python3 controller/detector.py \
    --p4info build/telemetry.p4.p4info.txtpb \
    --bmv2 build/telemetry.json --poll 1.0 --no-mitigation \
    --out logs/realtime.csv
```
Tạo traffic để thấy số nhảy (trong mininet CLI): `h1 curl -s srv`.
→ Mỗi giây in `pr=... syn/ack=... src=...`; `logs/realtime.csv` có `packet_rate`.

**Dấu hiệu đã xong (CHECKPOINT 2):** đọc counter real-time; CSV có timestamp +
packet_rate.

---

# TUẦN 5 — Tạo 4 loại traffic trong lab

**Làm gì:** tạo **Normal, Flash Crowd, SYN flood, UDP flood** trong lab, có nhãn.

**Cần hiểu:**
- **Normal/Flash:** người thật (bắt tay đủ, có phản hồi). Flash = rất nhiều người
  thật cùng vào.
- **SYN/UDP flood:** 2 kiểu tấn công bơm gói làm nghẽn.
- **threat model:** mô tả kẻ tấn công làm được gì, không làm được gì.
- **ground truth:** nhãn thật do bộ sinh traffic ghi, để chấm điểm model.

**Làm từng bước:**
```bash
$ make run SCENARIO=configs/scenarios/S2.yaml   # Flash
$ make run SCENARIO=configs/scenarios/S3.yaml   # SYN flood
$ make run SCENARIO=configs/scenarios/S4.yaml   # UDP flood
$ cat logs/ground_truth.json
```
→ Success rate giảm khi bị tấn công (S3/S4) nhưng vẫn cao với Flash (S2).

**AN TOÀN (bắt buộc):** mọi traffic tấn công chỉ chạy trong Mininet cô lập;
`docs/safety_checklist.md` cả 3 người ký trước khi chạy.

---

# TUẦN 6 — Dataset có nhãn + baseline threshold/EWMA

**Làm gì:** biến số liệu thu ở Tuần 4–5 thành **một bảng dữ liệu có nhãn**, rồi
làm 2 baseline đơn giản (threshold + EWMA) và **đo Flash-FPR** — bằng chứng cho
thấy baseline báo nhầm "đông người thật" thành "tấn công". Tuần 7 máy học sẽ
phải đánh bại con số này.

**Cần hiểu:**
- **window (1 giây):** gom traffic mỗi giây thành 1 dòng dữ liệu.
- **feature:** con số tóm tắt 1 window (tốc độ gói, tỉ lệ ACK/SYN, số nguồn,
  entropy, độ dốc tăng).
- **nhãn (label):** mỗi window là `normal` / `flash` / `ddos`, lấy từ
  `ground_truth.json` (pha nào đang chạy) — **không** suy từ detector.
- **transition:** window nằm đúng lúc chuyển pha (nửa normal nửa attack) → đánh
  dấu để **loại khi train** cho đỡ nhiễu.
- **threshold/EWMA:** ngưỡng cứng / ngưỡng tự điều chỉnh (đơn giản, hay báo nhầm
  Flash).
- **Flash-FPR:** tỉ lệ window Flash bị báo nhầm thành DDoS (càng thấp càng tốt).
- **data leakage:** lỗi chia dữ liệu khiến độ chính xác ảo — phải chia theo
  **run_id** (lần chạy), không chia ngẫu nhiên theo dòng.

**Làm từng bước:**

*Cách gọn nhất (🟢 máy ảo, ~60 phút, để máy chạy tự động):*
```bash
make collect     # S1..S6 × seed 0..3 = 24 lần chạy, tự gom log vào results/dataset_raw/
make dataset     # gom 24 lần chạy -> data/uniflash_v01.csv
make week6       # threshold + EWMA -> experiments/week6/baseline_report.md
```
Trước khi chạy: tắt chế độ ngủ của **máy thật** (xem Phụ lục A).

> **Nhóm đã đo được:** 2 754 window. Threshold báo nhầm **71%** window Flash,
> EWMA báo nhầm **94%**. Flash Crowd có tốc độ gói trung vị 1 343 gói/giây, còn
> CAO hơn DDoS (1 247). Hình: `figures/tuan06/`.

*Cách làm tay từng bước (để hiểu bản chất):*

*Bước 1 — Thu dữ liệu (🟢 máy ảo).* Chạy từng scenario, mỗi lần controller ghi
`logs/realtime.csv` + `logs/ground_truth.json`. Gom ngay sau mỗi lần chạy:
```bash
# ví dụ sau khi chạy xong scenario S2 (flash):
python3 ml/build_dataset.py --runs logs --run-id run1_S2 \
    --out data/uniflash_v01.csv --append
# lặp cho S1 (normal), S3 (syn), S4 (udp), S5 (flash+ddos)... đổi --run-id
```
Hoặc nếu đã có sẵn nhiều thư mục run (vd `results/raw/`):
```bash
python3 ml/build_dataset.py --runs results/raw/* --out data/uniflash_v01.csv
```
→ In ra mỗi run có bao nhiêu window, phân bố nhãn. Cần có **cả flash lẫn ddos**
mới đo được Flash-FPR.

*Bước 2 — Đánh giá baseline (chạy đâu cũng được, kể cả laptop):*
```bash
python3 baseline/eval_baseline.py --data data/uniflash_v01.csv --out experiments/week6
# hoặc gọn: make week6
```
→ In bảng so sánh + ghi `experiments/week6/baseline_report.md` và `.csv`. Nhìn
cột **Flash-FPR**: threshold/EWMA thường **cao** (báo nhầm flash) — đúng điều cần.

**Mẹo cho máy yếu (nhớ thiết bị nhóm có giới hạn):**
- Mỗi scenario chỉ cần chạy **60–120 giây**, lặp 2–3 lần (đổi seed) là đủ. Không
  cần chạy dài.
- Chạy **từng scenario một**, đóng Wireshark/Firefox khi đang thu để BMv2 khỏi
  tranh CPU.
- Rate tấn công để **vừa phải** (BMv2 chậm, chỉ cần vượt ngưỡng là thấy hiệu quả).
- `build_dataset.py` và `eval_baseline.py` **chỉ xử lý file CSV** (thuần Python,
  không cần pandas) → có thể **copy `logs/*.csv` + `ground_truth.json` sang
  laptop** 🔴 rồi gom/đánh giá offline cho nhẹ máy ảo.

**Dấu hiệu đã xong:**
1. `data/uniflash_v01.csv` có đủ nhãn normal/flash/ddos.
2. `docs`/`data/DATA_DICTIONARY.md` mô tả từng cột (đã có sẵn).
3. `experiments/week6/baseline_report.md` có con số **Flash-FPR** của threshold &
   EWMA (sẽ cao — đó là điểm yếu để tuần 7 vượt qua).

**Nếu lỗi:**
- `Dataset rỗng sau khi loại transition` → file chỉ toàn window chuyển pha; chạy
  scenario dài hơn một chút.
- `chưa đo được Flash-FPR` → dataset chưa có window `flash`; chạy thêm scenario
  S2 rồi `--append`.
- Thiếu cột feature → `realtime.csv` không phải do `controller/detector.py` sinh;
  chạy lại Tuần 4.

---

# TUẦN 7 — Máy học (CHECKPOINT 3)

**Làm gì:** train RandomForest và Logistic Regression phân biệt "người thật đông"
với "tấn công", so với threshold/EWMA.

**Cần hiểu:**
- **Machine Learning:** cho máy xem nhiều ví dụ có nhãn, nó học cách đoán.
- **Precision/Recall/F1/FPR:** thước đo độ chính xác (xem Phụ lục B).
- **Flash-FPR:** tỉ lệ Flash bị đoán nhầm DDoS — quan trọng hơn accuracy tổng.
- **GroupKFold theo run:** chia dữ liệu thành 5 phần sao cho mỗi **lần chạy**
  chỉ nằm trọn trong 1 phần. Model luôn bị chấm trên lần chạy nó chưa từng thấy.
  Nếu chia ngẫu nhiên theo dòng, model "học thuộc" lần chạy → điểm ảo.
- **feature importance:** feature nào model dựa vào nhiều nhất.

**Làm từng bước:**
```bash
make week7       # train + đánh giá + lưu models/rf.pkl
cat experiments/week7/model_report.md
```

> **Nhóm đã đo được:** RandomForest bắt 99,8% tấn công và chỉ báo nhầm **1%**
> Flash (threshold 76%, EWMA 95%). Feature quan trọng nhất là `syn_ack_ratio`
> (0,35): người thật hoàn tất bắt tay nên có nhiều ACK, SYN flood thì không.
> Hình: `figures/tuan07/`.

**Dấu hiệu đã xong (CHECKPOINT 3):** có bảng so sánh, chọn RandomForest, có
`models/rf.pkl`.

---

# TUẦN 8 — Phát hiện online

**Làm gì:** cho model chạy **thời gian thực** khi traffic đang chảy; đo độ trễ
phát hiện + CPU.

**Cần hiểu:**
- **online:** xử lý ngay (khác offline là phân tích file có sẵn).
- **detection latency:** từ lúc tấn công bắt đầu đến lúc model kêu "DDoS".
- **polling:** đọc switch bao lâu một lần (nhanh = phát hiện sớm nhưng tốn CPU).

**Làm từng bước:** Terminal 1: `make run SCENARIO=configs/scenarios/S5.yaml`.
Terminal 2, ngay khi Terminal 1 in `[run_net] server HTTP:80 ...`:
```bash
sudo -E python3 controller/detector.py --p4info build/telemetry.p4.p4info.txtpb \
  --bmv2 build/telemetry.json --model models/rf.pkl --mitigation none \
  --out logs/online_s5.csv
```
→ Giây 30–50 (chỉ có Flash) in `ok`; giây 50–110 (có tấn công) in `DDoS`.

> **Nhóm đã đo được:** phát hiện sau 1,0–1,7 giây; model đoán mỗi lần ~16 ms;
> CPU ~2%. Threshold thì kêu "DDoS" ngay từ khi Flash bắt đầu — báo nhầm.
> Hình: `figures/tuan08/`.

---

# TUẦN 9 — Chặn mà không hại người thật (CHECKPOINT 4)

**Làm gì:** controller **thật sự chặn**; đo **LSR**.

**Cần hiểu:**
- **mitigation:** L0 theo dõi → L1 giới hạn tốc độ → L2 chặn tạm thời (có hạn).
- **LSR:** tỉ lệ request của người thật thành công (càng cao càng tốt — thước đo
  quan trọng nhất).
- **chặn theo cổng vào:** mỗi máy cắm vào switch qua một cổng. IP nguồn thì kẻ tấn
  công giả được, cổng vào thì không. Controller xét từng cổng: cổng nào gửi nhiều
  SYN mà gần như không ACK (không bắt tay đủ), hoặc dồn UDP, thì chặn cổng đó.
- **chặn thô (coarse):** mọi gói SYN/UDP của mọi người đi chung một "cửa hẹp"
  300 gói/giây → chặn cả người thật. Dùng để so sánh.
- **hysteresis:** chỉ đổi mức sau vài window để tránh bật/tắt liên tục.
- **feedback:** probe đo dịch vụ liên tục; người dùng bắt đầu bị ảnh hưởng thì
  leo mức chặn ngay.

**Làm từng bước:** Terminal 1: `make run SCENARIO=configs/scenarios/S5.yaml`.
Terminal 2:
```bash
sudo -E python3 controller/detector.py --p4info build/telemetry.p4.p4info.txtpb \
  --bmv2 build/telemetry.json --model models/rf.pkl \
  --mitigation targeted --feedback --out logs/mitig_s5.csv
```
→ Thấy `L1-ratelimit` → `L2-drop chặn:a1,a2,a3`; khi tấn công dừng, mức tự hạ
về `L0-monitor`.

> **Nhóm đã đo được:** bắt đầu chặn sau ~2,5 giây; chặn đúng a1–a3, **không host
> người thật nào bị chặn** trong mọi lần chạy. Hình: `figures/tuan09/`.

---

# TUẦN 10 — Thí nghiệm chính + thống kê (CHECKPOINT 5)

**Làm gì:** chạy ma trận Scenario × Baseline × seed, tính số có độ tin cậy.

**Cần hiểu:**
- **baseline B0–B3:** B0 không phòng thủ · B1 threshold + chặn thô · B2 máy học
  + chặn thô · B3 máy học + chặn theo cổng + feedback. So B1 với B2 → máy học
  đóng góp gì; so B2 với B3 → chặn chọn lọc đóng góp gì.
- **seed:** mỗi seed đổi cường độ traffic ±30%. Seed train (0–3) khác seed chấm
  điểm (10–14) để không gian lận.
- **chạy lặp:** một lần chạy có thể may/rủi, nên mỗi ô chạy 3–5 lần.
- **CI 95%:** khoảng mà giá trị thật nằm trong đó với độ tin cậy 95%.
- **kiểm định + Holm:** chứng minh "B3 tốt hơn" không phải do may; Holm chỉnh
  lại khi so sánh nhiều lần cùng lúc.

**Làm:**
```bash
make matrix                                 # 72 lần chạy, ~3 giờ
make matrix SCNS="S3 S4 S5" SEEDS="13 14"  # thêm cho đủ 5 lần, ~1 giờ
make analyze                                # -> results/RESULTS.md
```

> **Nhóm đã đo được (LSR khi bị tấn công):** B0 1,5–2,9% · B1/B2 19–37% ·
> **B3 98,7% (S3), 99,8% (S4), 57,9% (S5)**. Mọi lần chạy B3 đều tốt hơn mọi lần
> chạy của baseline khác; p < 0,001. Chi tiết: `results/RESULTS.md`.

---

# TUẦN 11 — Phân tích, báo cáo, demo

**Làm gì:** biến số liệu thành kết luận có bằng chứng; hoàn thiện báo cáo + demo.

**Cần hiểu:**
- **claim-evidence:** mỗi kết luận trỏ tới một bảng/hình.
- **Threats to Validity:** nêu hạn chế (BMv2 không phải phần cứng thật, traffic
  lab, 2 loại attack) — làm bài đáng tin hơn.

**Làm:**
```bash
make figures      # 22 hình theo tuần, chú thích trong figures/README.md
```
Đọc theo thứ tự: `docs/BAO_CAO_KET_QUA.md` → `docs/HUONG_DAN_ON_TAP.md`.

**Demo (~5 phút):** chạy B3 ở S5 như Tuần 9 → Flash bắt đầu, vẫn `ok` → tấn
công bắt đầu, `DDoS` → `L2-drop chặn:a1,a2,a3` → tấn công dừng, về `L0`. Rồi mở
`figures/tuan11/timeline_S5_all.png` để so 4 baseline.

---

# PHỤ LỤC A — LỖI THƯỜNG GẶP & CÁCH SỬA (quan trọng cho newbie)

| Triệu chứng | Nguyên nhân | Cách sửa |
| --- | --- | --- |
| `p4c: command not found` | Chưa cài P4 toolchain | Dùng máy ảo P4 có sẵn (Phần 0.1), đừng tự compile |
| `make: p4c-bm2-ss: No such file` Error 127 | Như trên | Như trên |
| `No module named 'mininet.log'` | Chạy sai Python (không có Mininet) | Dùng `make run` (code đã sửa); giữ venv bật; `git pull` lấy bản mới |
| `'str' object has no attribute 'read'` | Bug cũ trong run_net.py | `git pull` lấy bản đã sửa |
| `Destination Host Unreachable` khi ping | Bug ARP cũ trong build_topo.py | `git pull` lấy bản đã sửa, chạy lại `make run` |
| `iperf3/hping3: command not found` | Máy ảo thiếu công cụ | `sudo apt install -y iperf3 hping3` |
| apt kẹt `Waiting for cache lock ... held by ... unattended-upgr` | Máy đang tự cập nhật nền, giữ khoá | Chờ 2–5 phút nó tự chạy tiếp; hoặc Ctrl+C rồi `sudo systemctl stop unattended-upgrades` → cài lại. Nếu báo `dpkg interrupted`: `sudo dpkg --configure -a` |
| `Address already in use` (port 80) | Server đã chạy sẵn từ make run | Vô hại, bỏ qua |
| `*** Unknown command: make run` | Gõ `make` trong Mininet CLI | `make` là lệnh shell; chạy ở Terminal thường, không gõ trong `mininet>` |
| Mininet treo / lỗi "resource busy" | Lần chạy trước chưa dọn | `sudo mn -c` rồi chạy lại |
| Thí nghiệm dài bỗng mất vài giờ, log có khoảng trống | **Máy thật** (laptop/VMware) cho máy ảo ngủ | Tắt chế độ ngủ của máy thật, đừng gập laptop; chạy lại `make matrix` (run hỏng có file `FAILED` sẽ được chạy lại) |
| Detector báo `mất kết nối switch -> dừng` | Scenario đã xong, mạng đã tắt | Bình thường, không phải lỗi |
| `Thiếu model models/rf.pkl` | Chưa train | Chạy `make week7` trước `make matrix` |
| `cannot bind port 50051` | Còn switch cũ | `make clean` hoặc `sudo mn -c` |
| Paste không được vào Terminal | Terminal dùng phím khác | Dán bằng **Ctrl+Shift+V** (không phải Ctrl+V); hoặc mở chat trong Firefox máy ảo |
| Shell kẹt ở dấu `>` | Nháy `"` chưa đóng (lỗi dán) | Nhấn **Ctrl+C**, gõ lại từng lệnh (đừng dán cả khối) |
| Git `Author identity unknown` | Chưa khai tên/email | `git config --global user.name/user.email` (Phần 0.4) |
| Git `Password authentication is not supported` | Dùng mật khẩu GitHub | Dùng **Personal Access Token** (`ghp_...`) làm password |
| Máy ảo báo nâng cấp 26.04 | Thông báo của Ubuntu | **Don't Upgrade** — nâng là hỏng P4 |
| Ổ đĩa đầy giữa lúc cài | Phân vùng chưa nới sau khi tăng ở VMware | `sudo growpart /dev/sda 2 && sudo resize2fs /dev/sda2` |
| apt lỗi `/cdrom ... no Release file` | Nguồn cài từ đĩa ISO | `sudo mv /etc/apt/sources.list.d/cdrom.sources ~/cdrom.bak` |

**Quy tắc chung khi gặp lỗi:** đọc **dòng cuối** của thông báo lỗi (thường nói rõ
nhất). Copy dòng đó tra Google hoặc hỏi. Phần lớn lỗi là **thiếu công cụ** hoặc
**chạy sai môi trường**.

---

# PHỤ LỤC B — BẢNG THUẬT NGỮ (gặp từ lạ tra ở đây)

| Thuật ngữ | Nghĩa dễ hiểu |
| --- | --- |
| Packet (gói tin) | Đơn vị dữ liệu nhỏ gửi trên mạng |
| Flow | Nhóm gói cùng một cuộc kết nối |
| TCP / UDP | 2 cách gửi dữ liệu; TCP có bắt tay, UDP thì không |
| SYN / ACK | Gói trong bắt tay TCP; SYN = mở, ACK = xác nhận |
| SYN flood / UDP flood | Tấn công bơm nhiều gói SYN/UDP làm nghẽn |
| DDoS | Tấn công từ nhiều máy làm dịch vụ ngừng |
| Flash Crowd | Lưu lượng tăng đột do nhiều người **thật** cùng vào |
| SDN | Mạng tách "bộ não" (controller) khỏi "tay chân" (switch) |
| Control/Data plane | Nơi ra quyết định / nơi chuyển gói |
| Switch | Thiết bị nối máy, chuyển gói đến đúng nơi |
| Controller | "Bộ não" đọc số liệu và ra lệnh cho switch |
| P4 | Ngôn ngữ lập trình cách switch xử lý gói |
| BMv2 | Switch phần mềm chạy thử P4 (không phải phần cứng) |
| P4Runtime | Đường dây để controller đọc counter/nạp rule |
| Mininet | Công cụ giả lập mạng (máy/switch ảo) |
| OVS | Switch ảo mặc định Mininet (đề tài thay bằng BMv2) |
| Counter | Bộ đếm gói/byte trong switch (số cộng dồn) |
| Register | Bộ nhớ nhỏ trong switch lưu trạng thái |
| Meter | Cơ chế đo/giới hạn tốc độ gói (dùng để chặn) |
| Rate | Số gói/giây = hiệu 2 lần đọc counter / thời gian |
| Window | Cửa sổ 1 giây gom gói lại tính feature |
| Feature | Con số tóm tắt traffic 1 window |
| Entropy | Đo độ đa dạng/phân tán (vd nguồn IP) |
| EWMA | Trung bình trượt, làm ngưỡng tự điều chỉnh |
| Threshold | Ngưỡng cứng để báo động |
| Random Forest / XGBoost | Mô hình máy học phân loại |
| Precision/Recall/F1 | Thước đo độ chính xác mô hình |
| FPR / Flash-FPR | Tỉ lệ báo nhầm; Flash-FPR = Flash bị báo DDoS |
| Mitigation | Hành động giảm tấn công (giới hạn/chặn) |
| Hysteresis | Chỉ đổi mức sau vài window, tránh bật/tắt liên tục |
| TTL | Thời hạn của rule chặn (hết hạn tự gỡ) |
| LSR | Tỉ lệ người dùng hợp lệ thành công (càng cao càng tốt) |
| LDR | Tỉ lệ gói hợp lệ bị chặn nhầm (càng thấp càng tốt) |
| Fairness (Jain/Gini) | Mitigation có công bằng giữa người dùng không |
| Detection latency | Từ lúc tấn công đến lúc phát hiện |
| Baseline (B0–B3) | Các phương án so sánh: B0 không phòng thủ … B3 đầy đủ |
| Data leakage | Lỗi chia dữ liệu khiến độ chính xác ảo |
| Ground truth | Nhãn thật do bộ sinh traffic ghi |
| Probe | Máy "người dùng mẫu" đo dịch vụ còn dùng được không |
| Threat model | Kẻ tấn công làm được gì / không làm được gì |
| Bottleneck (nút cổ chai) | Chỗ hẹp nhất làm nghẽn cả đường |
| **iperf3** | Công cụ đo tốc độ/băng thông mạng tối đa (như Speedtest) |
| **hping3** | Công cụ sinh gói SYN (dùng làm SYN flood trong lab) |
| **wrk** | Công cụ tạo tải HTTP nhiều kết nối |
| **venv** | Môi trường ảo Python; máy ảo P4 có `p4dev-python-venv` (giữ bật) |
| **Personal Access Token (ghp_...)** | "Mật khẩu" để đẩy code lên GitHub |
| **ping** | Kiểm tra có thông không + độ trễ (ms) |
| **curl** | Lấy một trang web từ dòng lệnh (kiểm tra dịch vụ) |
| **tcpdump / Wireshark** | Bắt và xem gói tin trên mạng |
| **.ova** | File chứa cả một máy ảo (để import vào VMware) |
| **pcap** | File lưu các gói tin đã bắt được |
| **seed** | Số "hạt giống" cho phần ngẫu nhiên; cùng seed = cùng cường độ traffic. Seed train (0–3) khác seed chấm điểm (10–14) |
| **cổng vào (ingress port)** | Cổng của switch mà gói đi vào; ở switch biên mỗi cổng ≈ một máy. Không giả mạo được như IP nguồn |
| **port_filter** | Bảng trong P4 chứa luật "cổng X → giới hạn tốc độ / chặn" do controller ghi vào |
| **chặn thô / chặn chọn lọc** | Thô: mọi gói SYN/UDP chung một hạn mức (hại cả người thật). Chọn lọc: chỉ chặn cổng có hành vi tấn công |
| **half-open** | Kết nối mới gửi SYN, chưa hoàn tất bắt tay; SYN flood lấp đầy hàng đợi half-open của server |
| **open-loop probe** | Probe gửi request đúng nhịp, không chờ request trước xong, để đo LSR không bị thiên lệch khi server chậm |
| **GroupKFold** | Chia dữ liệu thành K phần sao cho mỗi lần chạy chỉ nằm trong 1 phần — chống rò rỉ dữ liệu |
| **out-of-fold** | Dự đoán cho mỗi dòng dữ liệu bằng model chưa từng thấy lần chạy chứa dòng đó |
| **CI 95%** | Khoảng tin cậy 95%: ghi "98,7% ± 0,7" nghĩa là giá trị thật rất có thể nằm trong 98,0–99,4% |
| **Welch t-test / Mann-Whitney** | Hai kiểm định xem hai nhóm có khác nhau thật không; p < 0,05 = khác biệt có ý nghĩa |
| **Holm** | Cách chỉnh p khi làm nhiều phép so sánh cùng lúc, để tránh "ăn may" một phép |
| **FAILED** | File đánh dấu một lần chạy hỏng (vd máy ngủ giữa chừng); thống kê tự bỏ qua, `--resume` chạy lại |

---

# PHỤ LỤC C — LỆNH HAY DÙNG (bỏ túi)

```bash
# Môi trường
export P4_UTILS=$HOME/tutorials/utils     # chỉ đường thư viện P4 (nếu cần)
make test                                 # test offline (67 PASS)
make build                                # biên dịch P4
make run                                  # dựng mạng + vào Mininet CLI
make run SCENARIO=configs/scenarios/S5.yaml   # chạy 1 kịch bản
make clean                                # dọn
sudo mn -c                                # dọn Mininet treo

# Trong Mininet CLI
h1 ping -c3 srv                           # ping qua switch
h1 curl -s http://10.0.0.100/             # thử web
h1 iperf3 -c 10.0.0.100 -p 5201 -t 10     # đo tốc độ (srv iperf3 -s -p 5201 & trước)
exit                                      # thoát Mininet

# Tuần 5–11 — chạy cả quy trình
make collect                              # T5–6: 24 lần chạy thu dữ liệu (~60')
make dataset week6                        # T6: dataset + threshold/EWMA
make week7                                # T7: train model
make matrix                               # T8–10: ma trận B0..B3 (~3 giờ)
make analyze figures                      # T10–11: thống kê + hình

# Tuần 6 — dataset & baseline (chạy nhẹ, không cần testbed sau khi có CSV)
python3 ml/build_dataset.py --runs logs --run-id run1_S2 --out data/uniflash_v01.csv --append
python3 ml/build_dataset.py --runs results/raw/* --out data/uniflash_v01.csv
make week6                                # đánh giá threshold/EWMA -> Flash-FPR

# Git
git pull                                  # lấy bản mới nhất từ nhóm
git add . && git commit -m "mo ta" && git push   # đẩy việc của mình
```

Kẹt chỗ nào cứ hỏi — mỗi tuần làm từ từ, không vội. Tài liệu này sẽ được bổ sung
khi nhóm gặp thêm tình huống mới.
