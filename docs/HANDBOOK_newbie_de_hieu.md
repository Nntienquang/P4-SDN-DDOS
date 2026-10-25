# Sổ tay thực hành 11 tuần — BẢN DỄ HIỂU CHO NGƯỜI MỚI

> Bản này viết cho người **chưa biết gì về mạng/P4**. Mỗi thuật ngữ đều được
> giải thích bằng lời thường ngày. Cứ làm từ từ, không cần hiểu hết ngay —
> hiểu tới đâu làm tới đó. Bản kỹ thuật gọn hơn là `HANDBOOK.md`.

## Đọc cái này trước (3 phút)

**Đề tài làm gì?** Dựng một mạng giả trong máy ảo, cho "người dùng thật" và "kẻ
tấn công" cùng gửi dữ liệu tới một web server. Hệ thống của nhóm đứng ở giữa,
quan sát, **phân biệt ai là người thật — ai là tấn công**, rồi chặn kẻ tấn công
mà **không chặn nhầm người thật**.

**Ký hiệu trong tài liệu:**
- `$ lệnh` = gõ vào **Terminal** (cửa sổ dòng lệnh màu đen).
- `mininet>` = gõ khi đang ở trong Mininet.
- "🟢 máy ảo" = làm trong Ubuntu (máy ảo). Hầu như mọi thứ đều ở đây.

**Quy tắc sống còn cho newbie:**
1. Một tuần coi là xong khi **chạy ra kết quả**, không phải khi "đã đọc hiểu".
2. Gặp từ lạ → tra **Bảng thuật ngữ** ở cuối tài liệu này.
3. Kẹt lỗi quá 1 buổi → hỏi ngay (GVHD, bạn, hoặc chat), đừng ngồi mò cả ngày.
4. Mỗi lần chạy xong việc gì → **chụp màn hình** lưu lại để làm báo cáo.

**Làm thử ngay (không cần cài gì nặng):**
```bash
$ cd ~/nckh/sdn-p4-ddos
$ pip install -r requirements.txt
$ make test            # phải thấy: TẤT CẢ 38 kiểm tra PASS
```
Nếu ra "38 kiểm tra PASS" nghĩa là phần não của hệ thống (phát hiện, chặn, đo
đạc) chạy đúng. Chưa cần hiểu tại sao — chỉ cần biết nó chạy được.

---

# TUẦN 1 — Làm quen mạng và nhìn thấy "gói tin"

**Tuần này làm gì:** tập **nhìn thấy** dữ liệu chạy trên mạng, và dựng thử một
mạng giả nhỏ xíu.

**Cần hiểu (nói đơn giản):**
- **Gói tin (packet):** dữ liệu trên mạng đi theo từng "bưu kiện" nhỏ gọi là gói.
- **TCP:** bộ quy tắc gửi dữ liệu có "bắt tay" trước và xác nhận — giống gửi thư
  bảo đảm. Bắt tay 3 bước: **SYN → SYN-ACK → ACK** (gõ cửa → ai đó? → tôi đây).
- **Mininet:** công cụ tạo ra "nhiều máy tính ảo" ngay trong một máy, để giả lập
  mạng mà không cần máy thật.
- **Switch:** thiết bị nối các máy lại và chuyển dữ liệu đến đúng máy (như bưu cục).

**Làm từng bước:**

1. Chạy mạng giả có sẵn của Mininet và cho các máy "gọi" nhau:
   ```bash
   $ sudo mn --test pingall
   ```
   → **Kết quả mong đợi:** dòng `Results: 0% dropped (2/2 received)` = các máy
   thông nhau, không mất gói. (`ping` = gửi tín hiệu "còn sống không?")

2. "Ghi âm" dữ liệu mạng để xem bắt tay TCP. Mở **2 Terminal**:

   Terminal 1 — bật máy ghi:
   ```bash
   $ cd ~/nckh/sdn-p4-ddos
   $ sudo tcpdump -i any -w docs/w1_tcp.pcap 'tcp port 80'
   ```
   (tcpdump = máy ghi âm mạng; `tcp port 80` = chỉ ghi dữ liệu web; nó sẽ ngồi chờ)

   Terminal 2 — tạo ra dữ liệu để ghi:
   ```bash
   $ cd /tmp
   $ sudo python3 -m http.server 80 &   # dựng web server tạm
   $ curl http://127.0.0.1/             # gửi 1 yêu cầu web
   ```
   (curl = trình duyệt dòng lệnh; 127.0.0.1 = chính máy này)

   Quay lại Terminal 1 → nhấn **Ctrl + C** để dừng ghi.

3. Xem lại file vừa ghi:
   ```bash
   $ tcpdump -n -r docs/w1_tcp.pcap 'tcp port 80' | head
   ```
   → **Kết quả mong đợi:** thấy `Flags [S]` (SYN), `Flags [S.]` (SYN-ACK),
   `Flags [.]` (ACK) — đó là bắt tay 3 bước. Mở đẹp hơn bằng:
   `wireshark docs/w1_tcp.pcap &`

**Dấu hiệu đã xong tuần 1:**
- [ ] `pingall` ra 0% dropped.
- [ ] Có file pcap thấy được SYN / SYN-ACK / ACK.
- [ ] Cả nhóm nói được: packet là gì, bắt tay TCP là gì (không nhìn tài liệu).

**Nếu lỗi:** Mininet treo → `sudo mn -c` rồi chạy lại. Cổng 80 bận → có nginx
đang chạy sẵn, không sao, vẫn bắt được bắt tay.

---

# TUẦN 2 — Tự dựng mạng cho đề tài

**Tuần này làm gì:** thay vì dùng mạng mẫu, tự dựng mạng **đúng theo đề tài**:
nhiều người dùng, vài kẻ tấn công, một server, một máy đo.

**Cần hiểu:**
- **topology (sơ đồ mạng):** bản vẽ "máy nào nối với máy nào". Của nhóm:
  người dùng + kẻ tấn công + server + probe, tất cả cắm vào 1 switch.
- **File `configs/topology.yaml`:** nơi bạn chỉnh số máy, IP, tốc độ — rồi máy tự
  dựng mạng theo đó. Mọi máy cùng dải `10.0.0.x` (cùng một mạng).
- **probe:** một máy "người dùng mẫu" gửi request đều đều để **đo xem dịch vụ còn
  dùng được không** (chỉ số LSR sau này).
- **nút cổ chai (bottleneck):** đường tới server để hẹp (10 Mbps) **cố tình**, để
  tấn công mới gây nghẽn được — nếu rộng vô hạn thì thí nghiệm vô nghĩa.

**Làm từng bước:**

1. Xem/chỉnh cấu hình mạng (chưa cần sửa cũng được, số mặc định đã ổn):
   ```bash
   $ nano configs/topology.yaml
   ```
   (bên trong: `n_legit: 8` = 8 người dùng, `n_attack: 3` = 3 kẻ tấn công…)

2. Sinh mạng từ cấu hình:
   ```bash
   $ python3 mininet/build_topo.py
   ```
   → **Kết quả mong đợi:** in ra `Đã sinh topology: 8 host hợp lệ, 3 host tấn
   công, 1 probe, 1 server.` và tạo 2 file trong thư mục `mininet/`.

3. (Tuần 2 chưa có P4) Đo thử "sức chứa" của server để sau biết chọn tốc độ tấn
   công: dùng `iperf3` hoặc `wrk`. Ghi lại con số throughput nền.

**Dấu hiệu đã xong tuần 2:**
- [ ] `build_topo.py` chạy ra đúng số máy.
- [ ] Hiểu được: vì sao mọi máy cùng 1 mạng, vì sao server để đường hẹp.

**Nếu lỗi:** thiếu thư viện yaml → `pip install pyyaml` (nhưng code có bản dự
phòng, thường vẫn chạy).

---

# TUẦN 3 — Lập trình cho switch bằng P4 (QUAN TRỌNG)

> Từ tuần này cần **p4c** và **BMv2** (cài ở tuần 2–3). Chưa có thì xem mục cài
> đặt cuối tài liệu, hoặc dùng P4 tutorial VM có sẵn.

**Tuần này làm gì:** biên dịch chương trình P4 và cho máy ping nhau **qua switch
P4** (thay vì switch mặc định).

**Cần hiểu:**
- **P4:** ngôn ngữ để **lập trình cách switch xử lý từng gói tin** (đọc gì, chuyển
  đi đâu, đếm cái gì). Không phải ngôn ngữ viết app.
- **BMv2:** một switch **phần mềm** để chạy thử chương trình P4 (chậm, chỉ để học,
  không dùng số liệu tốc độ của nó để nói về phần cứng thật).
- **Pipeline P4:** gói tin đi qua 4 chặng — Parser (đọc header) → Ingress (tra
  bảng, đếm, chặn) → Egress → Deparser (gói lại, gửi ra).
- **Counter:** bộ đếm trong switch (đếm số gói/byte).

**Làm từng bước:**
```bash
$ export P4_UTILS=$HOME/tutorials/utils   # chỉ đường tới thư viện P4
$ make build        # biên dịch p4/telemetry.p4 -> thư mục build/
$ make run          # dựng Mininet + switch P4, vào CLI
mininet> h1 ping -c3 srv     # h1 ping server qua switch P4
```
→ **Kết quả mong đợi:** `make build` không báo lỗi; trong CLI, `h1 ping srv`
thành công (0% loss).

**Dấu hiệu đã xong (CHECKPOINT 1):** h1 ping được srv qua switch P4; cả nhóm đọc
hiểu được sơ đồ pipeline.

**Nếu lỗi:** `p4c: command not found` → chưa cài toolchain, dùng P4 tutorial VM.
`cannot bind port 50051` → còn switch cũ, `make clean` rồi chạy lại. p4c báo lỗi
cú pháp theo phiên bản → sửa nhỏ theo thông báo, ghi phiên bản vào `env/versions.txt`.

---

# TUẦN 4 — Đọc số liệu từ switch (CHECKPOINT 2)

**Tuần này làm gì:** viết chương trình (controller) **đọc các bộ đếm** từ switch
mỗi giây — để biết traffic đang nhiều hay ít.

**Cần hiểu:**
- **Controller:** "bộ não" chạy trên máy, đọc số liệu từ switch và ra lệnh.
- **P4Runtime:** "đường dây" nối controller với switch để đọc counter / nạp rule.
- **rate (tốc độ):** counter là số **cộng dồn**, phải lấy **hiệu 2 lần đọc** mới ra
  tốc độ. Ví dụ: giây này 1000 gói, giây trước 800 → tốc độ = 200 gói/giây.
- **register, meter:** bộ nhớ nhỏ trong switch (ước lượng số nguồn) và cơ chế giới
  hạn tốc độ (dùng để chặn sau này).

**Làm từng bước:** (Terminal 1 giữ `make run`; Terminal 2 chạy controller)
```bash
$ sudo -E python3 controller/detector.py \
    --p4info build/telemetry.p4.p4info.txtpb \
    --bmv2 build/telemetry.json --poll 1.0 --no-mitigation \
    --out logs/realtime.csv
```
Rồi tạo chút traffic để thấy số nhảy (trong mininet CLI): `h1 curl -s srv`.
→ **Kết quả mong đợi:** mỗi giây in một dòng `pr=... syn/ack=... src=...`; file
`logs/realtime.csv` có cột `packet_rate` tăng khi có traffic.

**Dấu hiệu đã xong (CHECKPOINT 2):** đọc được counter real-time; CSV có timestamp
+ packet_rate.

**Nếu lỗi:** đọc register báo lỗi → có bản dự phòng qua `simple_switch_CLI`, hoặc
dùng số cổng làm proxy (xem cảnh báo `[warn]` khi chạy).

---

# TUẦN 5 — Tạo ra 4 loại traffic trong lab

**Tuần này làm gì:** tạo được **Normal, Flash Crowd, SYN flood, UDP flood** trong
mạng ảo, có nhãn rõ ràng — để sau này dạy máy phân biệt.

**Cần hiểu:**
- **Normal:** ít người, truy cập đều.
- **Flash Crowd:** nhiều người **thật** cùng vào (mở đăng ký) — volume cao nhưng
  hành vi hợp lệ (bắt tay đủ, có phản hồi, nguồn đa dạng, tăng từ từ).
- **SYN flood / UDP flood:** 2 kiểu tấn công — bơm gói SYN/UDP để làm nghẽn.
- **threat model:** mô tả rõ "kẻ tấn công làm được gì, không làm được gì".
- **ground truth:** nhãn thật (loại traffic nào, lúc nào) do bộ sinh traffic ghi
  lại — để sau chấm điểm máy đoán đúng hay sai.

**Làm từng bước:** chạy tự động từng kịch bản:
```bash
$ make run SCENARIO=configs/scenarios/S2.yaml   # Flash Crowd
$ make run SCENARIO=configs/scenarios/S3.yaml   # SYN flood
$ make run SCENARIO=configs/scenarios/S4.yaml   # UDP flood
$ cat logs/ground_truth.json                    # xem nhãn + IP tấn công
```
→ **Kết quả mong đợi:** `ground_truth.json` ghi các pha và IP tấn công; log probe
cho thấy tỉ lệ thành công **giảm khi bị tấn công (S3/S4)** nhưng **vẫn cao với
Flash (S2)**.

**AN TOÀN (bắt buộc):** mọi traffic tấn công **chỉ chạy trong Mininet cô lập**.
File `docs/safety_checklist.md` phải được cả 3 người ký trước khi chạy.

**Dấu hiệu đã xong:** 4 loại traffic chạy lặp được, có config + ground truth,
safety checklist ký đủ.

**Nếu lỗi:** `hping3/iperf3 not found` → `sudo apt-get install hping3 iperf3`.

---

# TUẦN 6 — Biến traffic thành bảng số liệu (dataset)

**Tuần này làm gì:** từ số liệu thực, tạo một **bảng dữ liệu có nhãn** (dataset),
và làm 2 cách phát hiện đơn giản (threshold, EWMA) để so sánh sau.

**Cần hiểu:**
- **window (cửa sổ 1 giây):** gom traffic mỗi 1 giây thành **1 dòng số liệu**.
- **feature:** các con số tóm tắt 1 window: tốc độ gói, tỉ lệ ACK/SYN, số nguồn,
  entropy (độ đa dạng nguồn), độ dốc tăng…
- **threshold:** đặt ngưỡng cứng — vượt là báo tấn công (đơn giản nhưng báo nhầm
  Flash Crowd).
- **EWMA:** ngưỡng tự điều chỉnh theo traffic.
- **data leakage:** lỗi chia dữ liệu khiến độ chính xác cao giả tạo — phải chia
  theo **từng lần chạy (run)**, không chia ngẫu nhiên.

**Làm từng bước:** chạy nhiều lần mỗi kịch bản để gom đủ dữ liệu, ghép thành
dataset (nhóm viết `ml/build_dataset.py` theo gợi ý trong HANDBOOK kỹ thuật),
rồi chạy baseline threshold/EWMA.

→ **Kết quả mong đợi:** file `data/uniflash_v01.csv`; biểu đồ cho thấy
`syn_ack_ratio`, `entropy` **tách được** Flash khỏi DDoS.

**Dấu hiệu đã xong:** dataset có nhãn + data dictionary; đo được **Flash-FPR**
của threshold (tỉ lệ nó báo nhầm Flash).

---

# TUẦN 7 — Dạy máy phân biệt (Machine Learning) — CHECKPOINT 3

**Tuần này làm gì:** huấn luyện **mô hình máy học** (Random Forest, XGBoost) để
phân biệt Normal/Flash/DDoS, so với threshold/EWMA.

**Cần hiểu:**
- **Machine Learning:** cho máy xem nhiều ví dụ có nhãn, nó tự học cách đoán.
- **Random Forest / XGBoost:** 2 loại mô hình "nhiều cây quyết định bỏ phiếu".
- **Precision / Recall / F1 / FPR:** các thước đo độ chính xác.
- **Flash-FPR:** tỉ lệ Flash bị đoán nhầm là DDoS — **quan trọng hơn** độ chính
  xác tổng, vì đó là lỗi hại người dùng thật.

**Làm từng bước:**
```bash
$ python3 ml/train_eval.py --data data/uniflash_v01.csv --out experiments/week7
$ cat experiments/week7/model_compare.csv
```
→ **Kết quả mong đợi:** bảng so sánh; kỳ vọng threshold/EWMA có **Flash-FPR cao**,
Random Forest **thấp hơn hẳn** — đây là bằng chứng cho đề tài. Model lưu ở
`models/rf.pkl`.

**Dấu hiệu đã xong (CHECKPOINT 3):** có bảng so sánh, chọn được model, **khóa danh
sách feature**.

**Nếu lỗi:** độ chính xác ≈ 100% → nghi data leakage, kiểm tra có chia theo
`run_id` không.

---

# TUẦN 8 — Phát hiện theo thời gian thực (online)

**Tuần này làm gì:** cho model chạy **trực tiếp trong lúc traffic đang chạy**, và
đo xem phát hiện nhanh cỡ nào, tốn CPU bao nhiêu.

**Cần hiểu:**
- **online:** xử lý ngay theo thời gian thực (khác "offline" là phân tích file có sẵn).
- **detection latency:** thời gian từ lúc tấn công bắt đầu → lúc hệ thống phát
  hiện. **mitigation latency:** từ lúc phát hiện → lúc rule chặn có hiệu lực.
- **polling:** controller đọc switch bao lâu một lần (nhanh thì phát hiện sớm
  nhưng tốn CPU — đó là một đánh đổi để nghiên cứu).

**Làm từng bước:** chạy scenario có tấn công + detector dùng model, không chặn:
```bash
$ make run SCENARIO=configs/scenarios/S3.yaml      # terminal 1
$ sudo -E python3 controller/detector.py \
    --p4info build/telemetry.p4.p4info.txtpb --bmv2 build/telemetry.json \
    --model models/rf.pkl --no-mitigation --out logs/realtime.csv   # terminal 2
```
→ **Kết quả mong đợi:** in `DDoS` đúng trong pha tấn công; CSV có cột `pred`, `cpu_pct`.

**Dấu hiệu đã xong:** pipeline online in ra Normal/Flash/DDoS theo thời gian thực;
có số detection latency và CPU.

---

# TUẦN 9 — Chặn mà không hại người thật (CHECKPOINT 4)

**Tuần này làm gì:** cho controller **thật sự chặn** tấn công, và đo **LSR** (người
dùng thật còn dùng được dịch vụ không).

**Cần hiểu:**
- **mitigation:** hành động giảm tấn công — L0 chỉ theo dõi, L1 giới hạn tốc độ,
  L2 chặn tạm thời (có thời hạn).
- **LSR (Legitimate Success Rate):** tỉ lệ request của người thật thành công —
  **càng cao càng tốt**. Đây là thước đo quan trọng nhất của đề tài.
- **source attribution:** model chỉ nói "có DDoS", cần thêm bước **xác định chặn
  ai** (nguồn nào). Nếu IP bị giả mạo → chặn theo **loại traffic** (SYN/UDP).
- **hysteresis:** chỉ đổi mức chặn sau vài window để tránh bật/tắt liên tục.

**Làm từng bước:** chạy kịch bản chính (Flash + DDoS đồng thời) + detector có chặn:
```bash
$ make run SCENARIO=configs/scenarios/S5.yaml      # terminal 1
$ sudo -E python3 controller/detector.py \
    --p4info build/telemetry.p4.p4info.txtpb --bmv2 build/telemetry.json \
    --model models/rf.pkl --feedback --out logs/realtime.csv   # terminal 2
```
→ **Kết quả mong đợi:** traffic tấn công tới server giảm, nhưng **LSR vẫn cao**
(người dùng Flash vẫn vào được).

**Dấu hiệu đã xong (CHECKPOINT 4):** rule chặn thật được nạp lên switch; người
dùng hợp lệ vẫn truy cập được; có log LSR.

---

# TUẦN 10 — Thí nghiệm chính và thống kê (CHECKPOINT 5)

**Tuần này làm gì:** chạy **toàn bộ ma trận** thí nghiệm (nhiều kịch bản × nhiều
cách phòng thủ × lặp nhiều lần) và tính số liệu có độ tin cậy.

**Cần hiểu:**
- **baseline B0–B3:** 4 cách để so sánh — B0 không phòng thủ, B1 threshold, B2
  model đơn giản, B3 đầy đủ.
- **chạy lặp:** mỗi tổ hợp chạy ≥10 lần vì một lần có thể may/rủi.
- **khoảng tin cậy (CI 95%):** cho biết con số trung bình đáng tin cỡ nào.
- **kiểm định (Mann-Whitney / bootstrap):** chứng minh "B3 tốt hơn B1" không phải
  do may rủi (p < 0.05).

**Làm từng bước:**
```bash
$ sudo -E python3 experiments/run_matrix.py --seeds 0 1 2 3 4   # chạy qua đêm
$ python3 analysis/aggregate.py --raw results/raw --out results/summary.csv
$ python3 analysis/aggregate.py --raw results/raw --compare S5 lsr B1 B3
```
→ **Kết quả mong đợi:** `summary.csv` có trung bình ± CI95; kiểm định in `p < 0.05`
nếu B3 giữ LSR tốt hơn B1 — kết quả trung tâm của đề tài.

**Dấu hiệu đã xong (CHECKPOINT 5):** có bảng kết quả đầy đủ; khóa feature, không
thêm công nghệ mới.

---

# TUẦN 11 — Phân tích, viết báo cáo, demo

**Tuần này làm gì:** biến số liệu thành kết luận có bằng chứng, hoàn thiện báo
cáo + demo.

**Cần hiểu:**
- **claim-evidence:** mỗi câu kết luận phải trỏ tới một bảng/hình cụ thể.
- **limitation / Threats to Validity:** nêu rõ hạn chế (BMv2 không phải phần cứng
  thật, traffic trong lab, chỉ 2 loại attack) — làm bài **đáng tin hơn**, không
  phải điểm yếu.

**Làm từng bước:**
```bash
$ python3 analysis/make_figures.py --summary results/summary.csv --scn S5
```
→ **Kết quả mong đợi:** các hình trong thư mục `figures/`. Mỗi câu hỏi nghiên cứu
(RQ1–RQ4) có một hình/bảng trả lời.

**Kịch bản demo:** Normal → Flash (không chặn) → Attack (chặn) → Flash+Attack
đồng thời → mitigation → so LSR với baseline.

---

# BẢNG THUẬT NGỮ (gặp từ lạ thì tra ở đây)

| Thuật ngữ | Nghĩa dễ hiểu |
| --- | --- |
| Packet (gói tin) | Đơn vị dữ liệu nhỏ gửi trên mạng |
| Flow | Nhóm gói cùng một cuộc kết nối |
| TCP / UDP | 2 cách gửi dữ liệu; TCP có bắt tay, UDP thì không |
| SYN / ACK | Các gói trong bắt tay TCP; SYN = mở, ACK = xác nhận |
| SYN flood | Tấn công gửi nhiều SYN rồi bỏ dở, làm cạn tài nguyên server |
| UDP flood | Tấn công bơm nhiều gói UDP làm nghẽn băng thông |
| DDoS | Tấn công từ nhiều máy làm dịch vụ ngừng hoạt động |
| Flash Crowd | Lưu lượng tăng đột do nhiều người **thật** cùng vào |
| SDN | Mạng tách "bộ não" (controller) khỏi "tay chân" (switch) |
| Switch | Thiết bị nối máy và chuyển gói đến đúng nơi |
| Controller | "Bộ não" chạy trên máy, đọc số liệu và ra lệnh cho switch |
| P4 | Ngôn ngữ lập trình cách switch xử lý gói |
| BMv2 | Switch phần mềm để chạy thử P4 (không phải phần cứng) |
| P4Runtime | Đường dây để controller đọc counter / nạp rule xuống switch |
| Mininet | Công cụ giả lập mạng (máy/switch ảo) trên một máy |
| OVS | Switch ảo mặc định của Mininet (đề tài thay bằng BMv2) |
| Counter | Bộ đếm gói/byte trong switch (số cộng dồn) |
| Register | Bộ nhớ nhỏ trong switch để lưu trạng thái |
| Meter | Cơ chế đo/giới hạn tốc độ gói (dùng để chặn) |
| Rate (tốc độ) | Số gói trên giây = hiệu 2 lần đọc counter / thời gian |
| Window | Cửa sổ 1 giây để gom gói lại tính feature |
| Feature | Con số tóm tắt traffic trong 1 window (vd packet_rate) |
| Entropy | Đo độ đa dạng/phân tán (vd nguồn IP rải đều hay dồn) |
| EWMA | Trung bình trượt, dùng làm ngưỡng tự điều chỉnh |
| Threshold | Ngưỡng cứng để báo động (cách đơn giản) |
| Random Forest / XGBoost | Mô hình máy học phân loại Normal/Flash/DDoS |
| Precision / Recall / F1 | Thước đo độ chính xác của mô hình |
| FPR / Flash-FPR | Tỉ lệ báo nhầm; Flash-FPR = tỉ lệ Flash bị báo là DDoS |
| Mitigation | Hành động giảm tấn công (giới hạn tốc độ / chặn) |
| Rate-limit | Giới hạn tốc độ thay vì chặn hẳn |
| Hysteresis | Chỉ đổi mức sau vài window để tránh bật/tắt liên tục |
| TTL | Thời hạn của một rule chặn (hết hạn tự gỡ) |
| LSR | Tỉ lệ request của người dùng hợp lệ thành công (càng cao càng tốt) |
| LDR | Tỉ lệ gói hợp lệ bị chặn nhầm (càng thấp càng tốt) |
| Fairness (Jain/Gini) | Đo mitigation có công bằng giữa các người dùng không |
| Detection latency | Thời gian từ lúc tấn công bắt đầu đến lúc phát hiện |
| Baseline (B0–B3) | Các phương án để so sánh: B0 không phòng thủ … B3 đầy đủ |
| Data leakage | Lỗi chia dữ liệu khiến độ chính xác cao giả tạo |
| Ground truth | Nhãn thật do bộ sinh traffic ghi, để chấm điểm model |
| Probe | Máy "người dùng mẫu" đo xem dịch vụ còn dùng được không |
| Threat model | Mô tả kẻ tấn công làm được gì / không làm được gì |
| Bottleneck (nút cổ chai) | Chỗ hẹp nhất làm nghẽn cả đường |

---

# PHỤ LỤC — Cài p4c và BMv2 (cho tuần 3)

Chưa cần ở tuần 1–2. Khi tới tuần 3:
- **Dễ nhất:** tải **P4 tutorial VM** đã cài sẵn mọi thứ, import vào VMware.
- **Hoặc** chạy script cài tự động của p4lang (mất 1–3 tiếng biên dịch):
  ```bash
  $ cd ~ && git clone https://github.com/jafingerhut/p4-guide.git
  $ cd p4-guide/bin && cat README.md     # chọn script khớp phiên bản Ubuntu
  ```
  Cấp máy ảo ≥ 4GB RAM, ≥ 2 CPU, ≥ 20GB trống, chạy lúc rảnh.

Kẹt chỗ nào cứ hỏi — mỗi tuần làm từ từ, không vội.
