# sdn-p4-ddos — Phòng thủ DDoS thích ứng trên SDN/P4 có phân biệt Flash Crowd

Repo code + bài thực hành cho đề tài NCKH: phát hiện và giảm thiểu DDoS trên
SDN/P4 (Mininet + BMv2 + P4Runtime), **phân biệt Flash Crowd hợp lệ** và ưu tiên
giữ dịch vụ cho người dùng thật. Mọi thí nghiệm chạy trong Mininet **cô lập**.

> Bài thực hành chi tiết từng tuần: xem tài liệu "Sổ tay thực hành 11 tuần"
> (artifact Docs) hoặc `docs/`. File này là hướng dẫn chạy nhanh.

## 0. Yêu cầu môi trường

- Ubuntu 20.04/22.04/24.04 hoặc **P4 tutorial VM** của p4lang (khuyến nghị).
  **Không dùng Kali làm môi trường chính** — toolchain P4 không hỗ trợ tốt.
- Công cụ: `p4c` (p4c-bm2-ss), BMv2 (`simple_switch_grpc`, `simple_switch_CLI`),
  Mininet, Python 3.8+, và repo [p4lang/tutorials](https://github.com/p4lang/tutorials).
- Python: `pip install -r requirements.txt`
- Công cụ traffic lab: `sudo apt-get install hping3 iperf3 wrk`

Đặt đường dẫn tới utils của tutorials (chứa `p4runtime_lib/`):
```bash
export P4_UTILS=$HOME/tutorials/utils
```

## 1. Chạy thử KHÔNG cần testbed (làm được ngay, cả trên máy thường)

Kiểm tra toàn bộ logic phòng thủ bằng unit test và chạy thử pipeline ML trên
dữ liệu giả lập — để hiểu hệ thống trước khi dựng Mininet:

```bash
make test            # 27 kiểm tra: feature, detector, policy, metrics
make offline-demo    # sinh dữ liệu giả lập -> train model -> bảng so sánh
```

`make offline-demo` minh họa đúng điểm của đề tài: threshold/EWMA trên volume
báo nhầm Flash Crowd (flash_fpr cao), còn model dùng feature hành vi thì không.

> Dữ liệu giả lập (`ml/make_synthetic.py`) CHỈ để test code, **không dùng cho
> báo cáo**. Dữ liệu thật đến từ testbed (tuần 5–6).

## 2. Chạy testbed (trên VM có P4)

```bash
make build           # biên dịch telemetry.p4 -> build/
make topo            # sinh topology.json + s1-runtime.json từ configs/topology.yaml
make run             # dựng Mininet + BMv2, vào CLI
```

Trong một terminal khác, chạy detector (phát hiện + mitigation online):
```bash
sudo -E python3 controller/detector.py \
    --p4info build/telemetry.p4.p4info.txtpb \
    --bmv2   build/telemetry.json \
    --poll 1.0 --out logs/realtime.csv        # baseline threshold (B1)
# hoặc dùng model đã train:  --model models/rf.pkl
```

Chạy tự động một kịch bản (ghi ground truth):
```bash
make run SCENARIO=configs/scenarios/S5.yaml   # Flash + DDoS đồng thời
```

## 3. Thí nghiệm đầy đủ và phân tích (tuần 10–11)

```bash
# chạy ma trận S × B × seed (chạy qua đêm, cần sudo + model đã train)
sudo -E python3 experiments/run_matrix.py --seeds 0 1 2

# tổng hợp mean ± CI95 + kiểm định
python3 analysis/aggregate.py --raw results/raw --out results/summary.csv
python3 analysis/aggregate.py --raw results/raw --compare S5 lsr B1 B3

# vẽ hình
python3 analysis/make_figures.py --summary results/summary.csv --scn S5
```

## Cấu trúc thư mục

| Thư mục | Nội dung |
| --- | --- |
| `p4/` | `telemetry.p4` — forwarding + counter/register/meter + src_filter |
| `mininet/` | sinh topology, launcher Mininet + BMv2 |
| `controller/` | `features.py`, `read_stats.py`, `detector.py` (vòng online) |
| `baseline/` | static threshold + EWMA (B1) |
| `ml/` | dataset, train/eval LR/RF/XGB, sinh dữ liệu giả lập |
| `mitigation/` | `policy.py` (state machine), `mitigator.py` (áp rule P4) |
| `metrics/` | LSR/LDR/FPR/latency/detection-latency |
| `traffic/` | sinh traffic hợp lệ, probe LSR, vỏ gọi công cụ tấn công lab |
| `experiments/` | `run_matrix.py` — ma trận thí nghiệm |
| `analysis/` | tính metric, tổng hợp CI95 + Mann-Whitney, vẽ hình |
| `configs/` | `topology.yaml`, `scenarios/S1..S6.yaml` |

## Baseline so sánh

- **B0** không phòng thủ · **B1** static threshold · **B2** model + mitigation
  đơn giản · **B3** đầy đủ (feedback). Ma trận: S1–S5 × B0–B3, S6 × B1–B3.

## An toàn

Mọi script traffic gọi `traffic/safety.py` để từ chối đích ngoài dải lab
private. Tuyệt đối không chạy traffic tấn công ra ngoài Mininet/Internet.
