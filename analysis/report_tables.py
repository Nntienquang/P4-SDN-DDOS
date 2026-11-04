"""
report_tables.py — Sinh bảng Markdown (mean ± CI95) từ results/summary.csv và
bảng kiểm định từ results/stats.csv để dán vào báo cáo (tuần 10–11).

Chạy:  python3 analysis/report_tables.py --summary results/summary.csv \
           --stats results/stats.csv --out results/RESULTS.md
"""
import argparse
import csv
import os

SCN_NAME = {"S1": "S1 Normal", "S2": "S2 Flash", "S3": "S3 SYN flood",
            "S4": "S4 UDP flood", "S5": "S5 Flash+DDoS", "S6": "S6 Nền đổi"}


def _cell(r, m, pct=False, nd=3):
    v = r.get(m + "_mean")
    if v in (None, ""):
        return "—"
    v = float(v)
    ci = r.get(m + "_ci95")
    if pct:
        s = "%.1f%%" % (100 * v)
        if ci not in (None, ""):
            s += " ± %.1f" % (100 * float(ci))
        return s
    s = ("%." + str(nd) + "f") % v
    if ci not in (None, ""):
        s += " ± " + ("%." + str(nd) + "f") % float(ci)
    return s


def table(rows, scns, cols, title, note=""):
    out = ["### " + title, ""]
    if note:
        out += [note, ""]
    out.append("| Scenario | Baseline | n | " + " | ".join(c[1] for c in cols) + " |")
    out.append("| --- | --- | --- | " + " | ".join("---" for _ in cols) + " |")
    for r in rows:
        if r["scenario"] not in scns:
            continue
        out.append("| %s | %s | %s | %s |" % (
            SCN_NAME.get(r["scenario"], r["scenario"]), r["baseline"], r["n_runs"],
            " | ".join(_cell(r, c[0], **c[2]) for c in cols)))
    return out + [""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="results/summary.csv")
    ap.add_argument("--stats", default="results/stats.csv")
    ap.add_argument("--out", default="results/RESULTS.md")
    args = ap.parse_args()
    rows = list(csv.DictReader(open(args.summary)))
    rows.sort(key=lambda r: (r["scenario"], r["baseline"]))
    md = ["# Kết quả thí nghiệm chính (tuần 10)", "",
          "Mỗi ô: trung bình ± nửa khoảng tin cậy 95% (t-Student) trên các run "
          "(seed). B0 không phòng thủ nên không có metric phát hiện.", ""]
    pct = {"pct": True}
    num = {"pct": False}
    md += table(rows, {"S3", "S4", "S5"}, [
        ("lsr_attack", "LSR probe (pha tấn công)", pct),
        ("user_sr_attack", "Client hợp lệ OK (pha tấn công)", pct),
        ("lsr", "LSR cả run", pct),
        ("jain", "Jain fairness", {"pct": False, "nd": 2}),
        ("lat_p95_ms", "p95 latency (ms)", {"pct": False, "nd": 0}),
    ], "Bảng A — Trục User: giữ dịch vụ khi bị DDoS")
    md += table(rows, {"S1", "S2", "S5", "S6"}, [
        ("fpr", "FPR (window)", pct),
        ("flash_fpr", "Flash-FPR", pct),
        ("flash_sr", "User Flash OK", pct),
        ("lsr", "LSR cả run", pct),
    ], "Bảng B — Báo nhầm & Flash Crowd hợp lệ")
    md += table(rows, {"S3", "S4", "S5"}, [
        ("recall", "Recall", pct), ("precision", "Precision", pct),
        ("detection_latency_s", "Trễ phát hiện (s)", {"pct": False, "nd": 1}),
        ("mitigation_latency_s", "Trễ mitigation (s)", {"pct": False, "nd": 1}),
        ("cpu_mean_pct", "CPU detector (%)", {"pct": False, "nd": 1}),
        ("infer_ms_mean", "Suy luận (ms)", {"pct": False, "nd": 2}),
        ("max_rules", "Số rule tối đa", {"pct": False, "nd": 1}),
    ], "Bảng C — Trục Security / Speed / Cost")

    if os.path.exists(args.stats):
        st = list(csv.DictReader(open(args.stats)))
        md += ["### Bảng D — Kiểm định B3 so với từng baseline", "",
               "Đơn vị = run. Hiệu = mean(B3) − mean(baseline), CI95 bootstrap. "
               "p đã hiệu chỉnh Holm trong từng metric. \"Tách hoàn toàn\" = mọi "
               "run của B3 tốt hơn mọi run của baseline (U = 0). Lưu ý: với n run/"
               "nhóm, p Mann-Whitney nhỏ nhất có thể đạt là 2/C(2n,n) (n=3 → 0.10; "
               "n=5 → 0.0079), nên sau Holm với 9 phép so sánh, MW không thể xuống "
               "dưới 0.05 dù hai nhóm tách hoàn toàn; Welch t-test (giả định gần "
               "chuẩn) là kiểm định chính, MW là kiểm tra phi tham số bổ trợ.", "",
               "| Metric | Scenario | So với | n | Hiệu (B3−X) | CI95 hiệu | Tách hoàn toàn | p Welch (Holm) | p MW (Holm) |",
               "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in st:
            if r["metric"] not in ("lsr_attack", "user_sr_attack", "flash_sr", "flash_fpr"):
                continue
            pw = r.get("p_welch_holm")
            pw = "—" if pw in (None, "") else ("< 0.001" if float(pw) < 0.001
                                               else "%.3f" % float(pw))
            md.append("| %s | %s | %s | %s/%s | %+.3f | [%.3f, %.3f] | %s | %s | %s |" % (
                r["metric"], r["scenario"], r["other"], r["n_ref"], r["n_other"],
                float(r["diff"]), float(r["diff_ci95_lo"]), float(r["diff_ci95_hi"]),
                "có" if r.get("separated") == "1" else "không", pw,
                r.get("p_mw_holm") or "—"))
        md.append("")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    open(args.out, "w").write("\n".join(md) + "\n")
    print("Đã ghi", args.out)


if __name__ == "__main__":
    main()
