"""
weekly_figures.py — Hình minh hoạ kết quả TỪNG TUẦN (4 → 11) để đưa vào báo cáo.

Lưu vào figures/tuanNN/*.png và ghi figures/README.md (chú thích từng hình).
Chỉ đọc dữ liệu đã có; tuần nào thiếu dữ liệu thì bỏ qua và in cảnh báo.

  Tuần 4  controller đọc counter real-time        (results/dataset_raw/S1, S3)
  Tuần 5  4 loại traffic có nhãn                  (results/dataset_raw/S1..S4)
  Tuần 6  dataset + baseline threshold/EWMA        (data/uniflash_v01.csv, experiments/week6)
  Tuần 7  so sánh model, feature, confusion        (experiments/week7)
  Tuần 8  phát hiện online bằng model              (results/raw/S3_B2_*, S5_B2_*)
  Tuần 9  mitigation chọn lọc giữ LSR              (results/raw/S5_B3_*, S3_B3_*)
  Tuần 10 ma trận thí nghiệm + CI95                (results/summary.csv)
  Tuần 11 tổng kết so sánh baseline                (results/summary.csv, results/raw)

Chạy:  python3 analysis/weekly_figures.py            (mặc định ghi vào figures/)
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
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import compute_metrics as CM   # noqa: E402
import make_figures as MF      # noqa: E402  (dùng chung style + màu baseline)

SURFACE, TEXT2 = MF.SURFACE, MF.TEXT2
# màu theo NHÃN traffic (thực thể khác với baseline): thứ tự slot cố định
LABEL_COLOR = {"normal": "#2a78d6", "flash": "#eb6834", "ddos": "#1baf7a"}
LABEL_NAME = {"normal": "Normal", "flash": "Flash Crowd (hợp lệ)", "ddos": "DDoS"}
SERIES = "#2a78d6"
CAPTIONS = []


def save(fig, outdir, week, name, caption):
    d = os.path.join(outdir, "tuan%02d" % week)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    CAPTIONS.append((week, os.path.relpath(path, outdir), caption))
    print("  tuần %d: %s" % (week, path))


def shade(ax, gt, label=True):
    """Tô nền các pha flash/tấn công theo ground truth."""
    seen = set()
    for ph in gt["phases"]:
        kind = "ddos" if ph["kind"] in ("syn", "udp") else ph["kind"]
        if kind not in MF.PHASE_FILL:
            continue
        ax.axvspan(ph["start"], ph["end"], color=MF.PHASE_FILL[kind], lw=0)
        if label and kind not in seen:
            seen.add(kind)
            ax.text(ph["start"] + 1, 0.97, "tấn công" if kind == "ddos" else "flash",
                    transform=ax.get_xaxis_transform(), fontsize=8, color=TEXT2,
                    va="top")


def load_run(d):
    gt = json.load(open(os.path.join(d, "ground_truth.json")))
    rt = list(csv.DictReader(open(os.path.join(d, "realtime.csv"))))
    rel = CM.rel_time_fn(gt, rt)
    for r in rt:
        r["_t"] = rel(r)
    rt = [r for r in rt if 0 <= r["_t"] <= gt.get("duration", 999)]
    return gt, rt


def ok_run(d):
    return (os.path.isdir(d) and os.path.exists(os.path.join(d, "meta.json"))
            and not os.path.exists(os.path.join(d, "FAILED")))


def probe_series(d, gt, bin_s=3.0):
    probe = CM.load_probe(d, gt)
    xs, ys, t = [], [], 0.0
    while t < gt.get("duration", 150):
        sel = [p for p in probe if t <= p["rel"] < t + bin_s]
        if sel:
            xs.append(t + bin_s / 2)
            ys.append(sum(p["ok"] for p in sel) / len(sel))
        t += bin_s
    return xs, ys


# ------------------------------------------------------------------ tuần 4
def week4(raw, outdir):
    d = os.path.join(raw, "S3_B0_seed0")
    if not ok_run(d):
        return print("[bỏ qua tuần 4] thiếu", d)
    gt, rt = load_run(d)
    t = [r["_t"] for r in rt]
    fig, axes = plt.subplots(3, 1, figsize=(8.5, 6.2), sharex=True)
    for ax, col, lab in ((axes[0], "packet_rate", "packet_rate (gói/s)"),
                         (axes[1], "syn_rate", "syn_rate (gói SYN/s)"),
                         (axes[2], "syn_ack_ratio", "ACK/(SYN+1)")):
        ax.plot(t, [float(r[col]) for r in rt], color=SERIES, lw=1.8)
        ax.set_ylabel(lab)
        shade(ax, gt, label=(ax is axes[0]))
    axes[0].set_title("Controller đọc counter P4 mỗi ~1s qua P4Runtime "
                      "(S3, không phòng thủ)", loc="left")
    axes[2].set_xlabel("Thời gian từ đầu kịch bản (s)")
    save(fig, outdir, 4, "counter_realtime_S3.png",
         "Feature tính từ counter P4 theo thời gian thực (poll ~1s). Khi SYN "
         "flood bắt đầu (nền xanh lá), packet_rate và syn_rate tăng vọt, "
         "tỉ lệ ACK/SYN tụt về ~0 vì attacker không hoàn tất handshake.")

    # độ trễ một chu kỳ poll
    d1 = os.path.join(raw, "S1_B0_seed0")
    if ok_run(d1):
        _, rt1 = load_run(d1)
        w = [float(r["wall"]) for r in rt1]
        gaps = [b - a for a, b in zip(w, w[1:])]
        fig, ax = plt.subplots(figsize=(6, 3.2))
        ax.hist(gaps, bins=30, color=SERIES, edgecolor=SURFACE)
        ax.set_xlabel("Khoảng cách giữa 2 lần đọc (s)")
        ax.set_ylabel("Số window")
        ax.set_title("Chu kỳ poll thực tế (đặt 1.0s) — S1", loc="left")
        ax.grid(axis="x", visible=False)
        save(fig, outdir, 4, "poll_interval.png",
             "Phân bố chu kỳ poll thực tế: ~%.2fs trung vị (1s ngủ + thời gian "
             "đọc counter/register). Đây là độ phân giải thời gian của hệ thống."
             % sorted(gaps)[len(gaps) // 2])


# ------------------------------------------------------------------ tuần 5
def week5(raw, outdir):
    scns = [("S1", "S1 Normal"), ("S2", "S2 Flash Crowd"),
            ("S3", "S3 SYN flood"), ("S4", "S4 UDP flood")]
    runs = [(s, n, os.path.join(raw, "%s_B0_seed0" % s)) for s, n in scns]
    runs = [x for x in runs if ok_run(x[2])]
    if not runs:
        return print("[bỏ qua tuần 5]")
    fig, axes = plt.subplots(len(runs), 1, figsize=(8.5, 1.9 * len(runs) + 0.8),
                             sharex=True, sharey=True)
    for ax, (s, name, d) in zip(axes, runs):
        gt, rt = load_run(d)
        ax.plot([r["_t"] for r in rt], [float(r["packet_rate"]) for r in rt],
                color=SERIES, lw=1.6)
        shade(ax, gt)
        ax.set_ylabel("gói/s")
        ax.set_title(name, loc="left", fontsize=10)
    axes[-1].set_xlabel("Thời gian từ đầu kịch bản (s)")
    fig.suptitle("Bốn loại traffic sinh trong lab (packet_rate, seed 0)",
                 x=0.01, ha="left")
    save(fig, outdir, 5, "four_traffic_types.png",
         "packet_rate của 4 kịch bản. Điểm mấu chốt: Flash Crowd (S2) có volume "
         "ngang hoặc cao hơn SYN flood (S3) — nhìn volume không phân biệt được.")

    # LSR probe theo kịch bản khi KHÔNG phòng thủ
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    for s, name, d in runs:
        gt, _ = load_run(d)
        xs, ys = probe_series(d, gt)
        ax.plot(xs, ys, lw=2, label=name,
                color={"S1": "#2a78d6", "S2": "#eb6834", "S3": "#1baf7a",
                       "S4": "#eda100"}[s])
    ax.set_ylim(-0.03, 1.08)
    ax.set_xlabel("Thời gian từ đầu kịch bản (s)")
    ax.set_ylabel("Tỉ lệ request probe OK")
    ax.set_title("Dịch vụ khi KHÔNG phòng thủ (bin 3s)", loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=4, fontsize=8.5)
    save(fig, outdir, 5, "probe_no_defense.png",
         "Probe đo dịch vụ khi không phòng thủ: tấn công (S3, S4) làm tỉ lệ "
         "thành công tụt gần 0 trong pha 30–90s; Normal/Flash vẫn phục vụ được.")


# ------------------------------------------------------------------ tuần 6
def week6(data, week6_dir, outdir):
    if not os.path.exists(data):
        return print("[bỏ qua tuần 6] thiếu", data)
    rows = [r for r in csv.DictReader(open(data)) if r["transition"] == "0"]
    labs = ["normal", "flash", "ddos"]
    feats = [("packet_rate", "packet_rate (gói/s)"),
             ("syn_ack_ratio", "ACK/(SYN+1)"),
             ("source_entropy", "source_entropy")]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.6))
    for ax, (f, name) in zip(axes, feats):
        vals = [[float(r[f]) for r in rows if r["label"] == l] for l in labs]
        bp = ax.boxplot(vals, patch_artist=True, widths=0.55, showfliers=False,
                        medianprops={"color": "#0b0b0b"})
        for patch, l in zip(bp["boxes"], labs):
            patch.set_facecolor(LABEL_COLOR[l])
            patch.set_edgecolor(SURFACE)
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels(["Normal", "Flash", "DDoS"])
        ax.set_title(name, loc="left", fontsize=10)
        ax.grid(axis="x", visible=False)
    if "packet_rate" in feats[0]:
        th = None
        rep = os.path.join(week6_dir, "baseline_report.csv")
        if os.path.exists(rep):
            for r in csv.DictReader(open(rep)):
                if r["detector"] == "static_threshold":
                    pass
        md = os.path.join(week6_dir, "baseline_report.md")
        if os.path.exists(md):
            import re
            m = re.search(r"Ngưỡng tĩnh fit được: \*\*([\d.]+)", open(md).read())
            th = float(m.group(1)) if m else None
        if th:
            axes[0].axhline(th, color=TEXT2, lw=1, ls="--")
            axes[0].text(0.6, th, " ngưỡng %.0f" % th, fontsize=8, color=TEXT2,
                         va="bottom")
    fig.suptitle("Dataset UniFlash v01 — %d window từ 24 run testbed" % len(rows),
                 x=0.01, ha="left")
    save(fig, outdir, 6, "feature_distribution.png",
         "Phân bố feature theo nhãn. packet_rate của Flash Crowd chồng lên DDoS "
         "(ngưỡng tĩnh nằm dưới cả hai) nên threshold báo nhầm; ACK/SYN thì tách "
         "rõ: người thật hoàn tất handshake, SYN flood thì không.")

    # nhãn theo kịch bản
    from collections import Counter
    cnt = Counter((r["scenario"].split("_")[0], r["label"]) for r in rows)
    scns = sorted({s for s, _ in cnt})
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    bottom = [0] * len(scns)
    for l in labs:
        v = [cnt.get((s, l), 0) for s in scns]
        ax.bar(scns, v, bottom=bottom, color=LABEL_COLOR[l], label=LABEL_NAME[l],
               edgecolor=SURFACE, linewidth=1.5, width=0.6)
        bottom = [a + b for a, b in zip(bottom, v)]
    ax.set_ylabel("Số window (4 seed)")
    ax.set_title("Cấu trúc dataset theo kịch bản và nhãn", loc="left")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=8.5)
    save(fig, outdir, 6, "dataset_composition.png",
         "Số window có nhãn theo kịch bản (đã loại window sát ranh giới pha).")

    rep = os.path.join(week6_dir, "baseline_report.csv")
    if os.path.exists(rep):
        rr = {r["detector"]: r for r in csv.DictReader(open(rep))}
        fig, ax = plt.subplots(figsize=(6.5, 3.2))
        names = [("static_threshold", "Static threshold"), ("ewma", "EWMA")]
        mets = [("recall_ddos", "Recall DDoS"), ("normal_fpr", "FPR Normal"),
                ("flash_fpr", "Flash-FPR")]
        w = 0.36
        for i, (k, nm) in enumerate(names):
            v = [float(rr[k][m] or 0) for m, _ in mets]
            xs = [j + (i - 0.5) * w for j in range(len(mets))]
            ax.bar(xs, v, w * 0.92, color=["#2a78d6", "#eb6834"][i], label=nm,
                   edgecolor=SURFACE)
            for x, y in zip(xs, v):
                ax.text(x, y + 0.02, "%.2f" % y, ha="center", fontsize=8, color=TEXT2)
        ax.set_xticks(range(len(mets)))
        ax.set_xticklabels([n for _, n in mets])
        ax.set_ylim(0, 1.12)
        ax.set_title("Baseline theo volume: bắt hết DDoS nhưng báo nhầm Flash",
                     loc="left")
        ax.grid(axis="x", visible=False)
        ax.legend(loc="upper left", fontsize=8.5)
        save(fig, outdir, 6, "baseline_flash_fpr.png",
             "Kết quả tuần 6 (chia theo run): threshold và EWMA có Recall ~1 "
             "nhưng Flash-FPR rất cao — bằng chứng cho câu hỏi nghiên cứu RQ2.")


# ------------------------------------------------------------------ tuần 7
def week7(week7_dir, outdir):
    p = MF.model_compare(week7_dir, os.path.join(outdir, "_tmp.png"))
    if p:
        os.makedirs(os.path.join(outdir, "tuan07"), exist_ok=True)
        dst = os.path.join(outdir, "tuan07", "model_compare.png")
        os.replace(p, dst)
        CAPTIONS.append((7, os.path.relpath(dst, outdir),
                         "So sánh 4 phương pháp, dự đoán out-of-fold (GroupKFold "
                         "theo run): ML giữ Recall ~1 và giảm Flash-FPR từ 0.76–0.95 "
                         "xuống ~0.01."))
        print("  tuần 7:", dst)
    p = MF.feature_importance(week7_dir, os.path.join(outdir, "_tmp.png"))
    if p:
        dst = os.path.join(outdir, "tuan07", "feature_importance.png")
        os.replace(p, dst)
        CAPTIONS.append((7, os.path.relpath(dst, outdir),
                         "Độ quan trọng feature của RandomForest: syn_ack_ratio "
                         "đứng đầu — model dựa vào HÀNH VI (hoàn tất handshake), "
                         "không chỉ volume."))
        print("  tuần 7:", dst)
    cmf = os.path.join(week7_dir, "rf_confusion_by_label.csv")
    if os.path.exists(cmf):
        rows = list(csv.reader(open(cmf)))
        labels = [r[0] for r in rows[1:] if r[0] in ("normal", "flash", "ddos")]
        order = [l for l in ("normal", "flash", "ddos") if l in labels]
        data = {r[0]: [int(x) for x in r[1:]] for r in rows[1:] if r[0] in order}
        fig, ax = plt.subplots(figsize=(6.4, 3.6))
        mat = [[data[l][0], data[l][1]] for l in order]
        ax.imshow([[v / max(1, sum(row)) for v in row] for row in mat],
                  cmap="Blues", vmin=0, vmax=1, aspect="auto")
        for i, row in enumerate(mat):
            for j, v in enumerate(row):
                frac = v / max(1, sum(row))
                ax.text(j, i, "%d\n(%.1f%%)" % (v, 100 * frac), ha="center",
                        va="center", fontsize=9,
                        color="white" if frac > 0.6 else "#0b0b0b")
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["dự đoán: lành tính", "dự đoán: DDoS"])
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels([LABEL_NAME[l] for l in order])
        ax.grid(False)
        ax.set_title("Ma trận nhầm lẫn RF (out-of-fold)", loc="left")
        save(fig, outdir, 7, "confusion_rf.png",
             "Ma trận nhầm lẫn theo nhãn chi tiết: gần như toàn bộ Flash Crowd "
             "được giữ là lành tính.")


# ------------------------------------------------------------------ tuần 8
def week8(raw, outdir):
    d = os.path.join(raw, "S5_B2_seed10")
    if not ok_run(d):
        return print("[bỏ qua tuần 8] thiếu", d)
    gt, rt = load_run(d)
    db = os.path.join(raw, "S5_B1_seed10")
    fig, axes = plt.subplots(3, 1, figsize=(8.5, 5.6), sharex=True,
                             gridspec_kw={"height_ratios": [2.2, 1, 1]})
    t = [r["_t"] for r in rt]
    axes[0].plot(t, [float(r["packet_rate"]) for r in rt], color=SERIES, lw=1.6)
    axes[0].set_ylabel("packet_rate")
    shade(axes[0], gt)
    truth = [1 if CM.label_at(x, gt["phases"]) == "ddos" else 0 for x in t]
    axes[1].step(t, truth, where="post", color=TEXT2, lw=1.5)
    axes[1].set_ylabel("Nhãn thật\n(1=DDoS)")
    axes[1].set_yticks([0, 1])
    axes[2].step(t, [int(r["pred"]) for r in rt], where="post",
                 color=MF.BASE_COLOR["B2"], lw=1.8, label="RandomForest (B2)")
    if ok_run(db):
        gb, rb = load_run(db)
        axes[2].step([r["_t"] for r in rb], [int(r["pred"]) * 0.92 for r in rb],
                     where="post", color=MF.BASE_COLOR["B1"], lw=1.4,
                     label="Threshold (B1)")
    axes[2].set_ylabel("Dự đoán\n(1=DDoS)")
    axes[2].set_yticks([0, 1])
    axes[2].legend(loc="upper center", bbox_to_anchor=(0.5, -0.45), ncol=2,
                   fontsize=8.5)
    axes[2].set_xlabel("Thời gian từ đầu kịch bản (s)")
    axes[0].set_title("Phát hiện ONLINE ở S5 (Flash 30–120s + DDoS 50–110s), seed 10",
                      loc="left")
    save(fig, outdir, 8, "online_detection_S5.png",
         "Model chạy thời gian thực: báo DDoS đúng trong pha tấn công và im lặng "
         "trong Flash Crowd 30–50s và 110–120s; threshold báo động suốt cả pha "
         "Flash.")

    # độ trễ phát hiện
    lat = {}
    for b in ("B1", "B2", "B3"):
        for d in glob.glob(os.path.join(raw, "S[345]_%s_seed*" % b)):
            if ok_run(d):
                v = CM.compute(d).get("detection_latency_s")
                if v is not None:
                    lat.setdefault(b, []).append(v)
    if lat:
        fig, ax = plt.subplots(figsize=(6, 3.2))
        bs = [b for b in ("B1", "B2", "B3") if b in lat]
        bp = ax.boxplot([lat[b] for b in bs], patch_artist=True, widths=0.5,
                        medianprops={"color": "#0b0b0b"})
        for patch, b in zip(bp["boxes"], bs):
            patch.set_facecolor(MF.BASE_COLOR[b])
            patch.set_edgecolor(SURFACE)
        ax.set_xticks(range(1, len(bs) + 1))
        ax.set_xticklabels([MF.BASE_NAME[b].split(" ", 1)[1] for b in bs], fontsize=8)
        ax.set_ylabel("Giây từ lúc tấn công bắt đầu")
        ax.set_title("Độ trễ phát hiện (S3–S5, mọi seed)", loc="left")
        ax.grid(axis="x", visible=False)
        save(fig, outdir, 8, "detection_latency.png",
             "Độ trễ phát hiện online: ~2–3 chu kỳ poll. Model không chậm hơn "
             "threshold đáng kể.")


# ------------------------------------------------------------------ tuần 9
def week9(raw, outdir):
    d = os.path.join(raw, "S5_B3_seed10")
    if not ok_run(d):
        return print("[bỏ qua tuần 9] thiếu", d)
    gt, rt = load_run(d)
    fig, axes = plt.subplots(2, 1, figsize=(8.5, 4.8), sharex=True,
                             gridspec_kw={"height_ratios": [1, 1.6]})
    t = [r["_t"] for r in rt]
    axes[0].step(t, [int(r["level"]) for r in rt], where="post",
                 color=MF.BASE_COLOR["B3"], lw=2)
    axes[0].set_yticks([0, 1, 2])
    axes[0].set_yticklabels(["L0 theo dõi", "L1 rate-limit", "L2 drop"])
    shade(axes[0], gt)
    axes[0].set_title("Mitigation chọn lọc (B3) ở S5, seed 10", loc="left")
    for b in ("B0", "B3"):
        dd = os.path.join(raw, "S5_%s_seed10" % b)
        if ok_run(dd):
            g2, _ = load_run(dd)
            xs, ys = probe_series(dd, g2)
            axes[1].plot(xs, ys, color=MF.BASE_COLOR[b], lw=2, label=MF.BASE_NAME[b])
    shade(axes[1], gt, label=False)
    axes[1].set_ylim(-0.03, 1.05)
    axes[1].set_ylabel("Probe OK (bin 3s)")
    axes[1].set_xlabel("Thời gian từ đầu kịch bản (s)")
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=2, fontsize=8.5)
    sus = sorted({s for r in rt for s in r.get("suspects", "").split("|") if s})
    save(fig, outdir, 9, "mitigation_timeline_S5.png",
         "B3 leo L1→L2 trong ~3s sau khi tấn công bắt đầu và chặn đúng cổng %s. "
         "B0 sập về 0 suốt pha tấn công; B3 giữ được một phần dịch vụ nhưng "
         "không về 100%% vì Flash Crowd đồng thời vẫn làm server quá tải và các "
         "kết nối half-open còn tồn đọng." % (", ".join(sus) or "?"))

    # host bị chặn ở mọi run B3: đúng/sai
    hit = {}
    for dd in glob.glob(os.path.join(raw, "S*_B3_seed*")):
        if not ok_run(dd):
            continue
        for r in csv.DictReader(open(os.path.join(dd, "realtime.csv"))):
            for s in (r.get("suspects") or "").split("|"):
                if s and int(r.get("level") or 0) >= 1:
                    hit[s] = hit.get(s, 0) + 1
    if hit:
        names = sorted(hit, key=lambda h: (not h.startswith("a"), h))
        fig, ax = plt.subplots(figsize=(6.5, 3.0))
        ax.bar(names, [hit[n] for n in names], color=SERIES, edgecolor=SURFACE,
               width=0.6)
        ax.set_ylabel("Số window bị chặn")
        ax.set_title("Host bị B3 chặn (mọi run B3)", loc="left")
        ax.grid(axis="x", visible=False)
        legit = [n for n in names if not n.startswith("a")]
        save(fig, outdir, 9, "blocked_hosts.png",
             "Tổng số window mỗi host bị chặn trên mọi run B3. a1–a3 là host tấn "
             "công; %s." % ("host hợp lệ bị chặn nhầm: " + ", ".join(legit)
                            if legit else "không host hợp lệ (h1–h8) nào bị chặn"))


# ------------------------------------------------------------------ tuần 10–11
def week10_11(summary, raw, week7_dir, outdir):
    if not os.path.exists(summary):
        return print("[bỏ qua tuần 10–11] thiếu", summary)
    rows = MF.load_summary(summary)
    specs10 = [
        (["S3", "S3S", "S4", "S5"], "lsr_attack", "LSR probe trong pha tấn công",
         "LSR trong pha tấn công (mean ± CI95)", "lsr_attack.png",
         ("B0", "B1", "B2", "B3"), (0, 1.05), "%.2f",
         "Thước đo chính: tỉ lệ request probe thành công TRONG pha tấn công. "
         "S3S = SYN flood với IP nguồn giả mạo (thí nghiệm bổ sung, n = 3)."),
        (["S3", "S3S", "S4", "S5"], "user_sr_attack", "Tỉ lệ thành công client hợp lệ",
         "Mọi client hợp lệ h1–h8 trong pha tấn công", "user_sr_attack.png",
         ("B0", "B1", "B2", "B3"), (0, 1.05), "%.2f",
         "Thước đo độc lập với feedback: client h1–h8 không được đưa vào vòng "
         "phản hồi của B3."),
        (["S1", "S2", "S5", "S6"], "fpr", "FPR theo window",
         "Báo động nhầm trên traffic hợp lệ", "fpr.png", ("B1", "B2", "B3"),
         (0, 1.05), "%.2f", "FPR theo window: threshold báo nhầm khi Flash Crowd."),
        (["S2", "S5"], "flash_sr", "User Flash Crowd thành công",
         "Flash Crowd hợp lệ có được phục vụ?", "flash_sr.png",
         ("B0", "B1", "B2", "B3"), (0, 1.05), "%.2f",
         "Tỉ lệ thành công của chính người dùng Flash Crowd."),
        (["S3", "S4", "S5"], "mitigation_latency_s", "Giây từ lúc tấn công bắt đầu",
         "Độ trễ tới khi bắt đầu mitigation", "mitigation_latency.png",
         ("B1", "B2", "B3"), (0, 8), "%.1f", "Độ trễ từ khi tấn công bắt đầu tới "
         "khi rule mitigation đầu tiên được ghi."),
    ]
    for scns, metric, ylabel, title, name, bases, ylim, fmt, cap in specs10:
        os.makedirs(os.path.join(outdir, "tuan10"), exist_ok=True)
        p = MF.grouped_bar(rows, scns, metric, ylabel, title,
                           os.path.join(outdir, "tuan10", name), baselines=bases,
                           ylim=ylim, fmt=fmt)
        if p:
            CAPTIONS.append((10, os.path.relpath(p, outdir), cap))
            print("  tuần 10:", p)

    # tuần 11: tổng kết
    os.makedirs(os.path.join(outdir, "tuan11"), exist_ok=True)
    p = MF.timeline(raw, "S5", 10, os.path.join(outdir, "tuan11", "timeline_S5_all.png"))
    if p:
        CAPTIONS.append((11, os.path.relpath(p, outdir),
                         "Cùng kịch bản S5 (seed 10) dưới 4 baseline: chỉ B3 giữ "
                         "được dịch vụ trong pha tấn công."))
        print("  tuần 11:", p)
    p = MF.timeline(raw, "S3", 10, os.path.join(outdir, "tuan11", "timeline_S3_all.png"))
    if p:
        CAPTIONS.append((11, os.path.relpath(p, outdir),
                         "Kịch bản S3 (SYN flood) dưới 4 baseline."))
        print("  tuần 11:", p)
    # trade-off: Flash-FPR vs LSR tấn công ở S5
    idx = {(r["scenario"], r["baseline"]): r for r in rows}
    pts = [(b, MF._f(idx[("S5", b)].get("flash_fpr_mean")),
            MF._f(idx[("S5", b)].get("lsr_attack_mean")))
           for b in ("B1", "B2", "B3") if ("S5", b) in idx]
    pts = [p for p in pts if p[1] is not None and p[2] is not None]
    if pts:
        fig, ax = plt.subplots(figsize=(6, 4))
        for b, x, y in pts:
            ax.scatter([x], [y], s=110, color=MF.BASE_COLOR[b], edgecolor=SURFACE,
                       linewidth=2, zorder=3)
            right = x > 0.6     # điểm sát mép phải: đặt nhãn quay vào trong
            ax.annotate(MF.BASE_NAME[b], (x, y), textcoords="offset points",
                        xytext=(-8, 8) if right else (8, 6),
                        ha="right" if right else "left", fontsize=8.5, color=TEXT2)
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)
        ax.set_xlabel("Flash-FPR (báo nhầm Flash Crowd) — thấp = tốt")
        ax.set_ylabel("LSR trong pha tấn công — cao = tốt")
        ax.set_title("Trade-off ở S5 (Flash + DDoS): góc trên-trái là tốt nhất",
                     loc="left")
        save(fig, outdir, 11, "tradeoff_S5.png",
             "Mỗi điểm = trung bình một baseline ở S5. B3 đạt cả hai mục tiêu: "
             "không báo nhầm Flash và giữ dịch vụ khi bị tấn công.")


def write_readme(outdir):
    lines = ["# Hình kết quả theo tuần", "",
             "Sinh bằng `python3 analysis/weekly_figures.py` (hoặc `make figures`). "
             "Mỗi hình kèm chú thích gợi ý để dán vào báo cáo.", ""]
    for week in sorted({w for w, _, _ in CAPTIONS}):
        lines += ["## Tuần %d" % week, ""]
        for w, path, cap in CAPTIONS:
            if w == week:
                lines += ["![%s](%s)" % (os.path.basename(path), path), "",
                          "*%s*" % cap, ""]
    open(os.path.join(outdir, "README.md"), "w").write("\n".join(lines) + "\n")
    print("Đã ghi", os.path.join(outdir, "README.md"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-raw", default=os.path.join(ROOT, "results", "dataset_raw"))
    ap.add_argument("--raw", default=os.path.join(ROOT, "results", "raw"))
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "uniflash_v01.csv"))
    ap.add_argument("--week6", default=os.path.join(ROOT, "experiments", "week6"))
    ap.add_argument("--week7", default=os.path.join(ROOT, "experiments", "week7"))
    ap.add_argument("--summary", default=os.path.join(ROOT, "results", "summary.csv"))
    ap.add_argument("--outdir", default=os.path.join(ROOT, "figures"))
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    week4(args.dataset_raw, args.outdir)
    week5(args.dataset_raw, args.outdir)
    week6(args.data, args.week6, args.outdir)
    week7(args.week7, args.outdir)
    week8(args.raw, args.outdir)
    week9(args.raw, args.outdir)
    week10_11(args.summary, args.raw, args.week7, args.outdir)
    write_readme(args.outdir)


if __name__ == "__main__":
    main()
