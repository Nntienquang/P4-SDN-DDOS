"""
mitigator.py — Dịch kế hoạch từ policy.py thành rule P4Runtime trên switch.

- src_rule drop/mark_limit  -> entry bảng MyIngress.src_filter (match src IP /32)
- meter_on                  -> cấu hình meter MyIngress.syn_udp_meter (rate RED)
- remove_rules              -> xóa entry tương ứng (TTL)

Giữ map key -> table_entry để xóa đúng entry khi hết TTL. Thời điểm ghi rule
được trả về để controller tính mitigation latency.
"""
import time

SRC_FILTER = "MyIngress.src_filter"
A_DROP = "MyIngress.drop"
A_MARK = "MyIngress.mark_limit"
METER = "MyIngress.syn_udp_meter"


class Mitigator:
    def __init__(self, sw, p4info_helper, meter_cir_bps=200000, meter_pir_bps=400000):
        self.sw = sw
        self.h = p4info_helper
        self.meter_cir_bps = meter_cir_bps
        self.meter_pir_bps = meter_pir_bps
        self._entries = {}      # key -> table_entry (để xóa)
        self._meter_set = False

    def _src_entry(self, ip, action):
        action_name = A_DROP if action == "drop" else A_MARK
        return self.h.buildTableEntry(
            table_name=SRC_FILTER,
            match_fields={"hdr.ipv4.srcAddr": [ip, 32]},
            action_name=action_name,
            action_params={})

    def apply_plan(self, plan):
        """Thực thi plan (dict từ policy.update()). Trả về thời điểm ghi rule."""
        write_t = None
        for rule in plan.get("add_rules", []):
            if rule["type"] == "src_rule":
                te = self._src_entry(rule["ip"], rule["action"])
                try:
                    self.sw.WriteTableEntry(te)
                    self._entries[rule["key"]] = te
                    write_t = time.monotonic()
                except Exception as e:
                    print("[warn] ghi src_rule lỗi:", e)
            elif rule["type"] == "meter_on":
                self._configure_meter()
                write_t = time.monotonic()
        for key in plan.get("remove_rules", []):
            te = self._entries.pop(key, None)
            if te is not None:
                try:
                    self.sw.DeleteTableEntry(te)
                except Exception as e:
                    print("[warn] xóa rule lỗi:", e)
        return write_t

    def _configure_meter(self):
        """Nạp cấu hình meter 2 tốc độ cho index 0 (gói SYN/UDP nghi vấn).

        Dùng simple_switch_CLI nếu WriteMeter qua P4Runtime không có sẵn.
        """
        if self._meter_set:
            return
        try:
            import subprocess
            # rate theo byte/giây -> simple_switch_CLI meter_set_rates dùng
            # cặp (info_rate: bytes/microsec, burst_size). Quy đổi đơn giản.
            cir = self.meter_cir_bps / 8.0 / 1e6
            pir = self.meter_pir_bps / 8.0 / 1e6
            cmd = "meter_set_rates %s 0 %f:2000 %f:4000\n" % (
                METER.split(".")[-1], cir, pir)
            subprocess.run(["simple_switch_CLI"], input=cmd,
                           capture_output=True, text=True, timeout=5)
            self._meter_set = True
            print("[mitigation] đã bật meter rate-limit SYN/UDP")
        except Exception as e:
            print("[warn] cấu hình meter lỗi:", e)

    def clear_all(self):
        for key, te in list(self._entries.items()):
            try:
                self.sw.DeleteTableEntry(te)
            except Exception:
                pass
        self._entries.clear()
