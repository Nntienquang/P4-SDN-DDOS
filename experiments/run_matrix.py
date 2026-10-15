#!/usr/bin/env python3
"""
run_matrix.py — Chạy toàn bộ ma trận thí nghiệm S × B × seed (tuần 10).

Với mỗi tổ hợp: dựng Mininet + BMv2, chạy detector đúng cấu hình baseline,
chạy scenario, thu log vào results/raw/<SCN>_<B>_seed<k>/, rồi dọn (mn -c).

Baseline:
  B0 = không phát hiện, không mitigation        (detector --no-mitigation, pred luôn 0*)
  B1 = static threshold trên packet_rate         (detector không --model)
  B2 = model, mitigation KHÔNG feedback          (detector --model, policy mặc định)
  B3 = model, mitigation đầy đủ (feedback)        (detector --model --feedback)

* B0 vẫn chạy detector để GHI LOG feature/pred phục vụ so sánh, nhưng không áp
  rule (so sánh "không phòng thủ").

PHẢI chạy bằng sudo trên testbed VM. Đây là orchestrator nặng; chạy qua đêm cho
đủ seed. Có thể chạy từng phần bằng --scenarios/--baselines/--seeds.

Ví dụ:
  sudo -E python3 experiments/run_matrix.py --seeds 0 1 2 \
       --scenarios S1 S2 S3 S4 S5 --baselines B0 B1 B2 B3
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, "build")
P4INFO = os.path.join(BUILD, "telemetry.p4.p4info.txtpb")
BMV2 = os.path.join(BUILD, "telemetry.json")


def detector_args(baseline, model_path):
    """Trả về list tham số thêm cho detector theo baseline."""
    if baseline == "B0":
        return ["--no-mitigation"]            # ghi log, không áp rule
    if baseline == "B1":
        return []                              # threshold, có mitigation
    if baseline == "B2":
        return ["--model", model_path]
    if baseline == "B3":
        return ["--model", model_path, "--feedback"]
    raise ValueError(baseline)


def run_one(scn, baseline, seed, model_path, duration_pad=20):
    outdir = os.path.join(ROOT, "results", "raw",
                          "%s_%s_seed%d" % (scn, baseline, seed))
    os.makedirs(outdir, exist_ok=True)
    scn_file = os.path.join(ROOT, "configs", "scenarios", scn + ".yaml")
    print("\n===== %s / %s / seed %d =====" % (scn, baseline, seed))

    subprocess.call(["mn", "-c"], stderr=subprocess.DEVNULL)

    # 1) khởi động mạng + scenario ở tiến trình nền
    net = subprocess.Popen(
        ["python3", os.path.join(ROOT, "mininet", "run_net.py"),
         "--p4info", P4INFO, "--bmv2", BMV2,
         "--runtime", os.path.join(ROOT, "mininet", "s1-runtime.json"),
         "--scenario", scn_file],
        cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT))
    time.sleep(8)   # chờ mạng + pipeline sẵn sàng

    # 2) detector (nền) ghi realtime.csv
    det = subprocess.Popen(
        ["python3", os.path.join(ROOT, "controller", "detector.py"),
         "--p4info", P4INFO, "--bmv2", BMV2,
         "--poll", "1.0", "--out", os.path.join(outdir, "realtime.csv")]
        + detector_args(baseline, model_path),
        cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT))

    # 3) chờ scenario xong
    net.wait()
    det.terminate()
    try:
        det.wait(timeout=10)
    except Exception:
        det.kill()

    # 4) gom log của run này
    for name in ("probe.csv", "ground_truth.json"):
        src = os.path.join(ROOT, "logs", name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(outdir, name))
    # ghi metadata
    with open(os.path.join(outdir, "meta.txt"), "w") as f:
        f.write("scenario=%s baseline=%s seed=%d\n" % (scn, baseline, seed))
        f.write("time=%s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    subprocess.call(["mn", "-c"], stderr=subprocess.DEVNULL)
    print("  -> lưu", outdir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", nargs="+", default=["S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--baselines", nargs="+", default=["B0", "B1", "B2", "B3"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--model", default=os.path.join(ROOT, "models", "rf.pkl"))
    args = ap.parse_args()

    if os.geteuid() != 0:
        sys.exit("Phải chạy bằng sudo (Mininet cần quyền root).")
    need_model = any(b in ("B2", "B3") for b in args.baselines)
    if need_model and not os.path.exists(args.model):
        sys.exit("Thiếu model %s — train ở tuần 7 trước (ml/train_eval lưu .pkl)."
                 % args.model)

    total = len(args.scenarios) * len(args.baselines) * len(args.seeds)
    print("Tổng số run: %d" % total)
    for scn in args.scenarios:
        for base in args.baselines:
            if base == "B0" and scn == "S6":
                continue   # S6 không cần B0 (xem ma trận đề cương)
            for seed in args.seeds:
                try:
                    run_one(scn, base, seed, args.model)
                except Exception as e:
                    print("[lỗi] %s/%s/seed%d: %s" % (scn, base, seed, e))
    print("\nXong ma trận. Tổng hợp: python3 analysis/aggregate.py")


if __name__ == "__main__":
    main()
