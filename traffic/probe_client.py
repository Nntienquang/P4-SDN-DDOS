"""
probe_client.py — Probe client hợp lệ đo Legitimate Success Rate và latency.

Gửi request HTTP đều đặn tới server và ghi mỗi request thành công hay không,
latency bao nhiêu. Đây là "người dùng thật" để đo xem mitigation có chặn nhầm
không. Output: CSV mỗi dòng một request -> metrics/service_metrics tính LSR.

Chạy trên host probe:  python3 traffic/probe_client.py --server 10.0.0.100 \
    --rate 5 --duration 120 --out logs/probe.csv
"""
import argparse
import csv
import time
import urllib.request

from safety import assert_lab_target


def one_request(url, timeout):
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            r.read(256)
            ok = 200 <= r.status < 300
    except Exception:
        ok = False
    return ok, (time.monotonic() - t0) * 1000.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--port", type=int, default=80)
    ap.add_argument("--rate", type=float, default=5, help="request/giây")
    ap.add_argument("--duration", type=float, default=120)
    ap.add_argument("--timeout", type=float, default=2.0)
    ap.add_argument("--out", default="logs/probe.csv")
    args = ap.parse_args()
    assert_lab_target(args.server)

    # OPEN-LOOP: request thứ k được bắn đúng lúc t0 + k/rate trong thread riêng,
    # KHÔNG chờ request trước xong. Nếu chờ tuần tự (closed-loop), khi server
    # chậm probe gửi ít đi -> pha tấn công bị đếm ít mẫu -> LSR bị thổi phồng.
    import os
    import threading
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    url = "http://%s:%d/" % (args.server, args.port)
    interval = 1.0 / args.rate
    lock = threading.Lock()
    f = open(args.out, "w", newline="")
    w = csv.writer(f)
    w.writerow(["t", "ok", "latency_ms", "wall"])
    t0 = time.monotonic()

    def fire(k):
        wall = time.time()
        ok, lat = one_request(url, args.timeout)
        with lock:
            w.writerow([round(k * interval, 3), int(ok), round(lat, 2),
                        round(wall, 3)])
            f.flush()

    threads = []
    k = 0
    while True:
        due = t0 + k * interval
        if due - t0 >= args.duration:
            break
        time.sleep(max(0.0, due - time.monotonic()))
        th = threading.Thread(target=fire, args=(k,), daemon=True)
        th.start()
        threads.append(th)
        k += 1
    for th in threads:
        th.join(timeout=args.timeout + 1)
    f.close()
    print("[probe] xong ->", args.out)


if __name__ == "__main__":
    main()
