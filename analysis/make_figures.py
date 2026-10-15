"""
make_figures.py — Vẽ hình từ results/summary.csv (tuần 11).

Sinh:
  - figures/lsr_by_baseline_<SCN>.png  : LSR ± CI95 theo baseline (trục User)
  - figures/tradeoff_<SCN>.png         : LSR vs FPR theo baseline (Pareto)

Chạy:  python3 analysis/make_figures.py --summary results/summary.csv --scn S5
"""
import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def load_summary(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def bar_lsr(rows, scn, outdir):
    sub = [r for r in rows if r["scenario"] == scn]
    sub.sort(key=lambda r: r["baseline"])
    if not sub:
        return None
    labels = [r["baseline"] for r in sub]
    means = [_f(r["lsr_mean"]) or 0 for r in sub]
    cis = [_f(r["lsr_ci95"]) or 0 for r in sub]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, means, yerr=cis, capsize=5, color="#3b6ea5")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Legitimate Success Rate")
    ax.set_title("LSR theo baseline — %s" % scn)
    for i, m in enumerate(means):
        ax.text(i, m + 0.02, "%.2f" % m, ha="center", fontsize=9)
    path = os.path.join(outdir, "lsr_by_baseline_%s.png" % scn)
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)
    return path


def scatter_tradeoff(rows, scn, outdir):
    sub = [r for r in rows if r["scenario"] == scn]
    if not sub:
        return None
    fig, ax = plt.subplots(figsize=(6, 4))
    for r in sub:
        x = _f(r["fpr_mean"]); y = _f(r["lsr_mean"])
        if x is None or y is None:
            continue
        ax.scatter(x, y, s=60)
        ax.annotate(r["baseline"], (x, y), textcoords="offset points",
                    xytext=(6, 4), fontsize=9)
    ax.set_xlabel("FPR (báo nhầm)")
    ax.set_ylabel("LSR (giữ người dùng hợp lệ)")
    ax.set_title("Trade-off LSR vs FPR — %s" % scn)
    ax.grid(True, alpha=0.3)
    path = os.path.join(outdir, "tradeoff_%s.png" % scn)
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="results/summary.csv")
    ap.add_argument("--scn", default="S5")
    ap.add_argument("--outdir", default="figures")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    rows = load_summary(args.summary)
    for fn in (bar_lsr, scatter_tradeoff):
        p = fn(rows, args.scn, args.outdir)
        if p:
            print("Đã vẽ:", p)


if __name__ == "__main__":
    main()
