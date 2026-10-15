"""
safety.py — Rào an toàn: CHỈ cho phép sinh traffic thử nghiệm trong lab cô lập.

Mọi script traffic (kể cả flood thử nghiệm) phải gọi assert_lab_target() trước
khi chạy. Hàm này từ chối nếu đích KHÔNG phải IP private trong dải lab, để tránh
vô tình gửi traffic ra ngoài. Đây là yêu cầu đạo đức nghiên cứu của đề tài.
"""
import ipaddress
import sys

# Dải IP được phép (private, dùng trong Mininet). Chỉnh khớp configs/topology.yaml.
ALLOWED_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
]


def is_lab_target(ip):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if not addr.is_private:
        return False
    return any(addr in net for net in ALLOWED_NETS)


def assert_lab_target(ip):
    if not is_lab_target(ip):
        sys.stderr.write(
            "\n[AN TOÀN] Từ chối: '%s' không thuộc dải lab private cho phép.\n"
            "Mọi traffic thử nghiệm chỉ được chạy trong Mininet cô lập.\n"
            "Nếu đây đúng là đích lab, thêm dải vào ALLOWED_NETS.\n\n" % ip)
        sys.exit(2)
