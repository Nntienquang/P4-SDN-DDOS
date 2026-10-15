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

    url = "http://%s:%d/" % (args.server, args.port)
    interval = 1.0 / args.rate
    t0 = time.monotonic()
    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "ok", "latency_ms"])
        while time.monotonic() - t0 < args.duration:
            ok, lat = one_request(url, args.timeout)
            w.writerow([round(time.monotonic() - t0, 3), int(ok), round(lat, 2)])
            f.flush()
            time.sleep(max(0, interval))
    print("[probe] xong ->", args.out)


if __name__ == "__main__":
    main()
