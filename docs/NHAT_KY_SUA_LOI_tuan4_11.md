# Nhật ký sửa lỗi & quyết định thiết kế — Tuần 4 → 11

> Ghi lại mọi lỗi tìm thấy khi chạy testbed thật và cách sửa, để (1) báo cáo
> trung thực ở mục *Threats to Validity*, (2) nhóm hiểu vì sao code khác bản
> tuần 1–3. Ngày thực hiện: 03/11/2026.

## A. Lỗi làm hỏng toàn bộ kết quả cũ trong `results/raw/`

Các run chạy sáng 03/11 (S2/S3/S5 × B0/B1) **không dùng được** và đã được chuyển
ra khỏi repo. Dấu hiệu: `S5_B1_seed0/ground_truth.json` ghi `"name": "S1_normal"`,
không có `realtime.csv`.

| # | Lỗi | Hậu quả | Sửa |
| --- | --- | --- | --- |
| A1 | `run_net.py` truyền **đường dẫn (str)** cho `simple_controller.program_switch`, hàm này cần **file handle** (`json.load(f)`) | Mọi scenario crash ngay khi nạp pipeline; `run_matrix` vẫn copy `logs/probe.csv`, `ground_truth.json` **của lần chạy cũ** → kết quả giả | Mở file bằng `with open(...)` |
| A2 | `build_topo.py` bỏ ARP tĩnh, chỉ thêm default gateway | Host cùng subnet /24 ARP trực tiếp tới nhau, switch P4 không trả lời ARP → **mạng không thông**, counter = 0, probe 0% | Nạp ARP tĩnh: mọi IP lab khác → MAC switch |
| A3 | `run_matrix.py` không xoá log cũ, không kiểm tra run | Run hỏng vẫn được tổng hợp như run tốt | Xoá log trước mỗi run; kiểm tra `t0` của ground truth; ghi `FAILED` nếu hỏng; `aggregate`/`build_dataset` bỏ qua run `FAILED` |

## B. Lỗi logic (code chạy nhưng kết quả sai)

| # | Lỗi | Hậu quả | Sửa |
| --- | --- | --- | --- |
| B1 | Nhãn gán theo `elapsed` của detector, nhưng detector khởi động sau scenario ~9s | Window bị gán **sai pha** ~9s ở mỗi ranh giới → dataset nhiễu, detection latency sai | Detector ghi thêm cột `wall` (epoch); nhãn = `wall − t0` của ground truth. Scenario chờ detector sẵn sàng (`logs/detector_ready`) rồi mới bơm traffic |
| B2 | Mitigation không bao giờ drop gói: `suspect_sources=[]` luôn rỗng → chỉ "bật meter", mà meter chỉ áp cho gói đã khớp `src_filter` (không có entry) | B1/B2/B3 thực chất **không phòng thủ** | Thêm bảng `port_filter` (theo cổng vào) và `proto_filter` (theo loại gói SYN/UDP) trong P4; controller nhận diện cổng nghi vấn |
| B3 | Meter: drop khi `color == 1`, nhưng v1model GREEN=0, **YELLOW=1, RED=2**; tên meter trong CLI thiếu tiền tố `MyIngress.` | Meter cấu hình không ăn / drop sai màu | Drop khi RED (2); meter đơn vị gói; tên đầy đủ |
| B4 | UDP flood dùng `iperf3`: một `iperf3 -s` chỉ nhận **1 client một lúc** | S4/S5 chỉ 1/3 host tấn công thật sự gửi UDP | Dùng `hping3 --udp` với payload 1000B, rate = Mbps quy ra pps |
| B5 | `hping3 -c <pps×duration>`: hping3 thực tế chậm hơn danh nghĩa | Tấn công **kéo dài quá pha** (vd pha 15–35s nhưng flood tới 39s) → nhãn sai | Bọc `timeout <duration>`, bỏ `-c` |
| B6 | Probe gửi **tuần tự** (closed-loop): khi server chậm 2–3s/request, probe gửi rất ít trong pha tấn công | LSR cả run bị **thổi phồng** (đo được 0.91 trong khi LSR pha tấn công chỉ 0.06) | Probe open-loop: bắn request đúng nhịp 5 req/s trong thread riêng; thêm metric `lsr_attack` (chỉ trong pha tấn công) |
| B7 | Server `python3 -m http.server` có listen backlog = 5 | Quá mong manh so với server thật (nginx mặc định 511) | `traffic/web_server.py`, backlog 128 (đặt qua `SRV_BACKLOG`) |

## C. Quyết định thiết kế mới (tuần 9)

**Chặn theo CỔNG VÀO thay vì src IP.** Ở switch biên, mỗi cổng = một host.
Cổng vào không giả mạo được (hping3 `--rand-source` vẫn đi vào đúng cổng). Mỗi
cổng có 4 counter (total/SYN/ACK/UDP). Cổng bị nghi khi:
- SYN ≥ 50 gói/s **và** ACK/(SYN+1) < 0.5 (SYN không được hoàn tất), hoặc
- UDP ≥ 100 gói/s.

Client HTTP hợp lệ — kể cả Flash Crowd — có ACK/SYN ≈ 3–10 nên không bị nghi.
Counter đếm **trước** bảng lọc, nên controller vẫn thấy attacker đang bị chặn
(rule được làm mới tới khi attacker dừng hẳn).

**Định nghĩa lại baseline cho thí nghiệm ablation:**

| | Phát hiện | Mitigation |
| --- | --- | --- |
| B0 | (chỉ ghi log) | không |
| B1 | static threshold packet_rate | rate-limit THÔ: mọi gói SYN/UDP chung hạn mức 300 pps |
| B2 | RandomForest | rate-limit THÔ (như B1) |
| B3 | RandomForest | chặn CHỌN LỌC theo cổng (L1 meter 50 pps/cổng → L2 drop) + feedback LSR |

B1↔B2 cô lập đóng góp của **bộ phát hiện**; B2↔B3 cô lập đóng góp của
**mitigation chọn lọc + feedback**.

**Feedback (B3):** detector đọc `logs/probe.csv` mỗi window, tính LSR 5 giây gần
nhất (request OK và ≤ 1s). LSR < 0.9 khi đang có tấn công → leo mức ngay, không
chờ hysteresis; LSR tốt → nới nhanh gấp đôi. *Lưu ý trung thực:* probe vừa là
tín hiệu feedback vừa là thước đo LSR → kết quả LSR probe của B3 có lợi thế; vì
vậy báo cáo thêm `user_sr_attack` (tỉ lệ OK của **mọi client h1–h8**, không
được feed back) làm thước đo độc lập.

## D. Giới hạn đo được của testbed (ghi vào Threats to Validity)

- **BMv2 xử lý tối đa ~1.5–2k gói/s** trên VM 4 vCPU: 3 attacker cấu hình 2000 pps
  mỗi host thực tế chỉ đẩy qua được ~360–500 pps/host. Cường độ tấn công trong
  bài là "vài nghìn pps", không phải line-rate.
- **Thời gian hồi phục sau khi chặn ~6–10s**: khi drop cổng attacker, gói RST của
  attacker cũng bị chặn nên các kết nối half-open (`SYN_RECV`) trên server phải
  chờ hết timeout SYN-ACK. Đây là hiện tượng thật, không phải lỗi: bắt kịp sớm
  (detection latency thấp) quan trọng hơn chặn mạnh.
- Rate-limit 50 pps/cổng (L1) **không đủ** cứu server trước SYN flood (backlog bị
  lấp dần) → L2 drop mới thực sự hiệu quả.
