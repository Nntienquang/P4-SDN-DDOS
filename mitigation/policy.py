"""
policy.py — State machine mitigation với hysteresis, cooldown, TTL và feedback.

Chuyển quyết định "window này có DDoS" thành MỨC mitigation (L0/L1/L2) và
danh sách rule áp lên switch. Mục tiêu: giảm attack mà ít hại Flash Crowd.

Nguyên tắc:
  - Lên mức chỉ khi phát hiện DDoS liên tục >= up_windows (hysteresis).
  - Xuống mức chỉ sau >= down_windows window bình thường (cooldown).
    Về L0 thì gỡ hết rule.
  - Mỗi rule có TTL -> tự gỡ nếu không được làm mới, tránh false positive kéo dài.
  - Hai chế độ áp rule:
      targeted=True  : chặn THEO NGUỒN nghi vấn (cổng vào / src IP) — B3.
      targeted=False : rate-limit THÔ theo loại gói (SYN/UDP) cho mọi người —
                       mitigation "đơn giản" của B1/B2, dễ gây hại Flash Crowd.
  - Nguồn là src IP mà source_count cao (nghi giả mạo IP) -> không tin IP,
    chuyển sang rate-limit theo loại. Nguồn là CỔNG VÀO thì không giả mạo được.
  - Feedback (B3): nếu LSR đo từ probe tụt dưới lsr_target khi đang bị tấn công
    -> leo mức ngay (không chờ hysteresis); nếu LSR tốt và benign -> nới nhanh.

Nguồn nghi vấn (suspect_sources): chuỗi -> src IP, số nguyên -> cổng vào.

Thuần Python, test offline được. Controller dịch plan ra P4Runtime
(mitigation/mitigator.py).
"""

L0_MONITOR = 0
L1_RATELIMIT = 1
L2_DROP = 2
LEVEL_NAME = {0: "L0-monitor", 1: "L1-ratelimit", 2: "L2-drop"}


class MitigationPolicy:
    def __init__(self, up_windows=2, down_windows=5, rule_ttl_s=30.0,
                 spoof_source_threshold=50, targeted=True, feedback=False,
                 lsr_target=0.9):
        self.level = L0_MONITOR
        self.up_windows = up_windows
        self.down_windows = down_windows
        self.rule_ttl_s = rule_ttl_s
        self.spoof_source_threshold = spoof_source_threshold
        self.targeted = targeted
        self.feedback = feedback
        self.lsr_target = lsr_target
        self._attack_streak = 0
        self._benign_streak = 0
        self.active_rules = {}   # key -> {"expiry": t, "action": str}

    def _expire(self, now):
        expired = [k for k, r in self.active_rules.items() if r["expiry"] <= now]
        for k in expired:
            del self.active_rules[k]
        return expired

    def _touch(self, key, action, rule, add_rules, now):
        """Thêm/làm mới rule. Đổi action (mark->drop) thì phát lại có replace."""
        cur = self.active_rules.get(key)
        if cur is None or cur["action"] != action:
            r = dict(rule, key=key, action=action)
            if cur is not None:
                r["replace"] = True
            add_rules.append(r)
        self.active_rules[key] = {"expiry": now + self.rule_ttl_s, "action": action}

    def update(self, is_ddos, feat, suspect_sources, now, lsr=None):
        """Cập nhật mức và trả về kế hoạch hành động.

        is_ddos: 0/1 nhãn detector cho window hiện tại.
        feat: dict feature (để quyết định chặn theo nguồn hay theo loại).
        suspect_sources: list nguồn nghi vấn (str = src IP, int = cổng vào).
        now: thời gian hiện tại (giây).
        lsr: LSR gần đây đo từ probe (0..1) hoặc None — chỉ dùng khi feedback.

        Trả về dict: {level, level_name, add_rules, remove_rules, mode}
        """
        removed = self._expire(now)
        suspect_sources = list(suspect_sources or [])

        if is_ddos:
            self._attack_streak += 1
            self._benign_streak = 0
        else:
            self._benign_streak += 1
            self._attack_streak = 0

        hurting = (self.feedback and lsr is not None and lsr < self.lsr_target)
        up_need = 1 if (hurting and is_ddos) else self.up_windows
        down_need = self.down_windows
        if self.feedback and lsr is not None and not hurting:
            down_need = max(1, self.down_windows // 2)

        if self._attack_streak >= up_need and self.level < L2_DROP:
            self.level = min(L2_DROP, self.level + 1)
            self._attack_streak = 0
        elif self._benign_streak >= down_need and self.level > L0_MONITOR:
            self.level = max(L0_MONITOR, self.level - 1)
            self._benign_streak = 0
            if self.level == L0_MONITOR:
                removed += list(self.active_rules)
                self.active_rules.clear()

        add_rules = []
        mode = "none"
        if self.level >= L1_RATELIMIT and is_ddos:
            ports = [s for s in suspect_sources if isinstance(s, int)]
            ips = [s for s in suspect_sources if isinstance(s, str)]
            spoofed = feat.get("source_count", 0) >= self.spoof_source_threshold
            if ips and spoofed:
                ips = []      # IP không tin được khi nghi giả mạo
            action = "drop" if self.level == L2_DROP else "mark_limit"
            if self.targeted and (ports or ips):
                mode = "per_source"
                for p in ports:
                    self._touch("port:%d" % p, action,
                                {"type": "port_rule", "port": p},
                                add_rules, now)
                for ip in ips:
                    self._touch("src:%s" % ip, action,
                                {"type": "src_rule", "ip": ip}, add_rules, now)
            else:
                # Không xác định được nguồn (hoặc chế độ thô) -> rate-limit
                # theo LOẠI traffic: mọi gói SYN/UDP đi chung một hạn mức.
                mode = "rate_limit_traffic"
                self._touch("meter:syn_udp", "mark_limit",
                            {"type": "meter_on"}, add_rules, now)

        return {
            "level": self.level,
            "level_name": LEVEL_NAME[self.level],
            "add_rules": add_rules,
            "remove_rules": removed,
            "mode": mode,
        }
