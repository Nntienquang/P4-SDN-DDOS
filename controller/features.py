"""
features.py — Chuyển counter/register thô thành feature vector theo cửa sổ.

Thiết kế QUAN TRỌNG: module này KHÔNG phụ thuộc P4Runtime. Nó nhận vào
"snapshot" (một dict số liệu thô đọc tại thời điểm t) và trả về feature của
window. Nhờ vậy:
  - Online: controller đọc P4 -> tạo snapshot -> gọi hàm ở đây.
  - Offline/test: nạp snapshot mô phỏng -> kiểm tra công thức mà không cần switch.

Cùng một hàm compute_features() được dùng cho cả huấn luyện và chạy online,
tránh lệch phân phối giữa offline và online (xem sổ tay tuần 8).

Snapshot là dict:
  {
    "t": <float giây, đồng hồ monotonic>,
    "total_pkts": int, "total_bytes": int,
    "syn": int, "ack": int, "udp": int,
    "port_pkts": {port_id: int, ...},     # packet theo cổng vào (per-source proxy)
    "src_popcount": int,                  # số bit 1 trong bitmap
    "bitmap_size": int,                   # kích thước bitmap (để ước lượng số nguồn)
  }
"""
import math

# Thứ tự feature cố định — dùng xuyên suốt train/online/report
FEATURE_NAMES = [
    "packet_rate",
    "byte_rate",
    "syn_rate",
    "udp_rate",
    "syn_ack_ratio",
    "source_count",
    "source_entropy",
    "growth_slope",
]


def estimate_sources(popcount, bitmap_size):
    """Ước lượng số nguồn khác nhau từ bitmap bằng linear counting.

    n_hat = -m * ln(V), với V = tỉ lệ bit còn 0 = (m - popcount) / m.
    Khi bitmap gần đầy (popcount ~ m) ước lượng kém tin cậy -> trả về m.
    """
    m = bitmap_size
    if m <= 0:
        return 0.0
    zeros = m - popcount
    if zeros <= 0:
        return float(m)
    V = zeros / m
    return -m * math.log(V)


def shannon_entropy_norm(counts):
    """Entropy Shannon chuẩn hóa [0,1] của phân bố 'counts' (vd packet theo cổng).

    H = -Σ p_i log2 p_i ; H_norm = H / log2(N) với N = số mục > 0.
    Entropy cao = traffic trải đều nhiều nguồn; thấp = tập trung.
    """
    total = sum(counts)
    nz = [c for c in counts if c > 0]
    if total <= 0 or len(nz) <= 1:
        return 0.0
    H = 0.0
    for c in nz:
        p = c / total
        H -= p * math.log2(p)
    return H / math.log2(len(nz))


def diff_snapshot(cur, prev):
    """Tính delta giữa 2 snapshot, trả về (dt, d_total, d_bytes, d_syn, d_ack,
    d_udp, d_port_counts_list). Counter tích lũy nên phải lấy hiệu."""
    dt = cur["t"] - prev["t"]
    if dt <= 0:
        dt = 1e-6
    d_total = max(0, cur["total_pkts"] - prev["total_pkts"])
    d_bytes = max(0, cur["total_bytes"] - prev["total_bytes"])
    d_syn = max(0, cur["syn"] - prev["syn"])
    d_ack = max(0, cur["ack"] - prev["ack"])
    d_udp = max(0, cur["udp"] - prev["udp"])
    ports = sorted(set(cur.get("port_pkts", {})) | set(prev.get("port_pkts", {})))
    d_ports = []
    for p in ports:
        c = cur.get("port_pkts", {}).get(p, 0)
        pv = prev.get("port_pkts", {}).get(p, 0)
        d_ports.append(max(0, c - pv))
    return dt, d_total, d_bytes, d_syn, d_ack, d_udp, d_ports


def compute_features(cur, prev, prev_packet_rate=None):
    """Trả về dict feature cho một window.

    prev_packet_rate: packet_rate của window TRƯỚC, để tính growth_slope.
    Với window đầu tiên, truyền None -> growth_slope = 0.
    """
    dt, d_total, d_bytes, d_syn, d_ack, d_udp, d_ports = diff_snapshot(cur, prev)

    packet_rate = d_total / dt
    byte_rate = d_bytes / dt
    syn_rate = d_syn / dt
    udp_rate = d_udp / dt
    # ACK/SYN: SYN flood có nhiều SYN mà ít ACK -> tỉ lệ thấp.
    # +1 ở mẫu để tránh chia 0 và ổn định khi SYN nhỏ.
    syn_ack_ratio = d_ack / (d_syn + 1.0)
    source_count = estimate_sources(cur.get("src_popcount", 0),
                                    cur.get("bitmap_size", 1))
    source_entropy = shannon_entropy_norm(d_ports)
    growth_slope = 0.0 if prev_packet_rate is None else (packet_rate - prev_packet_rate)

    return {
        "packet_rate": packet_rate,
        "byte_rate": byte_rate,
        "syn_rate": syn_rate,
        "udp_rate": udp_rate,
        "syn_ack_ratio": syn_ack_ratio,
        "source_count": source_count,
        "source_entropy": source_entropy,
        "growth_slope": growth_slope,
    }


def feature_vector(feat):
    """dict feature -> list theo đúng thứ tự FEATURE_NAMES (cho model)."""
    return [feat[name] for name in FEATURE_NAMES]
