"""
detector.py — Vòng lặp online: P4 -> feature -> phát hiện -> mitigation -> log.

Chạy sau khi topology đã lên (make run ở terminal khác):
  sudo python3 controller/detector.py \
      --p4info build/telemetry.p4.p4info.txtpb \
      --bmv2   build/telemetry.json \
      --model models/rf.pkl \
      --poll 1.0 --out logs/realtime.csv

Nếu không truyền --model: dùng static threshold trên packet_rate (baseline B1),
ngưỡng nạp từ --threshold hoặc tự học trong warmup.

Dùng CÙNG features.compute_features() với lúc train để tránh lệch phân phối.
"""
import argparse
import csv
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "baseline"))
sys.path.insert(0, os.path.join(ROOT, "mitigation"))
# Hạ tầng p4runtime_lib của p4lang/tutorials
P4_UTILS = os.environ.get("P4_UTILS",
                          os.path.join(ROOT, "..", "tutorials", "utils"))
sys.path.insert(0, P4_UTILS)

import features as F          # noqa: E402
from detectors import StaticThreshold, EWMA   # noqa: E402
from policy import MitigationPolicy, LEVEL_NAME  # noqa: E402


def connect(p4info, bmv2, addr="127.0.0.1:50051"):
    import p4runtime_lib.bmv2
    import p4runtime_lib.helper
    helper = p4runtime_lib.helper.P4InfoHelper(p4info)
    sw = p4runtime_lib.bmv2.Bmv2SwitchConnection(
        name="s1", address=addr, device_id=0,
        proto_dump_file="logs/p4runtime_s1.txt")
    sw.MasterArbitrationUpdate()
    # Controller detector KHÔNG nạp lại pipeline (run_exercise đã nạp).
    return sw, helper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p4info", required=True)
    ap.add_argument("--bmv2", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--poll", type=float, default=1.0)
    ap.add_argument("--out", default="logs/realtime.csv")
    ap.add_argument("--duration", type=float, default=0, help="0 = chạy mãi")
    ap.add_argument("--no-mitigation", action="store_true")
    ap.add_argument("--feedback", action="store_true",
                    help="B3: bật vòng phản hồi (nới mitigation nhanh hơn)")
    args = ap.parse_args()
    os.makedirs("logs", exist_ok=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    from read_stats import StatReader
    from mitigator import Mitigator

    sw, helper = connect(args.p4info, args.bmv2)
    reader = StatReader(sw, helper)
    mitig = None if args.no_mitigation else Mitigator(sw, helper)
    # B3 (feedback): nới mức nhanh hơn để giảm hại người dùng hợp lệ khi attack
    # đã dịu. Đây là proxy nhẹ cho vòng phản hồi LSR (bản đầy đủ đọc probe).
    policy = (MitigationPolicy(down_windows=3) if args.feedback
              else MitigationPolicy(down_windows=6))

    model = None
    if args.model:
        with open(args.model, "rb") as f:
            model = pickle.load(f)
        print("[detector] dùng model:", args.model)
    else:
        print("[detector] dùng static threshold baseline (B1)")
    st = StaticThreshold(args.threshold if args.threshold else float("inf"))

    try:
        import psutil
        proc = psutil.Process()
    except Exception:
        proc = None

    f = open(args.out, "w", newline="")
    writer = csv.writer(f)
    writer.writerow(["t", "elapsed"] + F.FEATURE_NAMES +
                    ["pred", "level", "cpu_pct"])

    prev_snap = reader.read_snapshot()
    prev_pr = None
    warmup_rates = []
    t0 = time.monotonic()
    print("[detector] bắt đầu vòng lặp online, poll=%.2fs" % args.poll)
    try:
        while True:
            time.sleep(args.poll)
            snap = reader.read_snapshot()
            feat = F.compute_features(snap, prev_snap, prev_packet_rate=prev_pr)
            prev_snap, prev_pr = snap, feat["packet_rate"]

            if model is not None:
                pred = int(model.predict([F.feature_vector(feat)])[0])
            else:
                # baseline: tự học ngưỡng trong 10 window đầu nếu chưa có
                if st.threshold == float("inf"):
                    warmup_rates.append(feat["packet_rate"])
                    if len(warmup_rates) >= 10:
                        st = StaticThreshold.fit_from_normal(warmup_rates, 99, 1.2)
                        print("[detector] threshold học được: %.1f" % st.threshold)
                    pred = 0
                else:
                    pred = st.predict(feat["packet_rate"])

            plan = {"level": 0}
            if mitig is not None:
                plan = policy.update(pred, feat, suspect_sources=[],
                                     now=time.monotonic())
                mitig.apply_plan(plan)

            cpu = proc.cpu_percent() if proc else None
            elapsed = time.monotonic() - t0
            writer.writerow([snap["t"], round(elapsed, 3)] +
                            [round(feat[n], 3) for n in F.FEATURE_NAMES] +
                            [pred, plan.get("level", 0), cpu])
            f.flush()
            tag = "DDoS" if pred else "ok"
            print("  t=%6.1f pr=%8.1f syn/ack=%5.2f src=%5.1f -> %-4s [%s]" % (
                elapsed, feat["packet_rate"], feat["syn_ack_ratio"],
                feat["source_count"], tag, LEVEL_NAME.get(plan.get("level", 0))))

            if args.duration and elapsed >= args.duration:
                break
    except KeyboardInterrupt:
        print("\n[detector] dừng.")
    finally:
        if mitig:
            mitig.clear_all()
        f.close()
        from p4runtime_lib.switch import ShutdownAllSwitchConnections
        ShutdownAllSwitchConnections()


if __name__ == "__main__":
    main()
