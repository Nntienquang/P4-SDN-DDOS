"""
detector.py — Vòng lặp online: P4 -> feature -> phát hiện -> mitigation -> log.

Chạy sau khi topology đã lên (make run ở terminal khác):
  sudo -E python3 controller/detector.py \
      --p4info build/telemetry.p4.p4info.txtpb \
      --bmv2   build/telemetry.json \
      --model models/rf.pkl --mitigation targeted --feedback \
      --poll 1.0 --out logs/realtime.csv

Phát hiện:
  không --model  -> static threshold trên packet_rate (baseline B1), ngưỡng nạp
                    từ --threshold hoặc tự học trong 10 window warmup.
  --model X.pkl  -> model ML (B2/B3), dùng CÙNG features.compute_features()
                    với lúc train để tránh lệch phân phối.

Mitigation (--mitigation):
  none      -> chỉ ghi log (B0, thu dataset).  (--no-mitigation tương đương)
  coarse    -> rate-limit THÔ mọi gói SYN/UDP chung một hạn mức (B1, B2).
  targeted  -> chặn THEO CỔNG VÀO có hành vi tấn công (B3).
--feedback   -> đọc LSR gần đây từ probe.csv để leo/nới mức (B3).

Cột 'wall' (epoch giây) cho phép gán nhãn khớp với ground_truth.json (t0 epoch)
dù detector khởi động muộn hơn scenario.
"""
import argparse
import csv
import json
import os
import pickle
import sys
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "baseline"))
sys.path.insert(0, os.path.join(ROOT, "mitigation"))
P4_UTILS = os.environ.get("P4_UTILS",
                          os.path.join(ROOT, "..", "tutorials", "utils"))
sys.path.insert(0, P4_UTILS)

import features as F          # noqa: E402
from detectors import StaticThreshold   # noqa: E402
from policy import MitigationPolicy, LEVEL_NAME  # noqa: E402


def connect(p4info, bmv2, addr="127.0.0.1:50051"):
    import p4runtime_lib.bmv2
    import p4runtime_lib.helper
    helper = p4runtime_lib.helper.P4InfoHelper(p4info)
    sw = p4runtime_lib.bmv2.Bmv2SwitchConnection(
        name="s1", address=addr, device_id=0,
        proto_dump_file="logs/p4runtime_s1.txt")
    sw.MasterArbitrationUpdate()
    # detector KHÔNG nạp lại pipeline (run_net đã nạp).
    return sw, helper


def port_map(topo_path):
    """{port: host_name} từ topology.json (link 'sX-pN')."""
    m = {}
    try:
        topo = json.load(open(topo_path))
        for link in topo["links"]:
            m[int(link["node2"].split("-p")[1])] = link["node1"]
    except Exception:
        pass
    return m


class ProbeFeedback:
    """Đọc phần cuối probe.csv -> LSR trong 'window_s' giây gần nhất.

    Request coi là thành công khi ok=1 VÀ latency <= sla_ms (người dùng thật
    bỏ đi nếu phải chờ quá lâu)."""

    def __init__(self, path, window_s=5.0, sla_ms=1000.0):
        self.path, self.window_s, self.sla_ms = path, window_s, sla_ms

    def recent_lsr(self, now_wall):
        try:
            with open(self.path, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 4096))
                lines = f.read().decode(errors="ignore").splitlines()[1:]
        except OSError:
            return None
        n = ok = 0
        for ln in lines:
            parts = ln.split(",")
            if len(parts) < 4:
                continue
            try:
                wall = float(parts[3])
            except ValueError:
                continue
            if now_wall - wall <= self.window_s:
                n += 1
                ok += int(parts[1] == "1" and float(parts[2]) <= self.sla_ms)
        return ok / n if n else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p4info", required=True)
    ap.add_argument("--bmv2", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--poll", type=float, default=1.0)
    ap.add_argument("--out", default="logs/realtime.csv")
    ap.add_argument("--duration", type=float, default=0, help="0 = chạy mãi")
    ap.add_argument("--mitigation", choices=["none", "coarse", "targeted"],
                    default=None)
    ap.add_argument("--no-mitigation", action="store_true",
                    help="= --mitigation none")
    ap.add_argument("--feedback", action="store_true",
                    help="B3: vòng phản hồi LSR từ probe (ngụ ý targeted)")
    ap.add_argument("--probe-csv", default="logs/probe.csv")
    ap.add_argument("--topology", default=os.path.join(ROOT, "mininet", "topology.json"))
    ap.add_argument("--ready-file", default="logs/detector_ready")
    args = ap.parse_args()

    mode = args.mitigation
    if args.no_mitigation:
        mode = "none"
    if mode is None:
        mode = "targeted" if args.feedback else "coarse"
    os.makedirs("logs", exist_ok=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    from read_stats import StatReader
    from mitigator import Mitigator

    sw, helper = connect(args.p4info, args.bmv2)
    reader = StatReader(sw, helper)
    mitig = None if mode == "none" else Mitigator(sw, helper)
    policy = MitigationPolicy(
        up_windows=2,
        down_windows=4 if args.feedback else 6,
        rule_ttl_s=20.0 if args.feedback else 30.0,
        targeted=(mode == "targeted"), feedback=args.feedback)
    fb = ProbeFeedback(args.probe_csv) if args.feedback else None

    pmap = port_map(args.topology)
    protected = {p for p, h in pmap.items() if h in ("srv", "probe")}

    model = None
    if args.model:
        with open(args.model, "rb") as f:
            model = pickle.load(f)
        print("[detector] dùng model:", args.model)
    else:
        print("[detector] dùng static threshold baseline (B1)")
    print("[detector] mitigation=%s feedback=%s" % (mode, args.feedback))
    st = StaticThreshold(args.threshold if args.threshold else float("inf"))

    try:
        import psutil
        proc = psutil.Process()
        proc.cpu_percent()
    except Exception:
        proc = None

    f = open(args.out, "w", newline="")
    writer = csv.writer(f)
    writer.writerow(["t", "wall", "elapsed"] + F.FEATURE_NAMES +
                    ["pred", "level", "mode", "n_rules", "suspects",
                     "lsr_recent", "infer_ms", "cpu_pct"])

    prev_snap = reader.read_snapshot()
    prev_pr = None
    recent_rates = deque(maxlen=3)   # growth_slope trên 3 window gần nhất
    warmup_rates = []
    t0 = time.monotonic()
    with open(args.ready_file, "w") as rf:
        rf.write(str(time.time()))
    print("[detector] bắt đầu vòng lặp online, poll=%.2fs" % args.poll)
    try:
        while True:
            time.sleep(args.poll)
            try:
                snap = reader.read_snapshot()
            except Exception as e:
                print("[detector] mất kết nối switch (%s) -> dừng." %
                      type(e).__name__)
                break
            feat = F.compute_features(snap, prev_snap, prev_packet_rate=prev_pr,
                                      recent_rates=list(recent_rates))
            prates = F.port_rates(snap, prev_snap)
            prev_snap, prev_pr = snap, feat["packet_rate"]
            recent_rates.append(feat["packet_rate"])

            ti = time.perf_counter()
            if model is not None:
                pred = int(model.predict([F.feature_vector(feat)])[0])
            else:
                if st.threshold == float("inf"):
                    warmup_rates.append(feat["packet_rate"])
                    if len(warmup_rates) >= 10:
                        st = StaticThreshold.fit_from_normal(warmup_rates, 99, 1.2)
                        print("[detector] threshold học được: %.1f" % st.threshold)
                    pred = 0
                else:
                    pred = st.predict(feat["packet_rate"])
            infer_ms = (time.perf_counter() - ti) * 1000.0

            sus = F.suspect_ports(prates, protected=protected) if pred else []
            lsr = fb.recent_lsr(time.time()) if fb else None
            plan = {"level": 0, "mode": "none"}
            if mitig is not None:
                plan = policy.update(pred, feat, sus, now=time.monotonic(), lsr=lsr)
                try:
                    mitig.apply_plan(plan)
                except Exception as e:
                    print("[detector] lỗi ghi rule (%s) -> dừng." % type(e).__name__)
                    break

            cpu = proc.cpu_percent() if proc else None
            elapsed = time.monotonic() - t0
            n_rules = len(mitig.active_keys()) if mitig else 0
            writer.writerow([round(snap["t"], 3), round(snap["wall"], 3),
                             round(elapsed, 3)] +
                            [round(feat[n], 3) for n in F.FEATURE_NAMES] +
                            [pred, plan.get("level", 0), plan.get("mode", "none"),
                             n_rules,
                             "|".join(pmap.get(p, str(p)) for p in sus),
                             "" if lsr is None else round(lsr, 3),
                             round(infer_ms, 3), cpu])
            f.flush()
            tag = "DDoS" if pred else "ok"
            print("  t=%6.1f pr=%7.1f syn/ack=%5.2f src=%4.1f -> %-4s [%s] %s%s" % (
                elapsed, feat["packet_rate"], feat["syn_ack_ratio"],
                feat["source_count"], tag, LEVEL_NAME.get(plan.get("level", 0)),
                ("chặn:" + ",".join(pmap.get(p, str(p)) for p in sus)) if sus and mitig else "",
                (" lsr=%.2f" % lsr) if lsr is not None else ""))
            if args.duration and elapsed >= args.duration:
                break
    except KeyboardInterrupt:
        print("\n[detector] dừng.")
    finally:
        f.close()
        if mitig:
            try:
                mitig.clear_all()
            except Exception:
                pass
        try:
            from p4runtime_lib.switch import ShutdownAllSwitchConnections
            ShutdownAllSwitchConnections()
        except Exception:
            pass
        try:
            os.remove(args.ready_file)
        except OSError:
            pass


if __name__ == "__main__":
    main()
