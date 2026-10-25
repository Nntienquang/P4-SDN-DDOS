# Makefile — biên dịch P4 và chạy testbed.
# Yêu cầu: p4c, BMv2 (simple_switch_grpc), Mininet, và repo p4lang/tutorials
# (đặt đường dẫn utils vào P4_UTILS). Dùng trên Ubuntu/P4 tutorial VM.

P4_UTILS ?= $(HOME)/tutorials/utils
BUILD    := build
P4C      := p4c-bm2-ss
P4SRC    := p4/telemetry.p4

export P4_UTILS

.PHONY: all build topo run clean test offline-demo

all: build topo

# 1) Biên dịch P4 -> build/telemetry.json + build/telemetry.p4.p4info.txtpb
build:
	mkdir -p $(BUILD) logs
	$(P4C) --target bmv2 --arch v1model \
	  --p4runtime-files $(BUILD)/telemetry.p4.p4info.txtpb \
	  -o $(BUILD)/telemetry.json $(P4SRC)
	@echo "OK: đã biên dịch P4 -> $(BUILD)/"

# 2) Sinh topology.json + s1-runtime.json từ configs/topology.yaml
topo:
	python3 mininet/build_topo.py

# 3) Dựng Mininet + BMv2, nạp pipeline, vào CLI (hoặc chạy scenario)
#    make run SCENARIO=configs/scenarios/S5.yaml
run: build topo
	sudo PATH=$(PATH) python3 mininet/run_net.py \
	  --p4info $(BUILD)/telemetry.p4.p4info.txtpb \
	  --bmv2   $(BUILD)/telemetry.json \
	  --runtime mininet/s1-runtime.json \
	  $(if $(SCENARIO),--scenario $(SCENARIO),)

# Kiểm tra logic offline (không cần P4/Mininet)
test:
	python3 scripts/test_offline.py

# Demo nhanh pipeline ML trên dữ liệu giả lập (không cần testbed)
offline-demo:
	python3 ml/make_synthetic.py --out data/uniflash_synth.csv --runs 12
	python3 ml/train_eval.py --data data/uniflash_synth.csv --out experiments/demo

clean:
	sudo mn -c 2>/dev/null || true
	rm -rf $(BUILD) logs *.pcap
	@echo "đã dọn."
