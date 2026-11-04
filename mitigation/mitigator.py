"""
mitigator.py — Dịch kế hoạch từ policy.py thành rule P4Runtime trên switch.

- port_rule drop/mark_limit -> entry MyIngress.port_filter (match cổng vào)
- src_rule  drop/mark_limit -> entry MyIngress.src_filter (match src IP /32)
- meter_on                  -> 2 entry MyIngress.proto_filter (SYN, UDP) ->
                               mark_limit (hạn mức CHUNG, meter index 0)
- remove_rules              -> xóa các entry tương ứng (TTL / về L0)

Meter rl_meter (đơn vị gói) cấu hình 1 lần lúc khởi tạo qua simple_switch_CLI
(p4runtime_lib bản tutorial không có WriteMeter):
  index 0           = hạn mức chung cho rate-limit theo loại gói,
  index = số cổng   = hạn mức riêng cho một cổng bị rate-limit.

Trả về thời điểm ghi rule đầu tiên để tính mitigation latency.
"""
import subprocess
import time

PORT_FILTER = "MyIngress.port_filter"
SRC_FILTER = "MyIngress.src_filter"
PROTO_FILTER = "MyIngress.proto_filter"
METER = "MyIngress.rl_meter"
ACTIONS = {
    PORT_FILTER: {"drop": "MyIngress.drop", "mark_limit": "MyIngress.mark_limit_port"},
    SRC_FILTER: {"drop": "MyIngress.drop", "mark_limit": "MyIngress.mark_limit"},
}


class Mitigator:
    def __init__(self, sw, p4info_helper, global_pps=300, port_pps=50,
                 max_ports=16, thrift_port=9090):
        self.sw = sw
        self.h = p4info_helper
        self.global_pps = global_pps
        self.port_pps = port_pps
        self.max_ports = max_ports
        self.thrift_port = thrift_port
        self._entries = {}      # key -> [table_entry, ...]
        self.n_writes = 0       # số message P4Runtime ghi (chi phí control plane)
        self._configure_meters()

    # ---------- meter ----------
    def _configure_meters(self):
        """Đặt rate cho mọi ô meter. simple_switch_CLI: meter_set_rates <name>
        <idx> <cir>:<burst> <pir>:<burst>, rate tính theo gói/MICRO giây."""
        lines = []
        for idx in range(self.max_ports):
            pps = self.global_pps if idx == 0 else self.port_pps
            r = pps / 1e6
            burst = max(1, int(pps / 10))
            lines.append("meter_set_rates %s %d %.9f:%d %.9f:%d" %
                         (METER, idx, r, burst, r, burst))
        try:
            out = subprocess.run(
                ["simple_switch_CLI", "--thrift-port", str(self.thrift_port)],
                input="\n".join(lines) + "\n", capture_output=True, text=True,
                timeout=10)
            if "Invalid" in out.stdout or "Error" in out.stdout:
                print("[warn] meter_set_rates:", out.stdout[-300:])
            else:
                print("[mitigation] meter: chung %d pps, theo cổng %d pps" %
                      (self.global_pps, self.port_pps))
        except Exception as e:
            print("[warn] cấu hình meter lỗi:", e)

    # ---------- build entries ----------
    def _entries_for(self, rule):
        t = rule["type"]
        if t == "port_rule":
            return [self.h.buildTableEntry(
                table_name=PORT_FILTER,
                match_fields={"standard_metadata.ingress_port": int(rule["port"])},
                action_name=ACTIONS[PORT_FILTER][rule["action"]])]
        if t == "src_rule":
            return [self.h.buildTableEntry(
                table_name=SRC_FILTER,
                match_fields={"hdr.ipv4.srcAddr": [rule["ip"], 32]},
                action_name=ACTIONS[SRC_FILTER][rule["action"]])]
        if t == "meter_on":
            return [self.h.buildTableEntry(
                table_name=PROTO_FILTER,
                match_fields={"meta.is_syn": syn, "meta.is_udp": udp},
                action_name="MyIngress.mark_limit")
                for syn, udp in ((1, 0), (0, 1))]
        raise ValueError(t)

    def _delete(self, key):
        for te in self._entries.pop(key, []):
            try:
                self.sw.DeleteTableEntry(te)
                self.n_writes += 1
            except Exception as e:
                print("[warn] xóa rule lỗi:", e)

    def apply_plan(self, plan):
        """Thực thi plan (dict từ policy.update()). Trả về thời điểm ghi rule."""
        write_t = None
        for key in plan.get("remove_rules", []):
            self._delete(key)
        for rule in plan.get("add_rules", []):
            key = rule["key"]
            if key in self._entries:          # đổi action -> xóa rồi ghi lại
                self._delete(key)
            written = []
            for te in self._entries_for(rule):
                try:
                    self.sw.WriteTableEntry(te)
                    self.n_writes += 1
                    written.append(te)
                except Exception as e:
                    print("[warn] ghi rule %s lỗi: %s" % (key, e))
            if written:
                self._entries[key] = written
                write_t = write_t or time.monotonic()
        return write_t

    def active_keys(self):
        return sorted(self._entries)

    def clear_all(self):
        for key in list(self._entries):
            self._delete(key)
