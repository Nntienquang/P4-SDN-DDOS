#!/usr/bin/env python3
"""
build_dataset.py — Tuần 6: gom nhiều LẦN CHẠY thành MỘT dataset có nhãn.

Mỗi lần chạy (run) để lại một thư mục chứa:
  realtime.csv       <- controller/detector.py --no-mitigation ghi ra
  ground_truth.json  <- mininet/run_net.py ghi khi chạy scenario

Script này:
  1) đọc ground_truth.json -> biết pha nào chạy lúc nào (nhãn thật),
  2) gán nhãn cho từng window trong realtime.csv theo thời điểm so với t0 của
     scenario: rel = wall - t0 (cột 'wall' epoch do detector ghi). Log cũ chưa
     có 'wall' thì dùng 'elapsed' (lệch vài giây vì detector khởi động khác
     lúc scenario). KHÔNG suy nhãn từ detector — tránh rò rỉ nhãn,
  3) đánh dấu transition=1 cho window sát ranh giới pha (nên loại khi train),
  4) nối tất cả run lại, ghi data/uniflash_v01.csv.

Dùng CÙNG quy tắc nhãn với analysis/compute_metrics.py (attack > flash > normal).

Thuần thư viện chuẩn (csv/json) — KHÔNG cần pandas, chạy nhẹ trên máy yếu, hoặc
copy các CSV sang laptop rồi gom offline để đỡ tốn tài nguyên máy ảo.

Ví dụ:
  # gom mọi run trong results/raw (dấu * do shell mở rộng)
  python3 ml/build_dataset.py --runs results/raw/* --out data/uniflash_v01.csv

  # gom một run vừa chạy ở thư mục logs, tự đặt tên run
  python3 ml/build_dataset.py --runs logs --run-id run1_S2 \
      --out data/uniflash_v01.csv --append
"""
import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "controller"))
from features import FEATURE_NAMES  # noqa: E402

# Giống analysis/compute_metrics.py: pha tấn công coi là lớp dương.
ATTACK_KINDS = {"syn", "udp"}

# Cột định danh/ngữ cảnh đứng trước các feature (khớp data/DATA_DICTIONARY.md).
META_COLS = ["timestamp", "run_id", "scenario", "label", "transition"]
OUT_COLS = META_COLS + FEATURE_NAMES


def label_at(elapsed, phases):
    """Nhãn chuỗi tại thời điểm 'elapsed' (giây từ đầu scenario).

    Ưu tiên attack > flash > normal khi nhiều pha chồng nhau (vd S5 flash+ddos).
    """
    active = [ph["kind"] for ph in phases if ph["start"] <= elapsed < ph["end"]]
    if any(k in ATTACK_KINDS for k in active):
        return "ddos"
    if "flash" in active:
        return "flash"
    if "normal" in active:
        return "normal"
    return "normal"


def is_transition(elapsed, phases, margin):
    """True nếu 'elapsed' nằm trong 'margin' giây quanh BẤT KỲ ranh giới pha nào
    (điểm start/end). Window như vậy nửa pha này nửa pha kia -> nhiễu nhãn."""
    for ph in phases:
        if abs(elapsed - ph["start"]) < margin or abs(elapsed - ph["end"]) < margin:
            return 1
    return 0


def _read_realtime(path):
    """Đọc realtime.csv -> list dict. Cần cột 'elapsed','t' + các FEATURE_NAMES."""
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        have = set(reader.fieldnames or [])
        missing = [c for c in (["elapsed"] + FEATURE_NAMES) if c not in have]
        if missing:
            raise ValueError("%s thiếu cột: %s" % (path, missing))
        for r in reader:
            rows.append(r)
    return rows


def _infer_margin(rows):
    """Ước lượng nửa chu kỳ poll từ khoảng cách 'elapsed' trung vị (mặc định 0.6)."""
    els = sorted(float(r["elapsed"]) for r in rows)
    diffs = [b - a for a, b in zip(els, els[1:]) if b - a > 0]
    if not diffs:
        return 0.6
    diffs.sort()
    poll = diffs[len(diffs) // 2]
    # biên = 1 chu kỳ poll: window kéo dài poll giây nên mọi window chạm ranh
    # giới pha đều là "nửa nọ nửa kia"
    return max(0.6, poll)


def process_run(run_dir, run_id=None, margin=None):
    """Trả về (list[dict] hàng đã gán nhãn, scenario_name)."""
    gt_path = os.path.join(run_dir, "ground_truth.json")
    rt_path = os.path.join(run_dir, "realtime.csv")
    if not os.path.exists(gt_path):
        raise FileNotFoundError("Không thấy %s (thiếu ground_truth.json)" % gt_path)
    if not os.path.exists(rt_path):
        raise FileNotFoundError("Không thấy %s (thiếu realtime.csv)" % rt_path)

    gt = json.load(open(gt_path))
    phases = gt.get("phases", [])
    scenario = gt.get("name", os.path.basename(run_dir.rstrip("/")))
    rid = run_id or os.path.basename(run_dir.rstrip("/")) or scenario

    rows = _read_realtime(rt_path)
    m = margin if margin is not None else _infer_margin(rows)
    t0 = gt.get("t0")
    use_wall = bool(rows) and "wall" in rows[0] and t0
    duration = gt.get("duration") or max([ph["end"] for ph in phases] or [0])

    out = []
    for r in rows:
        el = float(r["wall"]) - t0 if use_wall else float(r["elapsed"])
        if use_wall and (el < 0 or el > duration):
            continue      # window trước/sau scenario: không có nhãn đáng tin
        rec = {
            "timestamp": r.get("t", el),
            "run_id": rid,
            "scenario": scenario,
            "label": label_at(el, phases),
            "transition": is_transition(el, phases, m),
        }
        for name in FEATURE_NAMES:
            rec[name] = r[name]
        out.append(rec)
    return out, scenario


def main():
    ap = argparse.ArgumentParser(description="Gom run -> dataset có nhãn (tuần 6)")
    ap.add_argument("--runs", nargs="+", required=True,
                    help="Một hoặc nhiều thư mục run (mỗi thư mục có "
                         "realtime.csv + ground_truth.json)")
    ap.add_argument("--out", default="data/uniflash_v01.csv")
    ap.add_argument("--run-id", default=None,
                    help="Chỉ dùng khi --runs là MỘT thư mục: tự đặt run_id")
    ap.add_argument("--margin", type=float, default=None,
                    help="Biên transition quanh ranh giới pha (giây). Mặc định: "
                         "tự suy từ chu kỳ poll")
    ap.add_argument("--append", action="store_true",
                    help="Nối vào file --out đã có thay vì ghi đè")
    args = ap.parse_args()

    def _usable(d):
        return (os.path.isdir(d) and not os.path.exists(os.path.join(d, "FAILED"))
                and os.path.exists(os.path.join(d, "ground_truth.json"))
                and os.path.exists(os.path.join(d, "realtime.csv")))
    # run hỏng (FAILED) hoặc đang chạy dở (chưa có ground truth) -> bỏ qua
    run_dirs = [d for d in args.runs if _usable(d)]
    skipped = [d for d in args.runs if d not in run_dirs]
    if not run_dirs:
        sys.exit("Không có thư mục run hợp lệ trong --runs: %s" % args.runs)
    if args.run_id and len(run_dirs) > 1:
        sys.exit("--run-id chỉ dùng khi --runs là một thư mục duy nhất.")

    all_rows, summary = [], []
    for d in run_dirs:
        rid = args.run_id if len(run_dirs) == 1 else None
        rows, scenario = process_run(d, run_id=rid, margin=args.margin)
        all_rows.extend(rows)
        n_tr = sum(r["transition"] for r in rows)
        by = {}
        for r in rows:
            by[r["label"]] = by.get(r["label"], 0) + 1
        summary.append((rows[0]["run_id"] if rows else "?", scenario,
                        len(rows), n_tr, by))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    mode = "a" if (args.append and os.path.exists(args.out)) else "w"
    write_header = not (mode == "a")
    with open(args.out, mode, newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS)
        if write_header:
            w.writeheader()
        for r in all_rows:
            w.writerow(r)

    print("== build_dataset: %d run -> %s (%s) ==" %
          (len(run_dirs), args.out, "nối thêm" if mode == "a" else "ghi mới"))
    for rid, scn, n, ntr, by in summary:
        dist = " ".join("%s=%d" % (k, v) for k, v in sorted(by.items()))
        print("  %-14s %-6s %4d window (transition %d) | %s" %
              (rid, scn, n, ntr, dist))
    if skipped:
        print("  (bỏ qua %d mục không dùng được: %s)" % (len(skipped), ", ".join(skipped)))
    print("Tổng: %d window có nhãn." % len(all_rows))
    print("Bước tiếp: python3 baseline/eval_baseline.py --data %s "
          "--out experiments/week6" % args.out)


if __name__ == "__main__":
    main()
