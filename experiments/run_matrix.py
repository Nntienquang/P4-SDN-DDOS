#!/usr/bin/env python3
"""
run_matrix.py — Chạy ma trận thí nghiệm S × B × seed (tuần 6 thu dữ liệu, tuần 10).

Với mỗi tổ hợp: dựng Mininet + BMv2, chạy detector đúng cấu hình baseline,
chạy scenario, thu log vào <out>/<SCN>_<B>_seed<k>/, rồi dọn (mn -c).

Baseline (phát hiện + mitigation):
  B0 = không phòng thủ: detector chỉ GHI LOG feature (dùng để thu dataset)
  B1 = static threshold trên packet_rate + rate-limit THÔ theo loại gói SYN/UDP
  B2 = model ML                          + rate-limit THÔ theo loại gói SYN/UDP
  B3 = model ML + chặn CHỌN LỌC theo cổng vào + vòng phản hồi LSR (đề xuất)
So sánh B1↔B2 = đóng góp của bộ phát hiện; B2↔B3 = đóng góp của mitigation
chọn lọc + feedback.

Mỗi thư mục run có: realtime.csv, probe.csv, ground_truth.json, legit/*.csv,
meta.json (+ FAILED nếu run hỏng — aggregate sẽ bỏ qua).

PHẢI chạy bằng sudo (giữ PATH của venv):
  sudo env "PATH=$PATH" python3 experiments/run_matrix.py \\
       --scenarios S1 S2 S3 S4 S5 S6 --baselines B0 B1 B2 B3 --seeds 10 11 12

Thu dataset tuần 6 (chỉ B0, seed riêng để không trùng tập đánh giá):
  sudo env "PATH=$PATH" python3 experiments/run_matrix.py --baselines B0 \\
       --seeds 0 1 2 3 --out results/dataset_raw
"""
import argparse
import glob
import json
import os
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, "build")
P4INFO = os.path.join(BUILD, "telemetry.p4.p4info.txtpb")
BMV2 = os.path.join(BUILD, "telemetry.json")
LOGS = os.path.join(ROOT, "logs")


def detector_args(baseline, model_path):
    """Tham số thêm cho detector theo baseline."""
    if baseline == "B0":
        return ["--mitigation", "none"]
    if baseline == "B1":
        return ["--mitigation", "coarse"]
    if baseline == "B2":
        return ["--model", model_path, "--mitigation", "coarse"]
    if baseline == "B3":
        return ["--model", model_path, "--mitigation", "targeted", "--feedback"]
    raise ValueError(baseline)


def _clean_logs():
    for fn in ("probe.csv", "ground_truth.json", "net_ready", "detector_ready"):
        p = os.path.join(LOGS, fn)
        if os.path.exists(p):
            os.remove(p)
    shutil.rmtree(os.path.join(LOGS, "legit"), ignore_errors=True)


def _stop(proc, sig=signal.SIGINT, timeout=10):
    if proc.poll() is not None:
        return
    proc.send_signal(sig)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def run_one(scn, baseline, seed, model_path, out_root, jitter, owner):
    name = "%s_%s_seed%d" % (scn, baseline, seed)
    outdir = os.path.join(out_root, name)
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir)
    scn_file = os.path.join(ROOT, "configs", "scenarios", scn + ".yaml")
    print("\n===== %s =====" % name, flush=True)
    t_start = time.time()

    subprocess.call(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _clean_logs()
    env = dict(os.environ, PYTHONPATH=ROOT)
    net_log = open(os.path.join(outdir, "net.log"), "w")
    net = subprocess.Popen(
        ["python3", os.path.join(ROOT, "mininet", "run_net.py"),
         "--p4info", P4INFO, "--bmv2", BMV2,
         "--runtime", os.path.join(ROOT, "mininet", "s1-runtime.json"),
         "--scenario", scn_file, "--seed", str(seed), "--jitter", str(jitter),
         "--wait-detector", "30"],
        cwd=ROOT, env=env, stdout=net_log, stderr=subprocess.STDOUT)

    # chờ mạng + pipeline sẵn sàng rồi mới bật detector
    t_wait = time.time()
    while not os.path.exists(os.path.join(LOGS, "net_ready")):
        if net.poll() is not None or time.time() - t_wait > 90:
            break
        time.sleep(0.3)

    det_log = open(os.path.join(outdir, "detector.log"), "w")
    det = subprocess.Popen(
        ["python3", os.path.join(ROOT, "controller", "detector.py"),
         "--p4info", P4INFO, "--bmv2", BMV2,
         "--poll", "1.0", "--out", os.path.join(outdir, "realtime.csv")]
        + detector_args(baseline, model_path),
        cwd=ROOT, env=env, stdout=det_log, stderr=subprocess.STDOUT)

    try:
        net.wait(timeout=600)
    except subprocess.TimeoutExpired:
        _stop(net, signal.SIGTERM)
    _stop(det)
    net_log.close(); det_log.close()

    # gom log + kiểm tra hợp lệ
    problems = []
    gt_path = os.path.join(LOGS, "ground_truth.json")
    if os.path.exists(gt_path):
        shutil.copy(gt_path, outdir)
        gt = json.load(open(gt_path))
        if gt.get("t0", 0) < t_start:
            problems.append("ground_truth cũ")
    else:
        problems.append("thiếu ground_truth.json")
    if os.path.exists(os.path.join(LOGS, "probe.csv")):
        shutil.copy(os.path.join(LOGS, "probe.csv"), outdir)
    else:
        problems.append("thiếu probe.csv")
    if os.path.isdir(os.path.join(LOGS, "legit")):
        shutil.copytree(os.path.join(LOGS, "legit"), os.path.join(outdir, "legit"))
    rt = os.path.join(outdir, "realtime.csv")
    if not os.path.exists(rt) or sum(1 for _ in open(rt)) < 20:
        problems.append("realtime.csv thiếu/quá ngắn")

    meta = {"scenario": scn, "baseline": baseline, "seed": seed,
            "jitter": jitter, "model": model_path if baseline in ("B2", "B3") else None,
            "detector_args": detector_args(baseline, model_path),
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "wall_s": round(time.time() - t_start, 1), "problems": problems}
    json.dump(meta, open(os.path.join(outdir, "meta.json"), "w"), indent=2)
    if problems:
        open(os.path.join(outdir, "FAILED"), "w").write("\n".join(problems))
    subprocess.call(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if owner:
        subprocess.call(["chown", "-R", owner, outdir])
    print("  -> %s (%.0fs) %s" % (outdir, time.time() - t_start,
                                  "LỖI: " + "; ".join(problems) if problems else "OK"),
          flush=True)
    return not problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", nargs="+",
                    default=["S1", "S2", "S3", "S4", "S5", "S6"])
    ap.add_argument("--baselines", nargs="+", default=["B0", "B1", "B2", "B3"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[10, 11, 12])
    ap.add_argument("--model", default=os.path.join(ROOT, "models", "rf.pkl"))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "raw"))
    ap.add_argument("--jitter", type=float, default=0.3,
                    help="biến thiên cường độ traffic theo seed (±)")
    ap.add_argument("--resume", action="store_true",
                    help="bỏ qua run đã có meta.json và không FAILED")
    ap.add_argument("--retries", type=int, default=1)
    args = ap.parse_args()

    if os.geteuid() != 0:
        sys.exit('Phải chạy bằng sudo: sudo env "PATH=$PATH" python3 ...')
    need_model = any(b in ("B2", "B3") for b in args.baselines)
    if need_model and not os.path.exists(args.model):
        sys.exit("Thiếu model %s — train ở tuần 7 trước (ml/train_eval.py)."
                 % args.model)
    owner = os.environ.get("SUDO_UID") and "%s:%s" % (
        os.environ["SUDO_UID"], os.environ.get("SUDO_GID", os.environ["SUDO_UID"]))
    os.makedirs(args.out, exist_ok=True)

    jobs = [(s, b, k) for s in args.scenarios for b in args.baselines
            for k in args.seeds]
    print("Tổng số run: %d -> %s" % (len(jobs), args.out), flush=True)
    t0 = time.time()
    ok = 0
    for i, (scn, base, seed) in enumerate(jobs, 1):
        d = os.path.join(args.out, "%s_%s_seed%d" % (scn, base, seed))
        if args.resume and os.path.exists(os.path.join(d, "meta.json")) \
                and not os.path.exists(os.path.join(d, "FAILED")):
            ok += 1
            continue
        print("[%d/%d] đã chạy %.0f phút" % (i, len(jobs), (time.time() - t0) / 60),
              flush=True)
        for attempt in range(1 + args.retries):
            try:
                if run_one(scn, base, seed, args.model, args.out, args.jitter, owner):
                    ok += 1
                    break
            except Exception as e:
                print("[lỗi] %s/%s/seed%d: %s" % (scn, base, seed, e), flush=True)
            print("  thử lại (%d)..." % (attempt + 1), flush=True)
    print("\nXong ma trận: %d/%d run OK sau %.0f phút. Tổng hợp: "
          "python3 analysis/aggregate.py --raw %s" %
          (ok, len(jobs), (time.time() - t0) / 60, args.out), flush=True)


if __name__ == "__main__":
    main()
