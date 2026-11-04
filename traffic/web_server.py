#!/usr/bin/env python3
"""
web_server.py — Web server tĩnh cho lab (chạy trên host srv trong Mininet).

Khác `python3 -m http.server`: cho đặt listen backlog (mặc định của
http.server chỉ là 5 — quá nhỏ so với server thật, nginx mặc định 511, nên
SYN flood vài trăm gói/giây đã làm tê liệt). Đặt backlog thực tế hơn giúp
thí nghiệm phản ánh đúng hơn tác động của tấn công và của mitigation.

Chạy:  python3 traffic/web_server.py --port 80 --backlog 128 --root /tmp/lab_www
"""
import argparse
import functools
import http.server
import socketserver


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=80)
    ap.add_argument("--backlog", type=int, default=128)
    ap.add_argument("--root", default="/tmp/lab_www")
    args = ap.parse_args()
    Server.request_queue_size = args.backlog
    handler = functools.partial(QuietHandler, directory=args.root)
    with Server(("0.0.0.0", args.port), handler) as httpd:
        print("[web] :%d backlog=%d root=%s" % (args.port, args.backlog, args.root))
        httpd.serve_forever()


if __name__ == "__main__":
    main()
