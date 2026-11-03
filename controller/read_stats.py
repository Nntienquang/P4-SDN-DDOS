"""
read_stats.py — Đọc counter (P4Runtime) và register bitmap (simple_switch_CLI)
từ BMv2, trả về snapshot cho features.compute_features().

Counter đọc qua P4Runtime bằng WILDCARD (không truyền index) -> mỗi counter chỉ
1 RPC/chu kỳ poll, thay vì 1 RPC/ô (đỡ tải controller khi bị tấn công).

Register bitmap đọc qua simple_switch_CLI/Thrift — p4runtime_lib bản tutorial
không bọc sẵn ReadRegister. Nếu đọc register lỗi, source_count suy giảm về số
cổng vào đang có traffic (ghi cảnh báo).

Chỉ số counter khớp telemetry.p4:
  global_ctr[C_TOTAL=0, C_SYN=1, C_ACK=2, C_UDP=3]
  port_ctr[port*4 + {0,1,2,3}]  (cùng thứ tự total/syn/ack/udp theo cổng vào)
"""
import subprocess
import time

C_TOTAL, C_SYN, C_ACK, C_UDP = 0, 1, 2, 3
PORT_STATS = 4
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
        self._gid = self.h.get_counters_id(GLOBAL_CTR)
        self._pid = self.h.get_counters_id(PORT_CTR)

    def _read_all(self, cid):
        """Đọc mọi ô của counter -> {index: (packets, bytes)}."""
        out = {}
        for resp in self.sw.ReadCounters(cid):
            for ent in resp.entities:
                ce = ent.counter_entry
                out[ce.index.index] = (ce.data.packet_count, ce.data.byte_count)
        return out

    def _register_popcount(self):
        """Đếm số bit 1 trong src_bitmap qua simple_switch_CLI, rồi reset về 0.

        Trả về (popcount, ok). ok=False nếu CLI lỗi.
        """
        try:
            cmd = "register_read %s\nregister_reset %s\n" % (SRC_BITMAP, SRC_BITMAP)
            out = subprocess.run(
                ["simple_switch_CLI", "--thrift-port", str(self.thrift_port)],
                input=cmd, capture_output=True, text=True, timeout=5)
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
        g = self._read_all(self._gid)
        p = self._read_all(self._pid)
        ports, port_syn, port_ack, port_udp = {}, {}, {}, {}
        for idx, (pk, _) in p.items():
            port, kind = divmod(idx, PORT_STATS)
            if kind == C_TOTAL:
                ports[port] = pk
            elif kind == C_SYN:
                port_syn[port] = pk
            elif kind == C_ACK:
                port_ack[port] = pk
            elif kind == C_UDP:
                port_udp[port] = pk
        pop, ok = self._register_popcount()
        if not ok:
            pop = sum(1 for v in ports.values() if v > 0)
        return {
            "t": time.monotonic(),
            "wall": time.time(),
            "total_pkts": g.get(C_TOTAL, (0, 0))[0],
            "total_bytes": g.get(C_TOTAL, (0, 0))[1],
            "syn": g.get(C_SYN, (0, 0))[0],
            "ack": g.get(C_ACK, (0, 0))[0],
            "udp": g.get(C_UDP, (0, 0))[0],
            "port_pkts": ports,
            "port_syn": port_syn, "port_ack": port_ack, "port_udp": port_udp,
            "src_popcount": pop, "bitmap_size": self.bitmap_size,
        }
