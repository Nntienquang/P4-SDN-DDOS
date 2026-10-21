"""
service_metrics.py — Tính metric đánh giá, chia 4 trục Security/User/Speed/Cost.

Đầu vào là các log do thí nghiệm sinh ra (probe client, generator ground truth,
detector log). Hàm ở đây thuần tính toán nên test offline được.
"""
from statistics import mean, median


# ---------- Trục User (quan trọng nhất cho đề tài) ----------
def legitimate_success_rate(probe_results):
    """LSR = số request hợp lệ thành công / tổng request hợp lệ gửi đi.

    probe_results: list dict {"ok": bool, "latency_ms": float}.
    """
    if not probe_results:
        return None
    ok = sum(1 for r in probe_results if r["ok"])
    return ok / len(probe_results)


def legitimate_drop_rate(legit_pkts_sent, legit_pkts_dropped):
    """LDR = packet hợp lệ bị drop bởi rule / packet hợp lệ gửi đi."""
    if legit_pkts_sent <= 0:
        return 0.0
    return legit_pkts_dropped / legit_pkts_sent


def latency_percentiles(probe_results):
    lat = [r["latency_ms"] for r in probe_results if r["ok"]]
    if not lat:
        return {"p50": None, "p95": None}
    lat.sort()
    return {"p50": median(lat), "p95": _percentile(lat, 95)}


def jains_fairness(values):
    """Jain's fairness index trên phân bố (vd LSR của từng client hợp lệ).

    J = (Σx)^2 / (n · Σx^2), nằm trong [1/n, 1]; =1 là công bằng tuyệt đối.
    Trả lời: mitigation có đối xử công bằng giữa các user hợp lệ không
    (góp ý giảng viên). None nếu không có dữ liệu.
    """
    xs = [float(v) for v in values if v is not None]
    if not xs:
        return None
    s = sum(xs)
    s2 = sum(x * x for x in xs)
    if s2 == 0:
        return 1.0
    return (s * s) / (len(xs) * s2)


def gini(values):
    """Hệ số Gini của phân bố (0 = đều tuyệt đối, 1 = bất bình đẳng tối đa).

    Bổ sung bên cạnh Jain's index để mô tả độ lệch LSR giữa các client.
    """
    xs = sorted(float(v) for v in values if v is not None)
    n = len(xs)
    if n == 0 or sum(xs) == 0:
        return 0.0
    cum = 0.0
    for i, x in enumerate(xs, 1):
        cum += i * x
    return (2 * cum) / (n * sum(xs)) - (n + 1) / n


def lsr_per_client(probe_results_by_client):
    """LSR cho TỪNG client -> list, để tính fairness.

    probe_results_by_client: dict {client_id: [ {ok, latency_ms}, ... ]}.
    """
    out = []
    for _, results in probe_results_by_client.items():
        lsr = legitimate_success_rate(results)
        if lsr is not None:
            out.append(lsr)
    return out


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (p / 100.0) * (len(sorted_vals) - 1)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


# ---------- Trục Security ----------
def confusion(y_true, y_pred, positive=1):
    """Trả về (TP, FP, TN, FN) với lớp 'positive' = DDoS."""
    tp = fp = tn = fn = 0
    for t, p in zip(y_true, y_pred):
        tp += (t == positive and p == positive)
        fp += (t != positive and p == positive)
        tn += (t != positive and p != positive)
        fn += (t == positive and p != positive)
    return tp, fp, tn, fn


def security_metrics(y_true, y_pred, positive=1):
    tp, fp, tn, fn = confusion(y_true, y_pred, positive)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "fpr": fpr,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn}


def flash_false_positive_rate(labels, preds, flash_label="flash", attack_pred=1):
    """Flash-FPR = window Flash bị dự đoán DDoS / tổng window Flash.

    labels: nhãn thật dạng chuỗi ("normal"/"flash"/"ddos").
    preds : 0/1 (1 = dự đoán DDoS).
    """
    flash_idx = [i for i, l in enumerate(labels) if l == flash_label]
    if not flash_idx:
        return None
    fp = sum(1 for i in flash_idx if preds[i] == attack_pred)
    return fp / len(flash_idx)


# ---------- Trục Speed ----------
def detection_latency(attack_start_t, first_alarm_t):
    """Giây từ khi attack bắt đầu tới alarm đầu tiên. None nếu không phát hiện."""
    if first_alarm_t is None:
        return None
    return max(0.0, first_alarm_t - attack_start_t)


# ---------- Tổng hợp một run ----------
def summarize_run(y_true01, y_pred01, labels, probe_results,
                  legit_sent, legit_dropped, attack_start_t, first_alarm_t,
                  cpu_samples=None, ctrl_messages=None):
    """Gom metric của một lần chạy thành dict phẳng để ghi CSV."""
    sec = security_metrics(y_true01, y_pred01)
    lat = latency_percentiles(probe_results)
    out = {
        "precision": sec["precision"], "recall": sec["recall"],
        "f1": sec["f1"], "fpr": sec["fpr"],
        "flash_fpr": flash_false_positive_rate(labels, y_pred01),
        "lsr": legitimate_success_rate(probe_results),
        "ldr": legitimate_drop_rate(legit_sent, legit_dropped),
        "lat_p50_ms": lat["p50"], "lat_p95_ms": lat["p95"],
        "detection_latency_s": detection_latency(attack_start_t, first_alarm_t),
        "cpu_mean_pct": mean(cpu_samples) if cpu_samples else None,
        "ctrl_messages": ctrl_messages,
    }
    return out
