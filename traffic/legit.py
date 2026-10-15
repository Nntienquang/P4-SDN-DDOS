"""
legit.py — Sinh traffic HỢP LỆ: Normal và Flash Crowd.

Cả hai mô phỏng người dùng thật: hoàn tất handshake, gửi request HTTP, nhận
response, có think time ngẫu nhiên. Khác nhau ở số lượng và cách tăng:
  - Normal: ít client, rate thấp-vừa, đều.
  - Flash:  số client tăng dần (ramp-up) -> đỉnh -> giảm, như sự kiện mở đăng ký.

Flash Crowd PHẢI hợp lệ (không phải flood đổi nhãn) — đây là điểm cốt lõi của
đề tài. Dùng nhiều host/IP để có đa dạng nguồn.

Chạy ví dụ:
  python3 traffic/legit.py --mode normal --server 10.0.0.100 --duration 120 --clients 4
  python3 traffic/legit.py --mode flash  --server 10.0.0.100 --duration 120 --peak 40
"""
import argparse
import random
import threading
import time
import urllib.request

from safety import assert_lab_target

_stop = threading.Event()
_lock = threading.Lock()
_stats = {"sent": 0, "ok": 0}


def client_loop(url, timeout, think_mean):
    rng = random.Random()
    while not _stop.is_set():
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                r.read(256)
                ok = 200 <= r.status < 300
        except Exception:
            ok = False
        with _lock:
            _stats["sent"] += 1
            _stats["ok"] += int(ok)
        # think time phân phối mũ -> giống người dùng thật
        _stop.wait(rng.expovariate(1.0 / think_mean))


def run_normal(url, duration, clients, timeout, think):
    threads = [threading.Thread(target=client_loop, args=(url, timeout, think),
                                daemon=True) for _ in range(clients)]
    for t in threads:
        t.start()
    time.sleep(duration)
    _stop.set()


def run_flash(url, duration, peak, timeout, think):
    """Ramp-up tuyến tính tới 'peak' client ở giữa, rồi giảm."""
    active = []
    start = time.monotonic()
    while time.monotonic() - start < duration and not _stop.is_set():
        frac = (time.monotonic() - start) / duration
        # tam giác: 0 -> peak ở frac=0.5 -> 0
        target = int(peak * (1 - abs(2 * frac - 1)))
        while len(active) < target:
            th = threading.Thread(target=client_loop, args=(url, timeout, think),
                                  daemon=True)
            th.start(); active.append(th)
        time.sleep(1.0)
    _stop.set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["normal", "flash"], required=True)
    ap.add_argument("--server", required=True)
    ap.add_argument("--port", type=int, default=80)
    ap.add_argument("--duration", type=float, default=120)
    ap.add_argument("--clients", type=int, default=4, help="normal: số client")
    ap.add_argument("--peak", type=int, default=40, help="flash: số client đỉnh")
    ap.add_argument("--think", type=float, default=1.0, help="think time TB (giây)")
    ap.add_argument("--timeout", type=float, default=2.0)
    args = ap.parse_args()
    assert_lab_target(args.server)

    url = "http://%s:%d/" % (args.server, args.port)
    print("[legit:%s] -> %s trong %.0fs" % (args.mode, url, args.duration))
    if args.mode == "normal":
        run_normal(url, args.duration, args.clients, args.timeout, args.think)
    else:
        run_flash(url, args.duration, args.peak, args.timeout, args.think)
    rate = _stats["ok"] / _stats["sent"] if _stats["sent"] else 0
    print("[legit] sent=%d ok=%d success=%.3f" %
          (_stats["sent"], _stats["ok"], rate))


if __name__ == "__main__":
    main()
