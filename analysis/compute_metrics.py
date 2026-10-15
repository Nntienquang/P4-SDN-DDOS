"""
compute_metrics.py — Từ log một run -> dòng metric 4 trục.

Đầu vào một thư mục run chứa:
  realtime.csv      (detector: t, elapsed, <features>, pred, level, cpu_pct)
  probe.csv         (probe:   t, ok, latency_ms)
  ground_truth.json (scenario: phases + attack_ips + t0)

Gán nhãn thật cho mỗi window detector dựa trên ground truth (pha nào đang chạy),
rồi tính Security/User/Speed/Cost.

Chạy:  python3 analysis/compute_metrics.py --run results/raw/S5_B3_seed0
"""
import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "metrics"))
import service_metrics as M  # noqa: E402

ATTACK_KINDS = {"syn", "udp"}


def label_at(elapsed, phases):
    """Nhãn chuỗi tại thời điểm 'elapsed' (giây từ đầu scenario).

    Ưu tiên attack > flash > normal nếu nhiều pha chồng nhau (S5).
    """
    active = [ph["kind"] for ph in phases if ph["start"] <= elapsed < ph["end"]]
    if any(k in ATTACK_KINDS for k in active):
        return "ddos"
    if "flash" in active:
        return "flash"
    if "normal" in active:
        return "normal"
    return "normal"


def first_attack_start(phases):
    atk = [ph["start"] for ph in phases if ph["kind"] in ATTACK_KINDS]
    return min(atk) if atk else None


def load_realtime(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def load_probe(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for r in csv.DictReader(f):
            out.append({"ok": r["ok"] in ("1", "True", "true"),
                        "latency_ms": float(r["latency_ms"])})
    return out


def compute(run_dir):
    gt = json.load(open(os.path.join(run_dir, "ground_truth.json")))
    phases = gt["phases"]
    rt = load_realtime(os.path.join(run_dir, "realtime.csv"))
    probe = load_probe(os.path.join(run_dir, "probe.csv"))

    y_true, y_pred, labels, cpu = [], [], [], []
    first_alarm = None
    for r in rt:
        el = float(r["elapsed"])
        lab = label_at(el, phases)
        yt = 1 if lab == "ddos" else 0
        yp = int(float(r["pred"]))
        y_true.append(yt); y_pred.append(yp); labels.append(lab)
        if r.get("cpu_pct") not in (None, "", "None"):
            cpu.append(float(r["cpu_pct"]))
        if yp == 1 and first_alarm is None and yt == 1:
            first_alarm = el

    atk_start = first_attack_start(phases)
    # ước lượng legit drop: xấp xỉ bằng (1-LSR) * tổng request probe (proxy)
    legit_sent = len(probe) or 1
    legit_dropped = sum(1 for p in probe if not p["ok"])

    out = M.summarize_run(
        y_true, y_pred, labels, probe,
        legit_sent=legit_sent, legit_dropped=legit_dropped,
        attack_start_t=atk_start if atk_start is not None else 0,
        first_alarm_t=first_alarm,
        cpu_samples=cpu or None,
        ctrl_messages=None)
    out["run_dir"] = os.path.basename(run_dir)
    out["scenario"] = gt.get("name")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    res = compute(args.run)
    for k, v in res.items():
        print("  %-20s %s" % (k, v))


if __name__ == "__main__":
    main()
