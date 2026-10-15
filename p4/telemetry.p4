/* -*- P4_16 -*- */
/*
 * telemetry.p4 — Data plane cho đề tài NCKH SDN/P4 DDoS + Flash Crowd
 *
 * Nhiệm vụ (chạy trên BMv2 / v1model):
 *   1. Forward IPv4 bằng bảng ipv4_lpm (control plane nạp entry).
 *   2. Parse TCP/UDP để đếm SYN, ACK, UDP phục vụ feature.
 *   3. Thu counter: tổng packet/byte tới server, SYN, ACK, UDP, và packet
 *      theo từng cổng vào (per-ingress-port) để biết traffic từ nhóm host nào.
 *   4. Ước lượng số nguồn bằng register bitmap (controller đọc + xóa mỗi window).
 *   5. Mitigation: bảng src_filter cho phép controller drop/đánh dấu theo src IP;
 *      meter 2 màu giới hạn tốc độ gói SYN/UDP tới server.
 *
 * LƯU Ý: chương trình chạy trong Mininet/BMv2 cô lập, phục vụ phòng thủ.
 * Không claim hiệu năng line-rate từ BMv2.
 */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x0800;
const bit<8>  PROTO_TCP = 6;
const bit<8>  PROTO_UDP = 17;

/* Số lượng đối tượng — chỉnh theo topology */
#define MAX_PORTS      16        // số cổng của switch (per-port counter)
#define SRCBITMAP_SIZE 4096      // register bitmap ước lượng số nguồn

/* Chỉ số counter toàn cục (index cố định) */
const bit<32> C_TOTAL = 0;       // tổng packet/byte tới server
const bit<32> C_SYN   = 1;       // gói TCP SYN (SYN=1, ACK=0)
const bit<32> C_ACK   = 2;       // gói TCP ACK (ACK=1)
const bit<32> C_UDP   = 3;       // gói UDP

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/
typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

header tcp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<32> seqNo;
    bit<32> ackNo;
    bit<4>  dataOffset;
    bit<3>  res;
    bit<3>  ecn;
    bit<6>  ctrl;       // URG,ACK,PSH,RST,SYN,FIN (6 cờ)
    bit<16> window;
    bit<16> checksum;
    bit<16> urgentPtr;
}

header udp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<16> length_;
    bit<16> checksum;
}

struct metadata {
    bit<1>  is_syn;
    bit<1>  is_ack;
    bit<1>  is_udp;
    bit<32> src_hash;
    bit<1>  meter_rate_limit;   // 1 = traffic nghi vấn, áp meter
}

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
    tcp_t      tcp;
    udp_t      udp;
}

/*************************************************************************
*********************** P A R S E R  ************************************
*************************************************************************/
parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        meta.is_syn = 0;
        meta.is_ack = 0;
        meta.is_udp = 0;
        meta.meter_rate_limit = 0;
        transition parse_ethernet;
    }
    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }
    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            PROTO_TCP: parse_tcp;
            PROTO_UDP: parse_udp;
            default: accept;
        }
    }
    state parse_tcp {
        packet.extract(hdr.tcp);
        transition accept;
    }
    state parse_udp {
        packet.extract(hdr.udp);
        transition accept;
    }
}

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/
control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    /* --- Counters đo lường --- */
    counter(8, CounterType.packets_and_bytes) global_ctr;   // index C_*
    counter(MAX_PORTS, CounterType.packets_and_bytes) port_ctr;

    /* --- Register bitmap ước lượng số nguồn --- */
    register<bit<1>>(SRCBITMAP_SIZE) src_bitmap;

    /* --- Meter rate-limit (2 màu GREEN/RED) --- */
    meter(1, MeterType.bytes) syn_udp_meter;

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action ipv4_forward(macAddr_t dstAddr, egressSpec_t port) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table ipv4_lpm {
        key = { hdr.ipv4.dstAddr: lpm; }
        actions = { ipv4_forward; drop; NoAction; }
        size = 1024;
        default_action = drop();
    }

    /* --- Mitigation: lọc theo src IP (controller nạp entry) --- */
    action mark_limit() { meta.meter_rate_limit = 1; }

    table src_filter {
        key = { hdr.ipv4.srcAddr: lpm; }
        // allow: không làm gì; drop: chặn hẳn; mark_limit: đẩy qua meter
        actions = { drop; mark_limit; NoAction; }
        size = 1024;
        default_action = NoAction();
    }

    apply {
        if (!hdr.ipv4.isValid()) { return; }

        /* Phân loại gói cho feature */
        if (hdr.tcp.isValid()) {
            // ctrl bit: SYN = bit1, ACK = bit4 (đếm từ 0 ở LSB của 6 cờ)
            if ((hdr.tcp.ctrl & 0b000010) != 0 && (hdr.tcp.ctrl & 0b010000) == 0) {
                meta.is_syn = 1;
            }
            if ((hdr.tcp.ctrl & 0b010000) != 0) {
                meta.is_ack = 1;
            }
        } else if (hdr.udp.isValid()) {
            meta.is_udp = 1;
        }

        /* Ước lượng nguồn: hash src IP -> bật 1 bit trong bitmap */
        hash(meta.src_hash, HashAlgorithm.crc32, (bit<32>)0,
             { hdr.ipv4.srcAddr }, (bit<32>)SRCBITMAP_SIZE);
        src_bitmap.write(meta.src_hash, 1);

        /* Đếm toàn cục */
        global_ctr.count(C_TOTAL);
        if (meta.is_syn == 1) { global_ctr.count(C_SYN); }
        if (meta.is_ack == 1) { global_ctr.count(C_ACK); }
        if (meta.is_udp == 1) { global_ctr.count(C_UDP); }

        /* Đếm theo cổng vào */
        port_ctr.count((bit<32>)standard_metadata.ingress_port);

        /* Mitigation theo src IP */
        src_filter.apply();
        if (meta.meter_rate_limit == 1) {
            bit<32> color;
            syn_udp_meter.execute_meter(0, color);
            // color==1 (RED) -> vượt rate -> drop gói nghi vấn
            if (color == 1) {
                drop();
                return;
            }
        }

        /* Forwarding */
        ipv4_lpm.apply();
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/
control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
}

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version, hdr.ipv4.ihl, hdr.ipv4.diffserv,
              hdr.ipv4.totalLen, hdr.ipv4.identification, hdr.ipv4.flags,
              hdr.ipv4.fragOffset, hdr.ipv4.ttl, hdr.ipv4.protocol,
              hdr.ipv4.srcAddr, hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum, HashAlgorithm.csum16);
    }
}

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.tcp);
        packet.emit(hdr.udp);
    }
}

V1Switch(
    MyParser(), MyVerifyChecksum(), MyIngress(),
    MyEgress(), MyComputeChecksum(), MyDeparser()
) main;
