"""
attack_lab.py — Vỏ gọi công cụ CHUẨN để sinh traffic tấn công TRONG LAB.

KHÔNG tự viết công cụ flood hiệu năng cao. File này chỉ dựng câu lệnh cho các
công cụ phổ biến (hping3, iperf3) với:
  - rào an toàn: đích phải là IP lab private (safety.assert_lab_target),
  - giới hạn rate và thời lượng bắt buộc,
  - chỉ dùng để KIỂM THỬ hệ thống phòng thủ trong Mininet cô lập.

SYN flood  -> hping3 (rate giới hạn bằng --interval)
UDP flood  -> iperf3 client UDP với -b (bitrate trần)

Nếu công cụ chưa cài, in hướng dẫn thay vì chạy. Mọi tham số rate phải do người
dùng đặt rõ, không có chế độ "flood tối đa".

Ví dụ (chạy trên host tấn công trong Mininet):
  python3 traffic/attack_lab.py --type syn --server 10.0.0.100 --pps 2000 --duration 60
  python3 traffic/attack_lab.py --type udp --server 10.0.0.100 --mbps 8 --duration 60
"""
import argparse
import shutil
import subprocess
import sys

from safety import assert_lab_target


def run_syn(server, pps, duration, port):
    if shutil.which("hping3") is None:
        print("Chưa cài hping3. Cài: sudo apt-get install hping3")
        return 1
    # interval micro giây = 1e6 / pps -> giới hạn tốc độ (không flood tối đa)
    interval_us = max(1, int(1_000_000 / max(1, pps)))
    cmd = ["hping3", "-S", "-p", str(port), "-i", "u%d" % interval_us,
           "-c", str(int(pps * duration)), server]
    print("[attack:syn] rate~%d pps, %ds ->" % (pps, duration), " ".join(cmd))
    return subprocess.call(cmd)


def run_udp(server, mbps, duration, port):
    if shutil.which("iperf3") is None:
        print("Chưa cài iperf3. Cài: sudo apt-get install iperf3")
        print("Lưu ý: server chạy 'iperf3 -s -p %d' trước." % port)
        return 1
    cmd = ["iperf3", "-c", server, "-u", "-b", "%dM" % mbps,
           "-t", str(int(duration)), "-p", str(port)]
    print("[attack:udp] trần %dMbps, %ds ->" % (mbps, duration), " ".join(cmd))
    return subprocess.call(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=["syn", "udp"], required=True)
    ap.add_argument("--server", required=True)
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--pps", type=int, default=2000, help="syn: gói/giây (trần)")
    ap.add_argument("--mbps", type=int, default=8, help="udp: Mbps trần")
    ap.add_argument("--port", type=int, default=80)
    args = ap.parse_args()
    assert_lab_target(args.server)
    if args.duration <= 0 or args.duration > 600:
        sys.exit("duration phải trong (0, 600] giây.")

    if args.type == "syn":
        sys.exit(run_syn(args.server, args.pps, args.duration, args.port))
    else:
        sys.exit(run_udp(args.server, args.mbps, args.duration, args.port))


if __name__ == "__main__":
    main()
