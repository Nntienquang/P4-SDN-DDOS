"""
read_stats.py — Đọc counter (P4Runtime) và register bitmap (simple_switch_CLI)
từ BMv2, trả về snapshot cho features.compute_features().

Counter đọc qua P4Runtime (ổn định, có trong p4runtime_lib).
Register bitmap đọc qua simple_switch_CLI/Thrift — đây là fallback giáo trình
đã nêu, vì p4runtime_lib bản tutorial không bọc sẵn ReadRegister. Nếu đọc
register lỗi, source_count suy giảm về số cổng vào đang có traffic (ghi cảnh báo).

Chỉ số counter khớp telemetry.p4: C_TOTAL=0, C_SYN=1, C_ACK=2, C_UDP=3.
"""
import subprocess
import time

C_TOTAL, C_SYN, C_ACK, C_UDP = 0, 1, 2, 3
GLOBAL_CTR = "MyIngress.global_ctr"
PORT_CTR = "MyIngress.port_ctr"
SRC_BITMAP = "MyIngress.src_bitmap"


class StatReader:
    def __init__(self, sw, p4info_helper, thrift_port=9090,
                 max_ports=16, bitmap_size=4096):
        self.sw = sw
        self.h = p4info_helper
        self.thrift_port = thrift_port
        self.max_ports = max_ports
        self.bitmap_size = bitmap_size
        self._warned_reg = False

    def _counter(self, name, index):
        """Đọc 1 ô counter -> (packets, bytes)."""
        cid = self.h.get_counters_id(name)
        for resp in self.sw.ReadCounters(cid, index):
            for ent in resp.entities:
                d = ent.counter_entry.data
                return d.packet_count, d.byte_count
        return 0, 0

    def _port_counts(self):
        counts = {}
        cid = self.h.get_counters_id(PORT_CTR)
        for p in range(self.max_ports):
            for resp in self.sw.ReadCounters(cid, p):
                for ent in resp.entities:
                    counts[p] = ent.counter_entry.data.packet_count
        return counts

    def _register_popcount(self):
        """Đếm số bit 1 trong src_bitmap qua simple_switch_CLI, rồi reset về 0.

        Trả về (popcount, ok). ok=False nếu CLI lỗi.
        """
        try:
            cmd = "register_read %s\nregister_reset %s\n" % (SRC_BITMAP, SRC_BITMAP)
            out = subprocess.run(
                ["simple_switch_CLI", "--thrift-port", str(self.thrift_port)],
                input=cmd, capture_output=True, text=True, timeout=5)
            # dòng kết quả dạng: "<name>= 0, 1, 0, 1, ..."
            pop = 0
            for line in out.stdout.splitlines():
                if "=" in line and SRC_BITMAP.split(".")[-1] in line:
                    vals = line.split("=", 1)[1]
                    pop = sum(1 for v in vals.split(",") if v.strip() == "1")
                    break
            return pop, True
        except Exception as e:
            if not self._warned_reg:
                print("[warn] đọc register lỗi (%s); dùng proxy số cổng." % e)
                self._warned_reg = True
            return None, False

    def read_snapshot(self):
        tp, tb = self._counter(GLOBAL_CTR, C_TOTAL)
        sp, _ = self._counter(GLOBAL_CTR, C_SYN)
        ap, _ = self._counter(GLOBAL_CTR, C_ACK)
        up, _ = self._counter(GLOBAL_CTR, C_UDP)
        ports = self._port_counts()
        pop, ok = self._register_popcount()
        if not ok:
            # proxy: số cổng có traffic coi như số "nguồn"
            pop = sum(1 for v in ports.values() if v > 0)
        return {
            "t": time.monotonic(),
            "total_pkts": tp, "total_bytes": tb,
            "syn": sp, "ack": ap, "udp": up,
            "port_pkts": ports,
            "src_popcount": pop, "bitmap_size": self.bitmap_size,
        }
