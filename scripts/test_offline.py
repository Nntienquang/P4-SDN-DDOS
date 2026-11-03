#!/usr/bin/env python3
"""
test_offline.py — Kiểm tra các module KHÔNG cần P4/Mininet.

Chạy:  python3 scripts/test_offline.py
Mục đích: newbie xác nhận logic feature/detector/policy/metrics đúng trước khi
đụng tới testbed. Không có framework test ngoài; dùng assert thuần.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for d in ("controller", "baseline", "mitigation", "metrics", "ml"):
    sys.path.insert(0, os.path.join(ROOT, d))

import features as F          # noqa: E402
import detectors as D         # noqa: E402
import policy as P            # noqa: E402
import service_metrics as M   # noqa: E402
import build_dataset as BD    # noqa: E402
import eval_baseline as EB    # noqa: E402

passed = 0


def check(name, cond):
    global passed
    assert cond, "FAIL: " + name
    passed += 1
    print("  ok:", name)


def test_features():
    print("[features]")
    prev = {"t": 0.0, "total_pkts": 0, "total_bytes": 0, "syn": 0, "ack": 0,
            "udp": 0, "port_pkts": {1: 0, 2: 0}, "src_popcount": 0,
            "bitmap_size": 4096}
    cur = {"t": 1.0, "total_pkts": 1000, "total_bytes": 700000, "syn": 50,
           "ack": 900, "udp": 20, "port_pkts": {1: 500, 2: 500},
           "src_popcount": 10, "bitmap_size": 4096}
    f = F.compute_features(cur, prev)
    check("packet_rate = 1000/s", abs(f["packet_rate"] - 1000) < 1e-6)
    check("byte_rate = 700000/s", abs(f["byte_rate"] - 700000) < 1e-6)
    check("syn_ack_ratio ~ 900/51", abs(f["syn_ack_ratio"] - 900/51) < 1e-6)
    check("entropy 2 cổng đều = 1.0", abs(f["source_entropy"] - 1.0) < 1e-6)
    check("source_count > 0", f["source_count"] > 0)
    # entropy khi dồn 1 cổng = 0
    cur2 = dict(cur); cur2["port_pkts"] = {1: 1000, 2: 0}
    f2 = F.compute_features(cur2, prev)
    check("entropy dồn 1 cổng = 0", f2["source_entropy"] == 0.0)
    # growth slope
    f3 = F.compute_features(cur, prev, prev_packet_rate=600)
    check("growth_slope = 400", abs(f3["growth_slope"] - 400) < 1e-6)
    check("feature_vector đúng độ dài", len(F.feature_vector(f)) == len(F.FEATURE_NAMES))
    # linear counting hợp lý: popcount nhỏ -> n_hat ~ popcount
    check("estimate_sources ~ popcount khi thưa",
          abs(F.estimate_sources(10, 4096) - 10) < 1.0)


def test_detectors():
    print("[detectors]")
    normal = [300 + (i % 20) for i in range(200)]
    st = D.StaticThreshold.fit_from_normal(normal, pct=99, k=1.0)
    check("threshold nằm quanh max normal", 315 <= st.threshold <= 340)
    check("normal không alarm", st.predict(310) == 0)
    check("spike alarm", st.predict(2000) == 1)
    ew = D.EWMA(alpha=0.3, k=3.0, warmup=10)
    series = [300]*30 + [3000]*10
    preds = ew.predict_series(series)
    check("EWMA không alarm pha normal", sum(preds[:30]) == 0)
    check("EWMA alarm khi spike", sum(preds[30:]) >= 1)


def test_policy():
    print("[policy]")
    pol = P.MitigationPolicy(up_windows=2, down_windows=3, rule_ttl_s=30)
    feat_spoof = {"source_count": 80}
    feat_fewsrc = {"source_count": 5}
    t = 100.0
    r1 = pol.update(1, feat_spoof, [], t)
    check("1 window attack chưa lên mức", r1["level"] == P.L0_MONITOR)
    r2 = pol.update(1, feat_spoof, [], t + 1)
    check("2 window attack -> L1", r2["level"] == P.L1_RATELIMIT)
    check("nguồn giả mạo -> rate-limit theo loại", r2["mode"] == "rate_limit_traffic")
    # nguồn xác định được -> per-source
    pol2 = P.MitigationPolicy(up_windows=1)
    r = pol2.update(1, feat_fewsrc, ["10.0.0.50"], 200.0)
    check("nguồn ít + có suspect -> per_source", r["mode"] == "per_source")
    check("có rule theo src IP", any(x.get("ip") == "10.0.0.50" for x in r["add_rules"]))
    # TTL hết hạn -> remove
    r_exp = pol2.update(0, feat_fewsrc, [], 200.0 + 40)
    check("rule hết TTL bị gỡ", len(r_exp["remove_rules"]) >= 1)


def test_metrics():
    print("[metrics]")
    probe = [{"ok": True, "latency_ms": 10}, {"ok": True, "latency_ms": 20},
             {"ok": False, "latency_ms": 0}, {"ok": True, "latency_ms": 30}]
    check("LSR = 3/4", abs(M.legitimate_success_rate(probe) - 0.75) < 1e-9)
    lp = M.latency_percentiles(probe)
    check("p50 latency hợp lý", 10 <= lp["p50"] <= 30)
    y_true = [0, 0, 1, 1, 1]
    y_pred = [0, 1, 1, 1, 0]
    sec = M.security_metrics(y_true, y_pred)
    check("precision = 2/3", abs(sec["precision"] - 2/3) < 1e-9)
    check("recall = 2/3", abs(sec["recall"] - 2/3) < 1e-9)
    labels = ["normal", "flash", "ddos", "ddos", "ddos"]
    ffpr = M.flash_false_positive_rate(labels, [0, 1, 1, 1, 0])
    check("flash_fpr = 1/1", abs(ffpr - 1.0) < 1e-9)
    check("detection_latency = 2.0", M.detection_latency(10.0, 12.0) == 2.0)
    check("detection_latency None khi không phát hiện",
          M.detection_latency(10.0, None) is None)
    # fairness (góp ý giảng viên)
    check("Jain = 1.0 khi mọi client bằng nhau",
          abs(M.jains_fairness([0.9, 0.9, 0.9]) - 1.0) < 1e-9)
    check("Jain < 1 khi lệch", M.jains_fairness([1.0, 0.0, 0.0]) < 0.4)
    check("Gini = 0 khi đều", abs(M.gini([0.9, 0.9, 0.9])) < 1e-9)
    check("Gini > 0 khi lệch", M.gini([1.0, 0.0, 0.0]) > 0.5)


def test_feature_slope():
    print("[feature slope]")
    check("linear_slope tăng đều = 1", abs(F.linear_slope([0, 1, 2, 3]) - 1.0) < 1e-9)
    check("linear_slope phẳng = 0", abs(F.linear_slope([5, 5, 5])) < 1e-9)
    check("linear_slope 1 điểm = 0", F.linear_slope([7]) == 0.0)


def test_stats():
    print("[stats]")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "aggregate", os.path.join(ROOT, "analysis", "aggregate.py"))
    AG = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(AG)
    est, lo, hi = AG.bootstrap_ci([0.9, 0.92, 0.88, 0.91, 0.9])
    check("bootstrap mean hợp lý", 0.88 <= est <= 0.92)
    check("bootstrap lo <= est <= hi", lo <= est <= hi)
    res = AG.holm_bonferroni({"a": 0.001, "b": 0.04, "c": 0.5})
    check("Holm: p nhỏ nhất bị hiệu chỉnh ×3", abs(res["a"][1] - 0.003) < 1e-9)
    check("Holm: p lớn không bác bỏ", res["c"][2] is False)


def test_dataset_builder():
    print("[dataset builder - tuần 6]")
    phases = [{"kind": "normal", "start": 0, "end": 10},
              {"kind": "flash", "start": 10, "end": 20},
              {"kind": "syn", "start": 20, "end": 30}]
    check("label normal giữa pha", BD.label_at(5, phases) == "normal")
    check("label flash giữa pha", BD.label_at(15, phases) == "flash")
    check("label ddos ở pha syn", BD.label_at(25, phases) == "ddos")
    # S5-style chồng pha: attack ưu tiên hơn flash
    overlap = [{"kind": "flash", "start": 0, "end": 30},
               {"kind": "udp", "start": 10, "end": 20}]
    check("chồng pha: attack > flash", BD.label_at(15, overlap) == "ddos")
    check("chồng pha: ngoài attack = flash", BD.label_at(5, overlap) == "flash")
    check("transition tại ranh giới pha", BD.is_transition(10, phases, 0.6) == 1)
    check("không transition giữa pha", BD.is_transition(5, phases, 0.6) == 0)


def test_baseline_eval():
    print("[baseline eval - tuần 6]")
    # Dựng dữ liệu nhỏ: normal thấp, flash CAO (giống ddos về volume), ddos cao.
    def mk(run, label, val, ts):
        return {"run_id": run, "label": label, "y": EB.LABEL01[label],
                "value": float(val), "timestamp": float(ts)}
    rows = []
    for run in ("r0", "r1", "r2", "r3"):
        for i in range(10):
            rows.append(mk(run, "normal", 300 + i, i))
        for i in range(10):
            rows.append(mk(run, "flash", 1500 + i, 10 + i))   # volume cao, lành tính
        for i in range(10):
            rows.append(mk(run, "ddos", 2200 + i, 20 + i))
    tr, te, tr_ids, te_ids = EB.group_split(rows, test_frac=0.5, seed=1)
    check("group_split tách run không trùng", set(tr_ids).isdisjoint(set(te_ids)))
    st = EB.fit_threshold(tr, pct=99, k=1.2)
    check("ngưỡng nằm trên normal, dưới flash", 330 < st.threshold < 1500)
    preds = [st.predict(r["value"]) for r in te]
    res = EB.evaluate(te, preds)
    check("threshold bắt hết ddos", res["recall_ddos"] == 1.0)
    check("Flash-FPR = 1.0 (báo nhầm flash)", abs(res["flash_fpr"] - 1.0) < 1e-9)
    check("normal-FPR = 0", res["normal_fpr"] == 0.0)
    # EWMA cũng không phân biệt được flash volume cao
    ew = EB.ewma_predict(te, alpha=0.2, k=3.0, warmup=5)
    res2 = EB.evaluate(te, ew)
    check("EWMA Flash-FPR > 0", res2["flash_fpr"] is not None and res2["flash_fpr"] > 0)


def test_port_features():
    print("[feature theo cổng - tuần 9]")
    prev = {"t": 0.0, "port_pkts": {3: 0, 11: 0, 1: 0}, "port_syn": {3: 0, 11: 0},
            "port_ack": {3: 0, 11: 0}, "port_udp": {12: 0}}
    cur = {"t": 1.0, "port_pkts": {3: 200, 11: 1500, 1: 400, 12: 900},
           "port_syn": {3: 30, 11: 1500}, "port_ack": {3: 160, 11: 2},
           "port_udp": {12: 900}}
    pr = F.port_rates(cur, prev)
    check("port_rates tính syn/giây", abs(pr[11]["syn"] - 1500) < 1e-9)
    sus = F.suspect_ports(pr, protected={1})
    check("cổng SYN flood bị nghi", 11 in sus)
    check("cổng UDP flood bị nghi", 12 in sus)
    check("client HTTP hợp lệ (ack >> syn) không bị nghi", 3 not in sus)
    check("cổng được bảo vệ (server) không bị nghi", 1 not in sus)


def test_policy_modes():
    print("[policy: thô / chọn lọc / feedback]")
    feat = {"source_count": 5}
    coarse = P.MitigationPolicy(up_windows=1, targeted=False)
    r = coarse.update(1, feat, [11], 0.0)
    check("coarse luôn rate-limit theo loại gói", r["mode"] == "rate_limit_traffic")
    tg = P.MitigationPolicy(up_windows=1, targeted=True)
    r = tg.update(1, feat, [11], 0.0)
    check("targeted -> rule theo cổng",
          any(x.get("port") == 11 and x["type"] == "port_rule" for x in r["add_rules"]))
    check("L1 dùng mark_limit", r["add_rules"][0]["action"] == "mark_limit")
    r = tg.update(1, feat, [11], 1.0)
    check("L2 đổi sang drop (replace)", r["level"] == P.L2_DROP and
          r["add_rules"] and r["add_rules"][0]["action"] == "drop" and
          r["add_rules"][0].get("replace"))
    spoof = P.MitigationPolicy(up_windows=1, targeted=True)
    r = spoof.update(1, {"source_count": 500}, [11], 0.0)
    check("cổng vào vẫn dùng được khi IP bị giả mạo", r["mode"] == "per_source")
    # feedback: LSR tụt -> leo mức ngay, không chờ hysteresis
    fb = P.MitigationPolicy(up_windows=3, targeted=True, feedback=True)
    r = fb.update(1, feat, [11], 0.0, lsr=0.4)
    check("feedback: LSR thấp -> lên L1 ngay", r["level"] == P.L1_RATELIMIT)
    nofb = P.MitigationPolicy(up_windows=3, targeted=True, feedback=False)
    r = nofb.update(1, feat, [11], 0.0, lsr=0.4)
    check("không feedback: vẫn chờ hysteresis", r["level"] == P.L0_MONITOR)
    # về L0 -> gỡ hết rule
    pol = P.MitigationPolicy(up_windows=1, down_windows=1, targeted=True)
    pol.update(1, feat, [11], 0.0)
    r = pol.update(0, feat, [], 1.0)
    check("về L0 gỡ hết rule", r["level"] == P.L0_MONITOR and "port:11" in r["remove_rules"])


def test_metric_alignment():
    print("[gán nhãn theo đồng hồ tuyệt đối]")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "compute_metrics", os.path.join(ROOT, "analysis", "compute_metrics.py"))
    CM = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(CM)
    gt = {"t0": 1000.0}
    rel = CM.rel_time_fn(gt, [{"wall": "1031.0", "elapsed": "21.0"}])
    check("rel = wall - t0 (không dùng elapsed lệch)",
          rel({"wall": "1031.0", "elapsed": "21.0"}) == 31.0)
    phases = [{"kind": "normal", "start": 0, "end": 30},
              {"kind": "syn", "start": 30, "end": 90}]
    check("label_at pha tấn công", CM.label_at(31.0, phases) == "ddos")
    check("near_boundary quanh ranh giới", CM.near_boundary(30.5, phases))


if __name__ == "__main__":
    test_port_features()
    test_policy_modes()
    test_metric_alignment()
    test_features()
    test_detectors()
    test_policy()
    test_metrics()
    test_feature_slope()
    test_stats()
    test_dataset_builder()
    test_baseline_eval()
    print("\nTẤT CẢ %d kiểm tra PASS." % passed)
