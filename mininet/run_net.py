#!/usr/bin/env python3
"""
run_net.py — Dựng Mininet + BMv2, nạp pipeline P4, và (tùy chọn) chạy một
kịch bản traffic tự động rồi thoát; nếu không có --scenario thì vào Mininet CLI.

Chạy qua Makefile:  make run                       (vào CLI)
                    make run SCENARIO=configs/scenarios/S5.yaml

Phải chạy bằng sudo. Cần repo p4lang/tutorials (P4_UTILS).

Kịch bản (configs/scenarios/*.yaml) định nghĩa các pha theo thời gian và ghi
ground_truth.json (nhãn + danh sách IP tấn công) để tính metric sau.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from common import load_yaml, load_json, save_json  # noqa: E402

SRV_BACKLOG = int(os.environ.get("SRV_BACKLOG", "128"))
P4_UTILS = os.environ.get("P4_UTILS", os.path.join(ROOT, "..", "tutorials", "utils"))
sys.path.insert(0, P4_UTILS)


def build_net(p4info, bmv2_json, runtime_json):
    from p4_mininet import P4Host
    from p4runtime_switch import P4RuntimeSwitch
    from mininet.net import Mininet
    from mininet.link import TCLink
    from mininet.topo import Topo

    topo_spec = load_json(os.path.join(ROOT, "mininet", "topology.json"))

    class LabTopo(Topo):
        def build(self):
            sw = self.addSwitch("s1", cls=P4RuntimeSwitch, sw_path="simple_switch_grpc",
                                json_path=bmv2_json, grpc_port=50051, thrift_port=9090,
                                pcap_dump=False, log_console=False,
                                log_file="logs/s1.log", device_id=0)
            for name, h in topo_spec["hosts"].items():
                self.addHost(name, ip=h["ip"], mac=h["mac"])
            for link in topo_spec["links"]:
                h = link["node1"]
                _, port = link["node2"].split("-p")
                self.addLink(h, sw, port2=int(port),
                             delay=link.get("latency", "1ms"),
                             bw=link.get("bandwidth", 10))

    net = Mininet(topo=LabTopo(), host=P4Host, link=TCLink, controller=None)
    net.start()
    # chạy lệnh cấu hình host (route/arp)
    for name, h in topo_spec["hosts"].items():
        node = net.get(name)
        for cmd in h.get("commands", []):
            node.cmd(cmd)
    return net


def program_switch(p4info, bmv2_json, runtime_json):
    import p4runtime_lib.simple_controller
    workdir = ROOT
    # simple_controller.program_switch cần FILE HANDLE (nó gọi json.load(f)),
    # không phải chuỗi đường dẫn -> phải mở file.
    with open(runtime_json, "r") as sw_conf_file:
        p4runtime_lib.simple_controller.program_switch(
            addr="127.0.0.1:50051", device_id=0,
            sw_conf_file=sw_conf_file, workdir=workdir,
            proto_dump_fpath="logs/p4runtime_bootstrap.txt",
            runtime_json=runtime_json)
    print("[run_net] đã nạp pipeline + forwarding vào s1.")


def start_server(net):
    srv = net.get("srv")
    # web server tĩnh (1 trang nhỏ cố định ~1KB) để probe/legit gửi request
    srv.cmd("mkdir -p /tmp/lab_www && python3 -c \"open('/tmp/lab_www/index.html',"
            "'w').write('<html><body>'+'lab-ok '*140+'</body></html>')\"")
    srv.cmd("python3 %s/traffic/web_server.py --port 80 --backlog %d "
            "--root /tmp/lab_www >/tmp/srv.log 2>&1 &" % (ROOT, SRV_BACKLOG))
    # iperf3 server cho UDP flood test
    srv.cmd("iperf3 -s -p 5201 >/tmp/iperf3s.log 2>&1 &")
    time.sleep(1)
    print("[run_net] server HTTP:80 + iperf3:5201 đã chạy.")


def _jitter(rng, value, frac):
    """Nhân 'value' với hệ số ngẫu nhiên trong [1-frac, 1+frac] (theo seed)."""
    if frac <= 0:
        return value
    return max(1, int(round(value * rng.uniform(1 - frac, 1 + frac))))


def run_scenario(net, scenario_path, seed=0, jitter=0.0, wait_detector=0.0):
    """Chạy các pha theo scenario yaml, ghi ground_truth.json.

    seed/jitter: mỗi seed đổi ngẫu nhiên cường độ (pps, mbps, peak, clients)
    trong ±jitter để các lần lặp không giống hệt nhau (tránh model học thuộc).
    wait_detector: chờ tối đa N giây tới khi detector tạo logs/detector_ready.
    """
    import random
    rng = random.Random(seed)
    sc = load_yaml(scenario_path)
    srv_ip = net.get("srv").IP()
    name = sc.get("name", os.path.basename(scenario_path))
    duration = sc.get("duration", 120)

    os.makedirs("logs/legit", exist_ok=True)
    for fn in os.listdir("logs/legit"):
        os.remove(os.path.join("logs/legit", fn))
    with open("logs/net_ready", "w") as f:
        f.write(str(time.time()))
    if wait_detector > 0:
        t_wait = time.time()
        while (not os.path.exists("logs/detector_ready")
               and time.time() - t_wait < wait_detector):
            time.sleep(0.2)
        print("[scenario] detector %s sau %.1fs" % (
            "sẵn sàng" if os.path.exists("logs/detector_ready") else "CHƯA lên",
            time.time() - t_wait))
        time.sleep(1.5)   # để detector có 1 window nền trước t0
    print("[scenario:%s] bắt đầu, %ds, seed=%d" % (name, duration, seed))

    # probe luôn chạy suốt scenario để đo LSR
    probe = net.get("probe")
    probe.cmd("python3 %s/traffic/probe_client.py --server %s --rate %d "
              "--duration %d --out logs/probe.csv >/tmp/probe.log 2>&1 &"
              % (ROOT, srv_ip, sc.get("probe_rate", 5), duration))

    t0 = time.time()
    attack_ips = []
    ground = {"name": name, "t0": t0, "seed": seed, "jitter": jitter,
              "duration": duration, "phases": [], "attack_ips": []}

    for i, ph in enumerate(sc.get("phases", [])):
        while time.time() - t0 < ph["start"]:
            time.sleep(0.2)
        dur = ph["end"] - ph["start"]
        kind = ph["kind"]
        hosts = ph.get("hosts", [])
        params = {}
        if kind == "normal":
            params["clients"] = _jitter(rng, ph.get("clients", 3), jitter)
        elif kind == "flash":
            params["peak"] = _jitter(rng, ph.get("peak", 30), jitter)
        elif kind == "syn":
            params["pps"] = _jitter(rng, ph.get("pps", 2000), jitter)
        elif kind == "udp":
            params["mbps"] = _jitter(rng, ph.get("mbps", 8), jitter)
        rel_start = time.time() - t0
        print("  [t=%5.1f] pha %s trên %s (%.0fs) %s" % (rel_start, kind, hosts,
                                                         dur, params))
        for hn in hosts:
            h = net.get(hn)
            hseed = rng.randrange(1 << 30)
            out = "logs/legit/%s_p%d.csv" % (hn, i)
            if kind == "normal":
                h.cmd("python3 %s/traffic/legit.py --mode normal --server %s "
                      "--duration %d --clients %d --seed %d --out %s "
                      ">/tmp/%s.log 2>&1 &"
                      % (ROOT, srv_ip, dur, params["clients"], hseed, out, hn))
            elif kind == "flash":
                h.cmd("python3 %s/traffic/legit.py --mode flash --server %s "
                      "--duration %d --peak %d --seed %d --out %s "
                      ">/tmp/%s.log 2>&1 &"
                      % (ROOT, srv_ip, dur, params["peak"], hseed, out, hn))
            elif kind == "syn":
                attack_ips.append(h.IP())
                h.cmd("python3 %s/traffic/attack_lab.py --type syn --server %s "
                      "--pps %d --duration %d >/tmp/%s.log 2>&1 &"
                      % (ROOT, srv_ip, params["pps"], dur, hn))
            elif kind == "udp":
                attack_ips.append(h.IP())
                h.cmd("python3 %s/traffic/attack_lab.py --type udp --server %s "
                      "--mbps %d --duration %d --port 5201 >/tmp/%s.log 2>&1 &"
                      % (ROOT, srv_ip, params["mbps"], dur, hn))
        ground["phases"].append({"kind": kind, "start": ph["start"],
                                 "end": ph["end"], "hosts": hosts,
                                 "params": params})

    while time.time() - t0 < duration:
        time.sleep(0.5)
    time.sleep(3.0)   # chờ legit.py ghi log xong
    ground["attack_ips"] = sorted(set(attack_ips))
    save_json("logs/ground_truth.json", ground)
    print("[scenario:%s] xong -> logs/ground_truth.json" % name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p4info", required=True)
    ap.add_argument("--bmv2", required=True)
    ap.add_argument("--runtime", required=True)
    ap.add_argument("--scenario", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--jitter", type=float, default=0.0,
                    help="biến thiên cường độ theo seed, vd 0.3 = ±30%%")
    ap.add_argument("--wait-detector", type=float, default=0.0,
                    help="chờ detector sẵn sàng (giây) trước khi bơm traffic")
    args = ap.parse_args()
    os.makedirs("logs", exist_ok=True)
    for fn in ("logs/ground_truth.json", "logs/probe.csv", "logs/net_ready"):
        if os.path.exists(fn):
            os.remove(fn)       # tránh copy nhầm file của lần chạy trước

    net = build_net(args.p4info, args.bmv2, args.runtime)
    program_switch(args.p4info, args.bmv2, args.runtime)
    start_server(net)

    if args.scenario:
        try:
            run_scenario(net, args.scenario, seed=args.seed, jitter=args.jitter,
                         wait_detector=args.wait_detector)
        finally:
            for h in net.hosts:       # dừng mọi traffic còn sót
                h.cmd("pkill -f 'traffic/(legit|attack_lab|probe_client)' ; "
                      "pkill hping3")
    else:
        from mininet.cli import CLI
        print("\n== Mininet CLI ==  (chạy detector ở terminal khác)\n"
              "  srv đã có HTTP:80. Thử:  probe ping srv\n")
        CLI(net)

    net.stop()


if __name__ == "__main__":
    main()
