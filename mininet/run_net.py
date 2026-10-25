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
    with open(runtime_json, 'r') as sw_conf_file:
        p4runtime_lib.simple_controller.program_switch(
            addr="127.0.0.1:50051", device_id=0,
            sw_conf_file=sw_conf_file, workdir=workdir,
            proto_dump_fpath="logs/p4runtime_bootstrap.txt",
            runtime_json=runtime_json)
    print("[run_net] đã nạp pipeline + forwarding vào s1.")


def start_server(net):
    srv = net.get("srv")
    # web server tĩnh để probe/legit gửi request
    srv.cmd("cd /tmp && python3 -m http.server 80 >/tmp/srv.log 2>&1 &")
    # iperf3 server cho UDP flood test
    srv.cmd("iperf3 -s -p 5201 >/tmp/iperf3s.log 2>&1 &")
    time.sleep(1)
    print("[run_net] server HTTP:80 + iperf3:5201 đã chạy.")


def run_scenario(net, scenario_path):
    """Chạy các pha theo scenario yaml, ghi ground_truth.json."""
    sc = load_yaml(scenario_path)
    srv_ip = net.get("srv").IP()
    name = sc.get("name", os.path.basename(scenario_path))
    duration = sc.get("duration", 120)
    print("[scenario:%s] bắt đầu, %ds" % (name, duration))

    os.makedirs("logs", exist_ok=True)
    # probe luôn chạy suốt scenario để đo LSR
    probe = net.get("probe")
    probe.cmd("python3 %s/traffic/probe_client.py --server %s --rate %d "
              "--duration %d --out logs/probe.csv >/tmp/probe.log 2>&1 &"
              % (ROOT, srv_ip, sc.get("probe_rate", 5), duration))

    t0 = time.time()
    attack_ips = []
    ground = {"name": name, "t0": t0, "phases": [], "attack_ips": []}

    for ph in sc.get("phases", []):
        # chờ tới thời điểm bắt đầu pha
        while time.time() - t0 < ph["start"]:
            time.sleep(0.2)
        dur = ph["end"] - ph["start"]
        kind = ph["kind"]
        hosts = ph.get("hosts", [])
        rel_start = time.time() - t0
        print("  [t=%5.1f] pha %s trên %s (%.0fs)" % (rel_start, kind, hosts, dur))
        for hn in hosts:
            h = net.get(hn)
            if kind == "normal":
                h.cmd("python3 %s/traffic/legit.py --mode normal --server %s "
                      "--duration %d --clients %d >/tmp/%s.log 2>&1 &"
                      % (ROOT, srv_ip, dur, ph.get("clients", 3), hn))
            elif kind == "flash":
                h.cmd("python3 %s/traffic/legit.py --mode flash --server %s "
                      "--duration %d --peak %d >/tmp/%s.log 2>&1 &"
                      % (ROOT, srv_ip, dur, ph.get("peak", 30), hn))
            elif kind == "syn":
                attack_ips.append(h.IP())
                h.cmd("python3 %s/traffic/attack_lab.py --type syn --server %s "
                      "--pps %d --duration %d >/tmp/%s.log 2>&1 &"
                      % (ROOT, srv_ip, ph.get("pps", 2000), dur, hn))
            elif kind == "udp":
                attack_ips.append(h.IP())
                h.cmd("python3 %s/traffic/attack_lab.py --type udp --server %s "
                      "--mbps %d --duration %d --port 5201 >/tmp/%s.log 2>&1 &"
                      % (ROOT, srv_ip, ph.get("mbps", 8), dur, hn))
        ground["phases"].append({"kind": kind, "start": ph["start"],
                                 "end": ph["end"], "hosts": hosts})

    while time.time() - t0 < duration:
        time.sleep(0.5)
    ground["attack_ips"] = sorted(set(attack_ips))
    save_json("logs/ground_truth.json", ground)
    print("[scenario:%s] xong -> logs/ground_truth.json" % name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p4info", required=True)
    ap.add_argument("--bmv2", required=True)
    ap.add_argument("--runtime", required=True)
    ap.add_argument("--scenario", default=None)
    args = ap.parse_args()
    os.makedirs("logs", exist_ok=True)

    net = build_net(args.p4info, args.bmv2, args.runtime)
    program_switch(args.p4info, args.bmv2, args.runtime)
    start_server(net)

    if args.scenario:
        run_scenario(net, args.scenario)
    else:
        from mininet.cli import CLI
        print("\n== Mininet CLI ==  (chạy detector ở terminal khác)\n"
              "  srv đã có HTTP:80. Thử:  probe ping srv\n")
        CLI(net)

    net.stop()


if __name__ == "__main__":
    main()
