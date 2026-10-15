"""
policy.py — State machine mitigation với hysteresis, cooldown và TTL.

Chuyển quyết định "window này có DDoS" thành MỨC mitigation (L0/L1/L2) và
danh sách rule áp lên switch. Mục tiêu: giảm attack mà ít hại Flash Crowd.

Nguyên tắc:
  - Lên mức chỉ khi phát hiện DDoS liên tục >= up_windows (hysteresis).
  - Xuống mức chỉ sau >= down_windows window bình thường (cooldown).
  - Mỗi rule chặn theo src IP có TTL -> controller tự gỡ, tránh false positive
    kéo dài.
  - Khi nguồn bị giả mạo (nhiều nguồn mới, SYN/UDP cao): rate-limit theo LOẠI
    traffic thay vì theo IP.

Thuần Python, test offline được. Controller thật gọi apply() rồi dịch rule ra
P4Runtime (xem mitigation/mitigator.py).
"""

L0_MONITOR = 0
L1_RATELIMIT = 1
L2_DROP = 2
LEVEL_NAME = {0: "L0-monitor", 1: "L1-ratelimit", 2: "L2-drop"}


class MitigationPolicy:
    def __init__(self, up_windows=2, down_windows=5, rule_ttl_s=30.0,
                 spoof_source_threshold=50):
        self.level = L0_MONITOR
        self.up_windows = up_windows
        self.down_windows = down_windows
        self.rule_ttl_s = rule_ttl_s
        self.spoof_source_threshold = spoof_source_threshold
        self._attack_streak = 0
        self._benign_streak = 0
        self.active_rules = {}   # key -> expiry_time

    def _expire(self, now):
        expired = [k for k, exp in self.active_rules.items() if exp <= now]
        for k in expired:
            del self.active_rules[k]
        return expired

    def update(self, is_ddos, feat, suspect_sources, now):
        """Cập nhật mức và trả về kế hoạch hành động.

        is_ddos: 0/1 nhãn detector cho window hiện tại.
        feat: dict feature (để quyết định chặn theo IP hay theo loại).
        suspect_sources: list src IP nghi vấn (rate cao / SYN chưa hoàn tất).
        now: thời gian hiện tại (giây).

        Trả về dict: {level, add_rules, remove_rules, mode}
        """
        removed = self._expire(now)

        if is_ddos:
            self._attack_streak += 1
            self._benign_streak = 0
        else:
            self._benign_streak += 1
            self._attack_streak = 0

        # chuyển mức
        if self._attack_streak >= self.up_windows and self.level < L2_DROP:
            self.level = min(L2_DROP, self.level + 1)
            self._attack_streak = 0
        elif self._benign_streak >= self.down_windows and self.level > L0_MONITOR:
            self.level = max(L0_MONITOR, self.level - 1)
            self._benign_streak = 0

        add_rules = []
        mode = "none"
        if self.level >= L1_RATELIMIT and is_ddos:
            spoofed = feat.get("source_count", 0) >= self.spoof_source_threshold
            if spoofed or not suspect_sources:
                # Nguồn giả mạo -> rate-limit theo loại traffic (meter SYN/UDP)
                mode = "rate_limit_traffic"
                key = "meter:syn_udp"
                if key not in self.active_rules:
                    add_rules.append({"type": "meter_on", "key": key})
                self.active_rules[key] = now + self.rule_ttl_s
            else:
                # Nguồn xác định được -> xử lý theo src IP
                mode = "per_source"
                action = "drop" if self.level == L2_DROP else "mark_limit"
                for ip in suspect_sources:
                    key = "src:%s:%s" % (ip, action)
                    if key not in self.active_rules:
                        add_rules.append({"type": "src_rule", "ip": ip,
                                          "action": action, "key": key})
                    self.active_rules[key] = now + self.rule_ttl_s

        return {
            "level": self.level,
            "level_name": LEVEL_NAME[self.level],
            "add_rules": add_rules,
            "remove_rules": removed,
            "mode": mode,
        }
