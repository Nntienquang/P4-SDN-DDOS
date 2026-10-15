"""
make_synthetic.py — Sinh dataset UniFlash-DDoS GIẢ LẬP để chạy thử pipeline.

CHỈ để smoke-test code ML/metrics khi testbed chưa chạy. KHÔNG phải dữ liệu
nghiên cứu: số liệu sinh từ phân phối tay, không thay thế dataset đo từ Mininet.
Tuần 6 trở đi nhóm thay bằng dữ liệu thật từ feature_collector.

Mỗi lớp (normal/flash/ddos-syn/ddos-udp) được mô phỏng theo đặc trưng kỳ vọng
đã nêu trong đề cương, có nhiễu và nhiều run để test được split-by-run.

Chạy:  python3 ml/make_synthetic.py --out data/uniflash_synth.csv --runs 8
"""
import argparse
import csv
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "controller"))
from features import FEATURE_NAMES  # noqa: E402


def gen_window(scenario, rng):
    """Trả về (feature_dict, label_str) mô phỏng 1 window của 1 scenario."""
    if scenario == "normal":
        pr = rng.gauss(300, 60)
        return _mk(pr, byte=pr*700, syn=rng.gauss(15, 5), udp=rng.gauss(10, 4),
                   ack=rng.gauss(280, 50), src=rng.gauss(8, 2),
                   ent=rng.gauss(0.85, 0.05), slope=rng.gauss(0, 20)), "normal"
    if scenario == "flash":
        # volume cao như DDoS nhưng hành vi hợp lệ: ACK cao, nguồn đa dạng, tăng dần
        pr = rng.gauss(1500, 300)
        return _mk(pr, byte=pr*750, syn=rng.gauss(120, 30), udp=rng.gauss(20, 8),
                   ack=rng.gauss(1400, 250), src=rng.gauss(18, 3),
                   ent=rng.gauss(0.9, 0.04), slope=rng.gauss(60, 40)), "flash"
    if scenario == "syn":
        # SYN flood: SYN rất cao, ACK thấp -> syn_ack_ratio thấp
        pr = rng.gauss(2200, 400)
        return _mk(pr, byte=pr*64, syn=rng.gauss(2000, 350), udp=rng.gauss(5, 3),
                   ack=rng.gauss(150, 80), src=rng.gauss(60, 15),
                   ent=rng.gauss(0.6, 0.1), slope=rng.gauss(400, 200)), "ddos"
    if scenario == "udp":
        # UDP flood: udp_rate rất cao, không có completion
        pr = rng.gauss(2500, 500)
        return _mk(pr, byte=pr*900, syn=rng.gauss(10, 5), udp=rng.gauss(2300, 400),
                   ack=rng.gauss(20, 10), src=rng.gauss(55, 15),
                   ent=rng.gauss(0.55, 0.1), slope=rng.gauss(450, 200)), "ddos"
    raise ValueError(scenario)


def _mk(pr, byte, syn, udp, ack, src, ent, slope):
    pr = max(0, pr)
    return {
        "packet_rate": pr,
        "byte_rate": max(0, byte),
        "syn_rate": max(0, syn),
        "udp_rate": max(0, udp),
        "syn_ack_ratio": max(0, ack) / (max(0, syn) + 1.0),
        "source_count": max(1, src),
        "source_entropy": min(1.0, max(0.0, ent)),
        "growth_slope": slope,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/uniflash_synth.csv")
    ap.add_argument("--runs", type=int, default=8)
    ap.add_argument("--windows", type=int, default=160, help="window/run (timeline)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    # Mỗi run là MỘT dòng thời gian: Normal (baseline) -> sự kiện (flash/attack)
    # -> Normal trở lại. Nhờ vậy EWMA có baseline và nhãn đổi giữa run, giống
    # testbed thật. Một run mang một loại sự kiện.
    events = ["flash", "syn", "udp"]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    cols = ["timestamp", "run_id", "scenario", "label", "transition"] + FEATURE_NAMES
    n = 0
    W = args.windows
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for run in range(args.runs):
            ev = events[run % len(events)]
            rng = random.Random(args.seed * 1000 + run)
            # pha: [0,0.3) normal | [0.3,0.7) event | [0.7,1.0) normal
            for t in range(W):
                frac = t / W
                if frac < 0.3 or frac >= 0.7:
                    sc = "normal"
                else:
                    sc = ev
                trans = 1 if t in (int(0.3 * W), int(0.7 * W)) else 0
                feat, label = gen_window(sc, rng)
                row = {"timestamp": float(t),
                       "run_id": "run%d_%s" % (run, ev),
                       "scenario": sc, "label": label, "transition": trans}
                row.update(feat)
                w.writerow(row)
                n += 1
    print("Đã sinh %d window -> %s (%d run, timeline normal->event->normal)" %
          (n, args.out, args.runs))
    print("LƯU Ý: dữ liệu giả lập chỉ để test pipeline, KHÔNG dùng cho báo cáo.")


if __name__ == "__main__":
    main()
