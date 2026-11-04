"""
make_figures.py — Vẽ hình cho báo cáo (tuần 11) từ results/summary.csv,
results/raw/* và experiments/week7.

Sinh (thư mục --outdir, mặc định figures/):
  fig1_lsr_attack.png      LSR của probe TRONG pha tấn công, theo scenario × baseline
  fig2_user_attack.png     Tỉ lệ thành công của mọi client hợp lệ trong pha tấn công
  fig3_flash.png           Flash Crowd: tỉ lệ thành công của user flash + Flash-FPR
  fig4_timeline_S5.png     Diễn biến LSR theo thời gian ở S5 (1 seed), mỗi baseline 1 đường
  fig5_detection_latency.png  Độ trễ phát hiện / bắt đầu mitigation
  fig6_model_compare.png   So sánh phương pháp offline (tuần 7): Recall vs Flash-FPR
  fig7_feature_importance.png  Độ quan trọng feature (RandomForest)

Màu: baseline B0..B3 luôn giữ cùng một màu (theo thực thể, không theo thứ hạng),
thứ tự slot cố định của palette tham chiếu (blue, orange, aqua, yellow).

Chạy:  python3 analysis/make_figures.py --summary results/summary.csv \
           --raw results/raw --week7 experiments/week7 --outdir figures
"""
import argparse
import csv
import glob
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT2 = "#52514e"
GRID = "#e4e3df"
BASE_COLOR = {"B0": "#2a78d6", "B1": "#eb6834", "B2": "#1baf7a", "B3": "#eda100"}
BASE_NAME = {"B0": "B0 không phòng thủ", "B1": "B1 threshold + RL thô",
             "B2": "B2 ML + RL thô", "B3": "B3 ML + chặn chọn lọc + feedback"}
SCN_NAME = {"S1": "S1 Normal", "S2": "S2 Flash", "S3": "S3 SYN flood",
            "S4": "S4 UDP flood", "S5": "S5 Flash+DDoS", "S6": "S6 Nền đổi"}
PHASE_FILL = {"ddos": "#e3494822", "flash": "#6250d618"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT2, "text.color": TEXT,
    "xtick.color": TEXT2, "ytick.color": TEXT2, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10, "axes.titlesize": 11, "legend.frameon": False,
})


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_summary(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def grouped_bar(rows, scns, metric, ylabel, title, path, baselines=("B0", "B1", "B2", "B3"),
                ylim=(0, 1.05), fmt="%.2f"):
    idx = {(r["scenario"], r["baseline"]): r for r in rows}
    scns = [s for s in scns if any((s, b) in idx for b in baselines)]
    if not scns:
        return None
    fig, ax = plt.subplots(figsize=(1.9 * len(scns) + 2.5, 3.8))
    n = len(baselines)
    width = 0.8 / n
    for j, b in enumerate(baselines):
        xs, ys, es = [], [], []
        for i, s in enumerate(scns):
            r = idx.get((s, b))
            m = _f(r.get(metric + "_mean")) if r else None
            if m is None:
                continue
            xs.append(i + (j - (n - 1) / 2) * width)
            ys.append(m)
            es.append(_f(r.get(metric + "_ci95")) or 0)
        # khe 2px giữa các cột: viền màu nền
        ax.bar(xs, ys, width * 0.92, yerr=es, color=BASE_COLOR[b], label=BASE_NAME[b],
               edgecolor=SURFACE, linewidth=1, error_kw={"ecolor": TEXT2, "lw": 1,
                                                          "capsize": 3})
        if b == "B3" or b == "B0":   # nhãn trực tiếp chọn lọc: B0 và B3
            for x, y in zip(xs, ys):
                ax.text(x, y + 0.03 * (ylim[1] - ylim[0]), fmt % y, ha="center",
                        fontsize=8, color=TEXT2)
    ax.set_xticks(range(len(scns)))
    ax.set_xticklabels([SCN_NAME.get(s, s) for s in scns])
    ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def timeline(raw_dir, scn, seed, path, baselines=("B0", "B1", "B2", "B3"), bin_s=3.0):
    import compute_metrics as CM
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    phases = None
    drawn = 0
    for b in baselines:
        d = os.path.join(raw_dir, "%s_%s_seed%d" % (scn, b, seed))
        if not os.path.isdir(d) or os.path.exists(os.path.join(d, "FAILED")):
            continue
        gt = json.load(open(os.path.join(d, "ground_truth.json")))
        phases = phases or gt["phases"]
        probe = CM.load_probe(d, gt)
        dur = gt.get("duration", 150)
        xs, ys = [], []
        t = 0.0
        while t < dur:
            sel = [p for p in probe if t <= p["rel"] < t + bin_s]
            if sel:
                xs.append(t + bin_s / 2)
                ys.append(sum(p["ok"] for p in sel) / len(sel))
            t += bin_s
        ax.plot(xs, ys, color=BASE_COLOR[b], lw=2, label=BASE_NAME[b])
        drawn += 1
    if not drawn:
        plt.close(fig)
        return None
    for ph in phases or []:
        kind = "ddos" if ph["kind"] in ("syn", "udp") else ph["kind"]
        if kind in PHASE_FILL:
            ax.axvspan(ph["start"], ph["end"], color=PHASE_FILL[kind], lw=0)
    # chú thích pha
    seen = set()
    for ph in phases or []:
        kind = "ddos" if ph["kind"] in ("syn", "udp") else ph["kind"]
        if kind in PHASE_FILL and kind not in seen:
            seen.add(kind)
            # 2 tầng chữ để nhãn các pha chồng nhau (S5) không đè lên nhau
            ax.text(ph["start"] + 1, 1.07 if kind == "flash" else 1.015,
                    "pha tấn công" if kind == "ddos" else "pha Flash Crowd",
                    fontsize=8, color=TEXT2)
    ax.set_ylim(-0.03, 1.14)
    ax.set_xlabel("Thời gian từ đầu kịch bản (s)")
    ax.set_ylabel("Tỉ lệ request probe thành công")
    ax.set_title("Diễn biến dịch vụ — %s, seed %d (bin %.0fs)" %
                 (SCN_NAME.get(scn, scn), seed, bin_s), loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def model_compare(week7_dir, path):
    p = os.path.join(week7_dir, "model_compare.csv")
    if not os.path.exists(p):
        return None
    rows = list(csv.DictReader(open(p)))
    names = [r["method"] for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, metric, title in ((axes[0], "recall", "Recall DDoS (cao = tốt)"),
                              (axes[1], "flash_fpr", "Flash-FPR (thấp = tốt)")):
        vals = [_f(r[metric]) or 0 for r in rows]
        ax.barh(names, vals, color="#2a78d6", height=0.55, edgecolor=SURFACE)
        for i, v in enumerate(vals):
            ax.text(v + 0.02, i, "%.2f" % v, va="center", fontsize=8, color=TEXT2)
        ax.set_xlim(0, 1.15)
        ax.set_title(title, loc="left")
        ax.grid(axis="y", visible=False)
    axes[0].invert_yaxis()
    fig.suptitle("Đánh giá offline trên dữ liệu testbed (chia theo run)", x=0.01,
                 ha="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def feature_importance(week7_dir, path, model="RandomForest"):
    p = os.path.join(week7_dir, "feature_importance.json")
    if not os.path.exists(p):
        return None
    imp = json.load(open(p)).get(model)
    if not imp:
        return None
    items = sorted(imp.items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.barh([k for k, _ in items], [v for _, v in items], color="#2a78d6",
            height=0.55, edgecolor=SURFACE)
    for i, (_, v) in enumerate(items):
        ax.text(v + 0.005, i, "%.2f" % v, va="center", fontsize=8, color=TEXT2)
    ax.set_title("Độ quan trọng feature — %s" % model, loc="left")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="results/summary.csv")
    ap.add_argument("--raw", default="results/raw")
    ap.add_argument("--week7", default="experiments/week7")
    ap.add_argument("--timeline-scn", default="S5")
    ap.add_argument("--timeline-seed", type=int, default=10)
    ap.add_argument("--outdir", default="figures")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    out = []
    if os.path.exists(args.summary):
        rows = load_summary(args.summary)
        out.append(grouped_bar(rows, ["S3", "S4", "S5"], "lsr_attack",
                               "LSR probe trong pha tấn công",
                               "Giữ dịch vụ cho người dùng hợp lệ khi bị DDoS",
                               os.path.join(args.outdir, "fig1_lsr_attack.png")))
        out.append(grouped_bar(rows, ["S3", "S4", "S5"], "user_sr_attack",
                               "Tỉ lệ thành công client hợp lệ",
                               "Mọi client hợp lệ (h1–h8) trong pha tấn công",
                               os.path.join(args.outdir, "fig2_user_attack.png")))
        out.append(grouped_bar(rows, ["S2", "S5"], "flash_sr",
                               "Tỉ lệ thành công user Flash Crowd",
                               "Flash Crowd hợp lệ có bị chặn nhầm không?",
                               os.path.join(args.outdir, "fig3_flash.png")))
        out.append(grouped_bar(rows, ["S1", "S2", "S5", "S6"], "fpr",
                               "FPR theo window (thấp = tốt)",
                               "Báo động nhầm trên traffic hợp lệ",
                               os.path.join(args.outdir, "fig3b_fpr.png"),
                               baselines=("B1", "B2", "B3")))
        out.append(grouped_bar(rows, ["S3", "S4", "S5"], "mitigation_latency_s",
                               "Giây từ lúc tấn công bắt đầu",
                               "Độ trễ tới khi bắt đầu mitigation (thấp = tốt)",
                               os.path.join(args.outdir, "fig5_mitigation_latency.png"),
                               baselines=("B1", "B2", "B3"), ylim=(0, 12), fmt="%.1f"))
    out.append(timeline(args.raw, args.timeline_scn, args.timeline_seed,
                        os.path.join(args.outdir, "fig4_timeline_%s.png" % args.timeline_scn)))
    out.append(model_compare(args.week7, os.path.join(args.outdir, "fig6_model_compare.png")))
    out.append(feature_importance(args.week7, os.path.join(args.outdir,
                                                           "fig7_feature_importance.png")))
    for p in out:
        if p:
            print("Đã vẽ:", p)


if __name__ == "__main__":
    main()
