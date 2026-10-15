# Data dictionary — dataset UniFlash-DDoS

Mỗi dòng = một **time window** (mặc định 1 giây) thu từ testbed. Nhãn lấy từ
`ground_truth.json` của generator, **không** suy ra từ detector đang đánh giá.

## Cột định danh / ngữ cảnh

| Cột | Kiểu | Ý nghĩa |
| --- | --- | --- |
| `timestamp` | float | Thời điểm window (giây, đồng hồ monotonic của controller) |
| `run_id` | str | Định danh lần chạy, vd `run3_S5`. **Dùng để chia train/test** |
| `scenario` | str | S1..S6 (normal/flash/syn/udp/flash+ddos/background) |
| `label` | str | Nhãn thật: `normal` / `flash` / `ddos` (hoặc `syn`/`udp`) |
| `transition` | 0/1 | 1 = window chuyển pha (nửa normal nửa attack); nên loại khi train |

## Cột feature (khớp `controller/features.py:FEATURE_NAMES`)

| Feature | Đơn vị | Cách tính | Tính ở đâu |
| --- | --- | --- | --- |
| `packet_rate` | pkt/s | Δpacket / Δt | P4 counter |
| `byte_rate` | byte/s | Δbyte / Δt | P4 counter |
| `syn_rate` | pkt/s | Δ(SYN) / Δt | P4 counter |
| `udp_rate` | pkt/s | Δ(UDP) / Δt | P4 counter |
| `syn_ack_ratio` | – | ΔACK / (ΔSYN + 1) | P4 counter |
| `source_count` | – | linear counting từ register bitmap: −m·ln(V) | P4 register + controller |
| `source_entropy` | [0,1] | entropy Shannon chuẩn hóa của packet theo cổng vào | P4 per-port counter + controller |
| `growth_slope` | pkt/s² | packet_rate(t) − packet_rate(t−1) | controller |

## Nhãn và label provenance

- Nhãn đến từ cấu hình scenario (pha nào đang chạy tại thời điểm window) và
  danh sách IP tấn công trong `ground_truth.json`.
- Trong S5 (Flash + DDoS), window có attack được gán `ddos`; đánh giá S5 chủ
  yếu bằng **LSR / LDR / latency**, không chỉ accuracy (vì nhãn hỗn hợp).
- Map nhãn -> lớp nhị phân (ở `ml/dataset.py`): normal=0, flash=0, ddos/syn/udp=1.

## Lưu ý tránh data leakage

- Luôn chia train/test theo `run_id` (GroupShuffleSplit), **không** chia ngẫu
  nhiên theo dòng — các window cùng run rất giống nhau.
- Giữ riêng vài run có tham số khác (rate, số client) làm test để kiểm tra
  khả năng tổng quát.
