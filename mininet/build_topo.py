#!/usr/bin/env python3
"""
build_topo.py — Sinh topology.json + s1-runtime.json từ configs/topology.yaml

Dùng với hạ tầng p4lang/tutorials (utils/run_exercise.py). Sau khi chạy file
này, `make run` sẽ dựng Mininet với 1 P4 switch BMv2, N host hợp lệ, M host
tấn công, 1 probe client và 1 web server — tất cả trong namespace cô lập.

Vì sao sinh tự động: nhóm chỉ sửa configs/topology.yaml (số host, IP, băng
thông) thay vì sửa tay JSON — tránh sai 5-tuple và dễ tái lập.

Chạy:  python3 mininet/build_topo.py
Output: mininet/topology.json, mininet/s1-runtime.json
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from common import load_yaml   # noqa: E402

SWITCH = "s1"


def mac(i):
    return "08:00:00:00:%02x:%02x" % ((i >> 8) & 0xff, i & 0xff)


def build(cfg):
    """Trả về (topology_dict, runtime_dict)."""
    hosts, links, table_entries = {}, [], []
    subnet = cfg.get("subnet", "10.0.0")
    bw = cfg.get("link_bw_mbps", 10)            # băng thông link host-switch
    server_bw = cfg.get("server_bw_mbps", 10)   # link tới server = cổ chai
    delay = cfg.get("link_delay", "1ms")

    port = 1
    sw_mac_base = 0x0100
    host_ips = {}

    def add_host(name, host_id, last_octet, is_server=False):
        nonlocal port
        ip = "%s.%s" % (subnet, last_octet)
        host_ips[name] = ip
        hosts[name] = {
            "ip": "%s/24" % ip,
            "mac": mac(host_id),
            "commands": [],
        }
        link_bw = server_bw if is_server else bw
        links.append({
            "node1": name, "node2": "%s-p%d" % (SWITCH, port),
            "latency": delay, "bandwidth": link_bw,
        })
        # forwarding entry: dst IP -> cổng của host này
        table_entries.append({
            "table": "MyIngress.ipv4_lpm",
            "match": {"hdr.ipv4.dstAddr": [ip, 32]},
            "action_name": "MyIngress.ipv4_forward",
            "action_params": {"dstAddr": mac(host_id), "port": port},
        })
        port += 1

    hid = 0x0001
    # web server
    add_host("srv", hid, cfg.get("server_octet", 100), is_server=True); hid += 1
    # probe client đo LSR
    add_host("probe", hid, cfg.get("probe_octet", 200)); hid += 1
    # host hợp lệ
    for k in range(cfg.get("n_legit", 8)):
        add_host("h%d" % (k + 1), hid, 10 + k); hid += 1
    # host tấn công
    for k in range(cfg.get("n_attack", 3)):
        add_host("a%d" % (k + 1), hid, 50 + k); hid += 1

    gw_mac = mac(sw_mac_base)
    for hname, hinfo in hosts.items():
        hinfo["commands"] = [
            "arp -s %s %s" % (peer_ip, gw_mac)
            for pname, peer_ip in host_ips.items() if pname != hname
        ]

    topology = {
        "hosts": hosts,
        "switches": {SWITCH: {"runtime_json": "mininet/s1-runtime.json"}},
        "links": links,
    }
    runtime = {
        "target": "bmv2",
        "p4info": "build/telemetry.p4.p4info.txtpb",
        "bmv2_json": "build/telemetry.json",
        "table_entries": table_entries,
    }
    return topology, runtime


def main():
    cfg = load_yaml(os.path.join(ROOT, "configs", "topology.yaml"))
    topology, runtime = build(cfg)
    with open(os.path.join(HERE, "topology.json"), "w") as f:
        json.dump(topology, f, indent=2)
    with open(os.path.join(HERE, "s1-runtime.json"), "w") as f:
        json.dump(runtime, f, indent=2)
    n = len([h for h in topology["hosts"] if h.startswith("h")])
    a = len([h for h in topology["hosts"] if h.startswith("a")])
    print("Đã sinh topology: %d host hợp lệ, %d host tấn công, 1 probe, 1 server."
          % (n, a))
    print("  mininet/topology.json")
    print("  mininet/s1-runtime.json")


if __name__ == "__main__":
    main()
