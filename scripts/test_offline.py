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
for d in ("controller", "baseline", "mitigation", "metrics"):
    sys.path.insert(0, os.path.join(ROOT, d))

import features as F          # noqa: E402
import detectors as D         # noqa: E402
import policy as P            # noqa: E402
import service_metrics as M   # noqa: E402

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


if __name__ == "__main__":
    test_features()
    test_detectors()
    test_policy()
    test_metrics()
    print("\nTẤT CẢ %d kiểm tra PASS." % passed)
