"""
compute_metrics.py — Từ log một run -> dòng metric 4 trục Security/User/Speed/Cost.

Đầu vào một thư mục run chứa:
  realtime.csv      (detector: t, wall, elapsed, <features>, pred, level, ...)
  probe.csv         (probe:   t, ok, latency_ms, wall)
  ground_truth.json (scenario: phases + attack_ips + t0 epoch)
  legit/*.csv       (mỗi host hợp lệ: wall, ok, latency_ms từng request)

Thời gian của mọi log được quy về "giây kể từ t0 của scenario" bằng cột wall
(epoch) -> nhãn khớp đúng pha dù detector khởi động trước/sau scenario.
Log cũ không có wall thì dùng elapsed (kém chính xác hơn vài giây).

Metric chính:
  Security: precision, recall, f1, fpr, flash_fpr (theo window, bỏ window
            transition sát ranh giới pha)
  User    : lsr (probe cả run), lsr_attack (probe trong pha tấn công),
            lsr_sla (ok VÀ latency <= 1s), user_sr (mọi client hợp lệ),
            flash_sr (client trong pha Flash Crowd), jain (công bằng giữa host)
  Speed   : detection_latency_s, mitigation_latency_s, lat_p50/p95_ms
  Cost    : cpu_mean_pct, infer_ms_mean, max_rules

Chạy:  python3 analysis/compute_metrics.py --run results/raw/S5_B3_seed10
"""
import argparse
import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "metrics"))
import service_metrics as M  # noqa: E402

ATTACK_KINDS = {"syn", "udp"}
SLA_MS = 1000.0
TRANSITION_MARGIN = 1.5     # giây quanh ranh giới pha bị loại khỏi metric window


def label_at(rel_t, phases):
    """Nhãn tại thời điểm rel_t (giây từ t0). Ưu tiên attack > flash > normal."""
    active = [ph["kind"] for ph in phases if ph["start"] <= rel_t < ph["end"]]
    if any(k in ATTACK_KINDS for k in active):
        return "ddos"
    if "flash" in active:
        return "flash"
    return "normal"


def near_boundary(rel_t, phases, margin=TRANSITION_MARGIN):
    return any(abs(rel_t - ph["start"]) < margin or abs(rel_t - ph["end"]) < margin
               for ph in phases)


def attack_windows(phases):
    return [(ph["start"], ph["end"]) for ph in phases if ph["kind"] in ATTACK_KINDS]


def in_any(rel_t, spans):
    return any(a <= rel_t < b for a, b in spans)


def first_attack_start(phases):
    atk = [ph["start"] for ph in phases if ph["kind"] in ATTACK_KINDS]
    return min(atk) if atk else None


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def rel_time_fn(gt, rt_rows):
    """Trả về hàm row -> giây kể từ t0 của scenario."""
    t0 = gt.get("t0")
    if rt_rows and "wall" in rt_rows[0] and t0:
        return lambda r: float(r["wall"]) - t0
    return lambda r: float(r["elapsed"])


def load_probe(run_dir, gt):
    rows = _read_csv(os.path.join(run_dir, "probe.csv"))
    out = []
    t0 = gt.get("t0")
    for r in rows:
        ok = r["ok"] in ("1", "True", "true")
        lat = float(r["latency_ms"])
        rel = float(r["wall"]) - t0 if ("wall" in r and t0) else float(r["t"])
        out.append({"ok": ok, "latency_ms": lat, "rel": rel})
    return out


def load_legit(run_dir, gt):
    """{host: [ {ok, latency_ms, rel, phase_kind} ]} từ legit/<host>_p<i>.csv."""
    t0 = gt.get("t0", 0)
    phases = gt.get("phases", [])
    by_host = {}
    for path in sorted(glob.glob(os.path.join(run_dir, "legit", "*.csv"))):
        base = os.path.basename(path)[:-4]
        host, _, pidx = base.rpartition("_p")
        try:
            kind = phases[int(pidx)]["kind"]
        except (ValueError, IndexError):
            kind = "normal"
        for r in _read_csv(path):
            by_host.setdefault(host, []).append({
                "ok": r["ok"] == "1", "latency_ms": float(r["latency_ms"]),
                "rel": float(r["wall"]) - t0, "phase_kind": kind})
    return by_host


def _rate(items):
    return (sum(1 for x in items if x["ok"]) / len(items)) if items else None


def compute(run_dir):
    gt = json.load(open(os.path.join(run_dir, "ground_truth.json")))
    phases = gt["phases"]
    rt = _read_csv(os.path.join(run_dir, "realtime.csv"))
    rel = rel_time_fn(gt, rt)
    atk_spans = attack_windows(phases)
    atk_start = first_attack_start(phases)
    duration = gt.get("duration") or max(ph["end"] for ph in phases)

    # ---------- Security (theo window detector) ----------
    y_true, y_pred, labels, cpu, infer, rules = [], [], [], [], [], []
    first_alarm = first_mitig = None
    for r in rt:
        t = rel(r)
        if t < 0 or t > duration:
            continue
        lab = label_at(t, phases)
        yp = int(float(r["pred"]))
        lvl = int(float(r.get("level", 0) or 0))
        if atk_start is not None and t >= atk_start:
            if yp == 1 and first_alarm is None and lab == "ddos":
                first_alarm = t
            if lvl >= 1 and first_mitig is None and lab == "ddos":
                first_mitig = t
        if r.get("cpu_pct") not in (None, "", "None"):
            cpu.append(float(r["cpu_pct"]))
        if r.get("infer_ms") not in (None, ""):
            infer.append(float(r["infer_ms"]))
        if r.get("n_rules") not in (None, ""):
            rules.append(int(float(r["n_rules"])))
        if near_boundary(t, phases):
            continue
        y_true.append(1 if lab == "ddos" else 0)
        y_pred.append(yp)
        labels.append(lab)

    # ---------- User ----------
    probe = load_probe(run_dir, gt)
    probe_atk = [p for p in probe if in_any(p["rel"], atk_spans)]
    sla = [dict(p, ok=p["ok"] and p["latency_ms"] <= SLA_MS) for p in probe]
    legit = load_legit(run_dir, gt)
    all_legit = [x for xs in legit.values() for x in xs]
    flash_req = [x for x in all_legit if x["phase_kind"] == "flash"]
    legit_atk = [x for x in all_legit if in_any(x["rel"], atk_spans)]
    # fairness: tỉ lệ thành công của TỪNG host (trong pha tấn công nếu có)
    per_host = []
    for h, xs in legit.items():
        xs2 = [x for x in xs if in_any(x["rel"], atk_spans)] if atk_spans else xs
        if xs2:
            per_host.append(_rate(xs2))

    sec = M.security_metrics(y_true, y_pred)
    lat = M.latency_percentiles(probe)
    out = {
        "precision": sec["precision"], "recall": sec["recall"],
        "f1": sec["f1"], "fpr": sec["fpr"],
        "flash_fpr": M.flash_false_positive_rate(labels, y_pred),
        "lsr": M.legitimate_success_rate(probe),
        "lsr_attack": M.legitimate_success_rate(probe_atk),
        "lsr_sla": M.legitimate_success_rate(sla),
        "ldr": (1 - M.legitimate_success_rate(probe)) if probe else None,
        "user_sr": _rate(all_legit),
        "user_sr_attack": _rate(legit_atk),
        "flash_sr": _rate(flash_req),
        "jain": M.jains_fairness(per_host) if per_host else None,
        "lat_p50_ms": lat["p50"], "lat_p95_ms": lat["p95"],
        "detection_latency_s": (M.detection_latency(atk_start, first_alarm)
                                if atk_start is not None else None),
        "mitigation_latency_s": (M.detection_latency(atk_start, first_mitig)
                                 if atk_start is not None else None),
        "cpu_mean_pct": (sum(cpu) / len(cpu)) if cpu else None,
        "infer_ms_mean": (sum(infer) / len(infer)) if infer else None,
        "max_rules": max(rules) if rules else None,
        "n_windows": len(y_true),
        "legit_requests": len(all_legit),
    }
    out["run_dir"] = os.path.basename(run_dir.rstrip("/"))
    out["scenario"] = gt.get("name")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    res = compute(args.run)
    for k, v in res.items():
        print("  %-22s %s" % (k, round(v, 4) if isinstance(v, float) else v))


if __name__ == "__main__":
    main()
