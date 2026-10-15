"""
aggregate.py — Gom metric nhiều run thành bảng mean ± CI95 theo (scenario, baseline),
và kiểm định khác biệt (Mann-Whitney U) cho so sánh chính.

Quy ước thư mục: results/raw/<SCENARIO>_<BASELINE>_seed<k>/
Ví dụ: results/raw/S5_B1_seed0, results/raw/S5_B3_seed0, ...

Chạy:
  python3 analysis/aggregate.py --raw results/raw --out results/summary.csv
  python3 analysis/aggregate.py --raw results/raw --compare S5 lsr B1 B3
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
               "lsr", "ldr", "lat_p50_ms", "lat_p95_ms",
               "detection_latency_s", "cpu_mean_pct"]

DIR_RE = re.compile(r"^(?P<scn>[^_]+)_(?P<base>B\d)_seed(?P<seed>\d+)$")


def collect(raw_dir):
    """Trả về dict (scn, base) -> {metric: [giá trị theo run]}."""
    groups = {}
    for d in sorted(glob.glob(os.path.join(raw_dir, "*"))):
        if not os.path.isdir(d):
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
    try:
        from scipy.stats import mannwhitneyu
        u, p = mannwhitneyu(a, b, alternative="two-sided")
        return u, p
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="results/raw")
    ap.add_argument("--out", default="results/summary.csv")
    ap.add_argument("--compare", nargs=4, metavar=("SCN", "METRIC", "B_A", "B_B"),
                    help="vd: S5 lsr B1 B3")
    args = ap.parse_args()
    groups = collect(args.raw)
    if not groups:
        print("Không tìm thấy run nào trong", args.raw)
        return
    write_summary(groups, args.out)

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
