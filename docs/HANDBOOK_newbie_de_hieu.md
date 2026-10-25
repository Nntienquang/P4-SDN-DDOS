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
Ra "38 PASS" = phần não hệ thống (phát hiện/chặn/đo) chạy đúng. Chưa cần hiểu sâu.

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

# TUẦN 6 — Dataset, feature, threshold/EWMA

**Làm gì:** từ số liệu thực tạo **bảng dữ liệu có nhãn**; làm baseline
threshold + EWMA.

**Cần hiểu:**
- **window (1 giây):** gom traffic mỗi giây thành 1 dòng dữ liệu.
- **feature:** con số tóm tắt 1 window (tốc độ gói, tỉ lệ ACK/SYN, số nguồn,
  entropy, độ dốc tăng).
- **threshold/EWMA:** ngưỡng cứng / ngưỡng tự điều chỉnh (đơn giản, báo nhầm Flash).
- **data leakage:** lỗi chia dữ liệu khiến độ chính xác ảo — phải chia theo **run**.

**Dấu hiệu đã xong:** dataset có nhãn + data dictionary; đo được Flash-FPR của
threshold.

---

# TUẦN 7 — Máy học (CHECKPOINT 3)

**Làm gì:** train Random Forest/XGBoost phân biệt Normal/Flash/DDoS, so với
threshold/EWMA.

**Cần hiểu:**
- **Machine Learning:** cho máy xem nhiều ví dụ có nhãn, nó học cách đoán.
- **Precision/Recall/F1/FPR:** thước đo độ chính xác.
- **Flash-FPR:** tỉ lệ Flash bị đoán nhầm DDoS — quan trọng hơn accuracy tổng.

**Làm từng bước:**
```bash
$ python3 ml/train_eval.py --data data/uniflash_v01.csv --out experiments/week7
$ cat experiments/week7/model_compare.csv
```
→ threshold/EWMA có Flash-FPR cao, RF thấp hơn hẳn = bằng chứng cho đề tài.

**Dấu hiệu đã xong (CHECKPOINT 3):** bảng so sánh, chọn model, khóa feature.

---

# TUẦN 8 — Phát hiện online

**Làm gì:** cho model chạy **thời gian thực**; đo detection latency + CPU.

**Cần hiểu:**
- **online:** xử lý ngay (khác offline là phân tích file có sẵn).
- **detection latency:** từ lúc tấn công bắt đầu đến lúc phát hiện.
- **polling:** đọc switch bao lâu một lần (nhanh = phát hiện sớm nhưng tốn CPU).

**Làm:** chạy scenario có tấn công + detector dùng model `--model models/rf.pkl
--no-mitigation`. → in Normal/Flash/DDoS theo thời gian thực.

---

# TUẦN 9 — Chặn mà không hại người thật (CHECKPOINT 4)

**Làm gì:** controller **thật sự chặn**; đo **LSR**.

**Cần hiểu:**
- **mitigation:** L0 theo dõi → L1 giới hạn tốc độ → L2 chặn tạm thời (có hạn).
- **LSR:** tỉ lệ người thật vẫn dùng được dịch vụ (càng cao càng tốt — thước đo
  quan trọng nhất).
- **source attribution:** model nói "có DDoS", cần thêm bước **chặn ai**; IP giả
  mạo → chặn theo loại traffic.
- **hysteresis:** chỉ đổi mức sau vài window để tránh bật/tắt liên tục.

**Làm:** `make run SCENARIO=configs/scenarios/S5.yaml` + detector `--model
models/rf.pkl --feedback`. → attack giảm nhưng LSR vẫn cao.

---

# TUẦN 10 — Thí nghiệm chính + thống kê (CHECKPOINT 5)

**Làm gì:** chạy ma trận S×B×seed, tính số có độ tin cậy.

**Cần hiểu:**
- **baseline B0–B3:** B0 không phòng thủ … B3 đầy đủ.
- **chạy lặp ≥10 lần:** vì một lần có thể may/rủi.
- **CI 95% / kiểm định:** chứng minh "B3 tốt hơn B1" không phải do may.

**Làm:**
```bash
$ sudo -E python3 experiments/run_matrix.py --seeds 0 1 2 3 4   # chạy qua đêm
$ python3 analysis/aggregate.py --raw results/raw --out results/summary.csv
$ python3 analysis/aggregate.py --raw results/raw --compare S5 lsr B1 B3
```
→ `summary.csv` có mean ± CI95; kiểm định in `p<0.05` nếu B3 giữ LSR tốt hơn B1.

---

# TUẦN 11 — Phân tích, báo cáo, demo

**Làm gì:** biến số liệu thành kết luận có bằng chứng; hoàn thiện báo cáo + demo.

**Cần hiểu:**
- **claim-evidence:** mỗi kết luận trỏ tới một bảng/hình.
- **Threats to Validity:** nêu hạn chế (BMv2 không phải phần cứng thật, traffic
  lab, 2 loại attack) — làm bài đáng tin hơn.

**Làm:**
```bash
$ python3 analysis/make_figures.py --summary results/summary.csv --scn S5
```
**Demo:** Normal → Flash (không chặn) → Attack (chặn) → Flash+Attack → mitigation
→ so LSR với baseline.

---

# PHỤ LỤC A — LỖI THƯỜNG GẶP & CÁCH SỬA (quan trọng cho newbie)

| Triệu chứng | Nguyên nhân | Cách sửa |
| --- | --- | --- |
| `p4c: command not found` | Chưa cài P4 toolchain | Dùng máy ảo P4 có sẵn (Phần 0.1), đừng tự compile |
| `make: p4c-bm2-ss: No such file` Error 127 | Như trên | Như trên |
| `No module named 'mininet.log'` | Chạy sai Python (không có Mininet) | Dùng `make run` (code đã sửa); giữ venv bật; `git pull` lấy bản mới |
| `'str' object has no attribute 'read'` | Bug cũ trong run_net.py | `git pull` lấy bản đã sửa |
| `Destination Host Unreachable` khi ping | Bug ARP cũ trong build_topo.py | `git pull` lấy bản đã sửa, chạy lại `make run` |
| `iperf3: command not found` | Máy ảo thiếu iperf3 | `sudo apt install -y iperf3` |
| `Address already in use` (port 80) | Server đã chạy sẵn từ make run | Vô hại, bỏ qua |
| `*** Unknown command: make run` | Gõ `make` trong Mininet CLI | `make` là lệnh shell; chạy ở Terminal thường, không gõ trong `mininet>` |
| Mininet treo / lỗi "resource busy" | Lần chạy trước chưa dọn | `sudo mn -c` rồi chạy lại |
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

---

# PHỤ LỤC C — LỆNH HAY DÙNG (bỏ túi)

```bash
# Môi trường
export P4_UTILS=$HOME/tutorials/utils     # chỉ đường thư viện P4 (nếu cần)
make test                                 # test offline (38 PASS)
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

# Git
git pull                                  # lấy bản mới nhất từ nhóm
git add . && git commit -m "mo ta" && git push   # đẩy việc của mình
```

Kẹt chỗ nào cứ hỏi — mỗi tuần làm từ từ, không vội. Tài liệu này sẽ được bổ sung
khi nhóm gặp thêm tình huống mới.
