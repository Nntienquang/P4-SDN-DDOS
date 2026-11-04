#!/usr/bin/env python3
"""
eval_baseline.py — Tuần 6: đánh giá baseline threshold + EWMA trên dataset.

Mục tiêu CHÍNH của tuần 6 không phải "đạt accuracy cao" mà là ĐO ĐIỂM YẾU của
baseline theo volume, đặc biệt **Flash-FPR** = tỉ lệ window Flash Crowd bị báo
nhầm thành DDoS. Con số này là bằng chứng cho RQ2: ngưỡng/EWMA chỉ nhìn
packet_rate nên không phân biệt được "đông người thật" với "tấn công". Tuần 7
máy học sẽ phải đánh bại đúng con số này.

Chống rò rỉ: chia theo run_id. Ngưỡng tĩnh được fit từ phần NORMAL của các run
train, rồi đánh giá trên các run test chưa thấy. EWMA chạy tuần tự trong từng
run test (tự thích nghi, không cần fit).

Thuần thư viện chuẩn (csv/random/math) — chạy nhẹ trên máy yếu, không cần
pandas/sklearn. Có thể copy data/*.csv sang laptop rồi chạy offline.

Chạy:
  python3 baseline/eval_baseline.py --data data/uniflash_v01.csv --out experiments/week6
"""
import argparse
import csv
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "controller"))
sys.path.insert(0, os.path.join(ROOT, "metrics"))

from detectors import StaticThreshold, EWMA        # noqa: E402
import service_metrics as M                        # noqa: E402

# normal/flash = lành tính (0); mọi pha tấn công = dương (1)
LABEL01 = {"normal": 0, "flash": 0, "ddos": 1, "syn": 1, "udp": 1}


def load_rows(path, feature="packet_rate", drop_transition=True):
    """Đọc dataset -> list dict {run_id, label, y, value, timestamp}."""
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if drop_transition and str(r.get("transition", "0")) == "1":
                continue
            lab = r["label"]
            if lab not in LABEL01:
                raise ValueError("Nhãn lạ: %s" % lab)
            rows.append({
                "run_id": r["run_id"],
                "label": lab,
                "y": LABEL01[lab],
                "value": float(r[feature]),
                "timestamp": float(r.get("timestamp", 0) or 0),
            })
    if not rows:
        raise ValueError("Dataset rỗng sau khi loại transition: %s" % path)
    return rows


def group_split(rows, test_frac=0.3, seed=42):
    """Chia theo run_id. Trả về (train_rows, test_rows, train_ids, test_ids)."""
    ids = sorted({r["run_id"] for r in rows})
    if len(ids) < 2:
        # chỉ 1 run: không tách được -> fit và đánh giá trên cùng tập (có leakage)
        return rows, rows, ids, ids
    rng = random.Random(seed)
    rng.shuffle(ids)
    n_test = max(1, int(round(test_frac * len(ids))))
    test_ids = set(ids[:n_test])
    train = [r for r in rows if r["run_id"] not in test_ids]
    test = [r for r in rows if r["run_id"] in test_ids]
    return train, test, sorted(set(ids) - test_ids), sorted(test_ids)


def fit_threshold(train_rows, pct=99, k=1.2):
    """Fit ngưỡng tĩnh từ packet_rate của các window NORMAL trong train."""
    normal_vals = [r["value"] for r in train_rows if r["label"] == "normal"]
    if not normal_vals:
        # không có normal riêng -> lấy phân vị thấp của toàn train làm nền
        normal_vals = sorted(r["value"] for r in train_rows)[: max(1, len(train_rows)//3)]
    return StaticThreshold.fit_from_normal(normal_vals, pct=pct, k=k)


def ewma_predict(test_rows, alpha=0.2, k=3.0, warmup=10):
    """Chạy EWMA TUẦN TỰ trong từng run (sắp theo timestamp). Trả về list pred
    cùng thứ tự với test_rows."""
    by_run = {}
    for i, r in enumerate(test_rows):
        by_run.setdefault(r["run_id"], []).append(i)
    preds = [0] * len(test_rows)
    for rid, idxs in by_run.items():
        idxs_sorted = sorted(idxs, key=lambda i: test_rows[i]["timestamp"])
        det = EWMA(alpha=alpha, k=k, warmup=warmup)
        for i in idxs_sorted:
            preds[i] = det.predict(test_rows[i]["value"])
    return preds


def evaluate(test_rows, preds):
    """Gộp các chỉ số tuần 6 cho một baseline."""
    y_true = [r["y"] for r in test_rows]
    labels = [r["label"] for r in test_rows]
    sec = M.security_metrics(y_true, preds)
    flash_fpr = M.flash_false_positive_rate(labels, preds)
    # FPR riêng cho normal (loại flash ra để thấy rõ)
    norm_idx = [i for i, l in enumerate(labels) if l == "normal"]
    normal_fpr = (sum(preds[i] for i in norm_idx) / len(norm_idx)
                  if norm_idx else None)
    n_flash = sum(1 for l in labels if l == "flash")
    return {
        "recall_ddos": sec["recall"],
        "precision": sec["precision"],
        "f1": sec["f1"],
        "fpr_overall": sec["fpr"],
        "normal_fpr": normal_fpr,
        "flash_fpr": flash_fpr,
        "n_flash_windows": n_flash,
        "tp": sec["tp"], "fp": sec["fp"], "tn": sec["tn"], "fn": sec["fn"],
    }


def _fmt(x):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return "%.3f" % x
    return str(x)


def main():
    ap = argparse.ArgumentParser(description="Đánh giá baseline threshold/EWMA (tuần 6)")
    ap.add_argument("--data", default="data/uniflash_v01.csv")
    ap.add_argument("--out", default="experiments/week6")
    ap.add_argument("--feature", default="packet_rate")
    ap.add_argument("--test-frac", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pct", type=float, default=99.0)
    ap.add_argument("--k", type=float, default=1.2, help="hệ số nhân ngưỡng tĩnh")
    ap.add_argument("--ewma-alpha", type=float, default=0.2)
    ap.add_argument("--ewma-k", type=float, default=3.0)
    args = ap.parse_args()

    rows = load_rows(args.data, feature=args.feature)
    train, test, train_ids, test_ids = group_split(rows, args.test_frac, args.seed)
    leaky = (train_ids == test_ids)

    # Baseline B1: ngưỡng tĩnh
    st = fit_threshold(train, pct=args.pct, k=args.k)
    th_preds = [st.predict(r["value"]) for r in test]
    th_res = evaluate(test, th_preds)
    th_res["threshold_value"] = st.threshold

    # Baseline adaptive: EWMA
    ew_preds = ewma_predict(test, alpha=args.ewma_alpha, k=args.ewma_k)
    ew_res = evaluate(test, ew_preds)

    os.makedirs(args.out, exist_ok=True)
    cols = ["detector", "recall_ddos", "precision", "f1", "fpr_overall",
            "normal_fpr", "flash_fpr", "n_flash_windows",
            "tp", "fp", "tn", "fn"]
    csv_path = os.path.join(args.out, "baseline_report.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for name, res in (("static_threshold", th_res), ("ewma", ew_res)):
            w.writerow([name] + [_fmt(res.get(c)) for c in cols[1:]])

    # Bản tóm tắt markdown cho báo cáo
    md = []
    md.append("# Tuần 6 — Kết quả baseline (threshold vs EWMA)\n")
    md.append("- Dataset: `%s` (%d window sau khi loại transition)" % (args.data, len(rows)))
    md.append("- Feature dùng: `%s` | chia theo run_id, test_frac=%.2f, seed=%d" %
              (args.feature, args.test_frac, args.seed))
    md.append("- Run train: %s" % ", ".join(train_ids))
    md.append("- Run test : %s" % ", ".join(test_ids))
    if leaky:
        md.append("\n> ⚠️ Chỉ có 1 run nên fit và đánh giá trên cùng tập "
                  "(kết quả lạc quan). Thu thêm run để tách train/test.")
    md.append("\n| Detector | Recall DDoS | Precision | F1 | FPR normal | **Flash-FPR** |")
    md.append("| --- | --- | --- | --- | --- | --- |")
    md.append("| Static threshold (B1) | %s | %s | %s | %s | **%s** |" % (
        _fmt(th_res["recall_ddos"]), _fmt(th_res["precision"]), _fmt(th_res["f1"]),
        _fmt(th_res["normal_fpr"]), _fmt(th_res["flash_fpr"])))
    md.append("| EWMA (adaptive) | %s | %s | %s | %s | **%s** |" % (
        _fmt(ew_res["recall_ddos"]), _fmt(ew_res["precision"]), _fmt(ew_res["f1"]),
        _fmt(ew_res["normal_fpr"]), _fmt(ew_res["flash_fpr"])))
    md.append("\nNgưỡng tĩnh fit được: **%.1f pkt/s** (phân vị %.0f × %.2f)." %
              (st.threshold, args.pct, args.k))
    md.append("\n**Đọc kết quả:** Flash-FPR cao = baseline báo nhầm flash crowd "
              "thành tấn công. Đây là điểm yếu tuần 7 (máy học) phải khắc phục: "
              "giữ Recall DDoS cao mà Flash-FPR thấp.")
    md_path = os.path.join(args.out, "baseline_report.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md) + "\n")

    # In ra màn hình
    print("\n".join(md))
    print("\nĐã ghi: %s" % csv_path)
    print("Đã ghi: %s" % md_path)
    if th_res["flash_fpr"] is None:
        print("\n(Lưu ý: dataset chưa có window FLASH -> chưa đo được Flash-FPR. "
              "Chạy thêm scenario S2 (flash) rồi gom lại.)")


if __name__ == "__main__":
    main()
