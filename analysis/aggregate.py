"""
aggregate.py — Gom metric nhiều run thành bảng mean ± CI95 theo (scenario, baseline),
và kiểm định khác biệt (Mann-Whitney U) cho so sánh chính.

Quy ước thư mục: results/raw/<SCENARIO>_<BASELINE>_seed<k>/
Ví dụ: results/raw/S5_B1_seed0, results/raw/S5_B3_seed0, ...

Chạy:
  python3 analysis/aggregate.py --raw results/raw --out results/summary.csv
  python3 analysis/aggregate.py --raw results/raw --compare S5 lsr B1 B3
  python3 analysis/aggregate.py --raw results/raw --compare-all \
      --stats-out results/stats.csv        # B3 vs B0/B1/B2, mọi scenario, Holm

Ghi chú thống kê: đơn vị lặp là MỘT RUN (seed), không phải window/request
(các window trong một run phụ thuộc nhau). Với n run mỗi nhóm, Mann-Whitney
hai phía có p nhỏ nhất = 2/C(2n, n): n=3 -> 0.10, n=5 -> 0.008. Vì vậy báo
cáo kèm Welch t-test và khoảng tin cậy bootstrap của HIỆU hai nhóm.
"""
import argparse
import csv
import glob
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compute_metrics as CM  # noqa: E402

METRIC_COLS = ["precision", "recall", "f1", "fpr", "flash_fpr",
               "lsr", "lsr_attack", "lsr_sla", "ldr",
               "user_sr", "user_sr_attack", "flash_sr", "jain",
               "lat_p50_ms", "lat_p95_ms",
               "detection_latency_s", "mitigation_latency_s",
               "cpu_mean_pct", "infer_ms_mean", "max_rules"]
# B0 chỉ ghi log (không phòng thủ) -> metric phát hiện/mitigation không có nghĩa
DETECTION_COLS = {"precision", "recall", "f1", "fpr", "flash_fpr",
                  "detection_latency_s", "mitigation_latency_s"}

DIR_RE = re.compile(r"^(?P<scn>[^_]+)_(?P<base>B\d)_seed(?P<seed>\d+)$")


def collect(raw_dir):
    """Trả về dict (scn, base) -> {metric: [giá trị theo run]}."""
    groups = {}
    for d in sorted(glob.glob(os.path.join(raw_dir, "*"))):
        if not os.path.isdir(d) or os.path.exists(os.path.join(d, "FAILED")):
            continue
        m = DIR_RE.match(os.path.basename(d))
        if not m:
            continue
        try:
            res = CM.compute(d)
        except Exception as e:
            print("[warn] bỏ qua %s: %s" % (d, e))
            continue
        key = (m["scn"], m["base"])
        g = groups.setdefault(key, {c: [] for c in METRIC_COLS})
        for c in METRIC_COLS:
            if m["base"] == "B0" and c in DETECTION_COLS:
                continue
            v = res.get(c)
            if v is not None:
                g[c].append(float(v))
    return groups


def mean_ci95(values):
    n = len(values)
    if n == 0:
        return (None, None, 0)
    mean = sum(values) / n
    if n < 2:
        return (mean, None, n)
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    sd = math.sqrt(var)
    # t xấp xỉ 1.96 cho n lớn; dùng bảng nhỏ cho n nhỏ
    t = _t95(n - 1)
    ci = t * sd / math.sqrt(n)
    return (mean, ci, n)


_T = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36,
      8: 2.31, 9: 2.26, 10: 2.23, 15: 2.13, 20: 2.09, 30: 2.04}


def _t95(dof):
    if dof in _T:
        return _T[dof]
    keys = sorted(_T)
    for k in keys:
        if dof <= k:
            return _T[k]
    return 1.96


def write_summary(groups, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        header = ["scenario", "baseline", "n_runs"]
        for c in METRIC_COLS:
            header += [c + "_mean", c + "_ci95"]
        w.writerow(header)
        for (scn, base) in sorted(groups):
            g = groups[(scn, base)]
            nmax = max((len(g[c]) for c in METRIC_COLS), default=0)
            row = [scn, base, nmax]
            for c in METRIC_COLS:
                mean, ci, _ = mean_ci95(g[c])
                row += [None if mean is None else round(mean, 4),
                        None if ci is None else round(ci, 4)]
            w.writerow(row)
    print("Đã ghi bảng tổng hợp ->", out_path)


def mann_whitney_u(a, b):
    """Mann-Whitney U hai phía. Dùng scipy nếu có, else xấp xỉ chuẩn."""
    # Hai nhóm toàn giá trị giống hệt nhau: không có bằng chứng khác biệt.
    # (scipy trả p = NaN trường hợp này; NaN làm hỏng thứ tự Holm.)
    if len(set(a) | set(b)) <= 1:
        return float(len(a) * len(b)) / 2, 1.0
    try:
        from scipy.stats import mannwhitneyu
        u, p = mannwhitneyu(a, b, alternative="two-sided")
        if p != p:      # NaN
            return float(u), 1.0
        return float(u), float(p)
    except Exception:
        return _mwu_normal(a, b)


def _mwu_normal(a, b):
    combined = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    ranks = {}
    i = 0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    r1 = sum(ranks[k] for k, (_, g) in enumerate(combined) if g == 0)
    n1, n2 = len(a), len(b)
    u1 = r1 - n1 * (n1 + 1) / 2
    u = min(u1, n1 * n2 - u1)
    mu = n1 * n2 / 2
    sigma = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if sigma == 0:
        return u, 1.0
    z = (u - mu) / sigma
    p = 2 * (1 - _norm_cdf(abs(z)))
    return u, p


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bootstrap_ci(values, stat="mean", n_boot=2000, alpha=0.05, seed=0):
    """Khoảng tin cậy bootstrap (percentile). Dùng cho metric tỉ lệ như LSR
    (bị chặn [0,1]) vì t-test thường không phù hợp — góp ý giảng viên.

    Trả về (điểm ước lượng, lo, hi). stat='mean' hoặc 'median'.
    """
    import random
    xs = [float(v) for v in values if v is not None]
    n = len(xs)
    if n == 0:
        return (None, None, None)
    if n == 1:
        return (xs[0], xs[0], xs[0])
    rng = random.Random(seed)
    f = (sum(x for x in xs) / n) if stat == "mean" else _median(xs)
    boots = []
    for _ in range(n_boot):
        sample = [xs[rng.randrange(n)] for _ in range(n)]
        boots.append(sum(sample) / n if stat == "mean" else _median(sample))
    boots.sort()
    lo = boots[int((alpha / 2) * n_boot)]
    hi = boots[int((1 - alpha / 2) * n_boot) - 1]
    return (f, lo, hi)


def _median(xs):
    ys = sorted(xs)
    m = len(ys)
    return ys[m // 2] if m % 2 else (ys[m // 2 - 1] + ys[m // 2]) / 2


def holm_bonferroni(pvalues, alpha=0.05):
    """Hiệu chỉnh đa so sánh Holm–Bonferroni — tránh false positive khi so
    nhiều baseline × nhiều scenario (góp ý giảng viên).

    pvalues: dict {tên: p}. Trả về dict {tên: (p, p_hiệu_chỉnh, bác_bỏ_H0?)}.
    """
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    out = {}
    prev_adj = 0.0
    for i, (name, p) in enumerate(items):
        adj = min(1.0, (m - i) * p)
        adj = max(adj, prev_adj)   # giữ tính đơn điệu
        prev_adj = adj
        out[name] = (p, adj, adj < alpha)
    return out


def welch_t(a, b):
    """Welch t-test hai phía. scipy nếu có; None nếu không tính được."""
    try:
        from scipy.stats import ttest_ind
        if len(set(a)) <= 1 and len(set(b)) <= 1:
            return None if a[0] != b[0] else 1.0
        p = float(ttest_ind(a, b, equal_var=False).pvalue)
        return None if p != p else p
    except Exception:
        return None


def bootstrap_diff_ci(a, b, n_boot=4000, seed=0):
    """CI95 bootstrap của mean(a) - mean(b)."""
    import random
    rng = random.Random(seed)
    if not a or not b:
        return (None, None)
    diffs = []
    for _ in range(n_boot):
        sa = [a[rng.randrange(len(a))] for _ in a]
        sb = [b[rng.randrange(len(b))] for _ in b]
        diffs.append(sum(sa) / len(sa) - sum(sb) / len(sb))
    diffs.sort()
    return (diffs[int(0.025 * n_boot)], diffs[int(0.975 * n_boot) - 1])


COMPARE_METRICS = ["lsr_attack", "user_sr_attack", "flash_sr", "flash_fpr", "fpr"]


def compare_all(groups, out_path, ref="B3", others=("B0", "B1", "B2")):
    """So sánh ref với từng baseline khác trên mọi scenario × metric.
    Holm–Bonferroni áp riêng cho từng metric (họ so sánh của metric đó)."""
    rows = []
    scns = sorted({s for s, _ in groups})
    for metric in COMPARE_METRICS:
        fam, fam_w = {}, {}
        for scn in scns:
            a = groups.get((scn, ref), {}).get(metric, [])
            for ob in others:
                b = groups.get((scn, ob), {}).get(metric, [])
                if len(a) < 2 or len(b) < 2:
                    continue
                _, p_mw = mann_whitney_u(a, b)
                p_w = welch_t(a, b)
                lo, hi = bootstrap_diff_ci(a, b)
                key = (scn, ob)
                fam[key] = p_mw
                fam_w[key] = 1.0 if p_w is None else p_w
                # tách hoàn toàn: mọi run của nhóm này lớn (hoặc nhỏ) hơn mọi run nhóm kia
                sep = (min(a) > max(b)) or (max(a) < min(b))
                rows.append({"metric": metric, "scenario": scn,
                             "ref": ref, "other": ob,
                             "n_ref": len(a), "n_other": len(b),
                             "mean_ref": round(sum(a) / len(a), 4),
                             "mean_other": round(sum(b) / len(b), 4),
                             "diff": round(sum(a) / len(a) - sum(b) / len(b), 4),
                             "diff_ci95_lo": None if lo is None else round(lo, 4),
                             "diff_ci95_hi": None if hi is None else round(hi, 4),
                             "p_mannwhitney": round(p_mw, 4),
                             "p_welch": None if p_w is None else round(p_w, 6),
                             "separated": int(sep)})
        if fam:
            adj = holm_bonferroni({"%s|%s" % k: v for k, v in fam.items()})
            adj_w = holm_bonferroni({"%s|%s" % k: v for k, v in fam_w.items()})
            for r in rows:
                k = "%s|%s" % (r["scenario"], r["other"])
                if r["metric"] == metric and k in adj:
                    r["p_mw_holm"] = round(adj[k][1], 4)
                    r["p_welch_holm"] = round(adj_w[k][1], 6)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    cols = ["metric", "scenario", "ref", "other", "n_ref", "n_other",
            "mean_ref", "mean_other", "diff", "diff_ci95_lo", "diff_ci95_hi",
            "separated", "p_mannwhitney", "p_mw_holm", "p_welch", "p_welch_holm"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})
    print("Đã ghi kiểm định ->", out_path, "(%d so sánh)" % len(rows))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="results/raw")
    ap.add_argument("--out", default="results/summary.csv")
    ap.add_argument("--compare", nargs=4, metavar=("SCN", "METRIC", "B_A", "B_B"),
                    help="vd: S5 lsr B1 B3")
    ap.add_argument("--compare-all", action="store_true",
                    help="B3 vs B0/B1/B2 trên mọi scenario + Holm")
    ap.add_argument("--stats-out", default="results/stats.csv")
    args = ap.parse_args()
    groups = collect(args.raw)
    if not groups:
        print("Không tìm thấy run nào trong", args.raw)
        return
    write_summary(groups, args.out)
    if args.compare_all:
        compare_all(groups, args.stats_out)

    if args.compare:
        scn, metric, ba, bb = args.compare
        a = groups.get((scn, ba), {}).get(metric, [])
        b = groups.get((scn, bb), {}).get(metric, [])
        if len(a) < 2 or len(b) < 2:
            print("Không đủ run để kiểm định (cần >=2 mỗi nhóm).")
            return
        u, p = mann_whitney_u(a, b)
        ma, _, _ = mean_ci95(a)
        mb, _, _ = mean_ci95(b)
        print("\n%s trên %s: %s=%.4f (n=%d) vs %s=%.4f (n=%d)" %
              (metric, scn, ba, ma, len(a), bb, mb, len(b)))
        print("Mann-Whitney U=%.1f, p=%.4f -> %s" %
              (u, p, "KHÁC BIỆT có ý nghĩa (p<0.05)" if p < 0.05
               else "chưa đủ bằng chứng khác biệt"))


if __name__ == "__main__":
    main()
