# Makefile — biên dịch P4 và chạy testbed.
# Yêu cầu: p4c, BMv2 (simple_switch_grpc), Mininet, và repo p4lang/tutorials
# (đặt đường dẫn utils vào P4_UTILS). Dùng trên Ubuntu/P4 tutorial VM.

P4_UTILS ?= $(HOME)/tutorials/utils
BUILD    := build
P4C      := p4c-bm2-ss
P4SRC    := p4/telemetry.p4

export P4_UTILS

.PHONY: all build topo run clean test offline-demo dataset week6 collect week7 matrix analyze figures

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
	sudo -E python3 mininet/run_net.py \
	  --p4info $(BUILD)/telemetry.p4.p4info.txtpb \
	  --bmv2   $(BUILD)/telemetry.json \
	  --runtime mininet/s1-runtime.json \
	  $(if $(SCENARIO),--scenario $(SCENARIO),)

# Kiểm tra logic offline (không cần P4/Mininet)
test:
	python3 scripts/test_offline.py

SUDO_PY := sudo env "PATH=$(PATH)" P4_UTILS=$(P4_UTILS) python3

# TUẦN 5–6 — thu dữ liệu có nhãn: S1..S6 × B0 (chỉ ghi log) × seed 0..3
collect: build topo
	$(SUDO_PY) experiments/run_matrix.py --baselines B0 --seeds 0 1 2 3 \
	  --scenarios S1 S2 S3 S4 S5 S6 --out results/dataset_raw --resume

# TUẦN 6 — gom log nhiều lần chạy thành dataset có nhãn.
#   make dataset                      (mặc định: mọi run trong results/dataset_raw)
#   make dataset RUNS="results/raw/S1_B0_seed10 ..."
RUNS ?= results/dataset_raw/*
dataset:
	python3 ml/build_dataset.py --runs $(RUNS) --out data/uniflash_v01.csv

# TUẦN 6 — đánh giá baseline threshold/EWMA -> Flash-FPR (không cần testbed)
week6:
	python3 baseline/eval_baseline.py --data data/uniflash_v01.csv --out experiments/week6

# TUẦN 7 — train/đánh giá LR + RF (GroupKFold theo run), lưu models/*.pkl
week7:
	python3 ml/train_eval.py --data data/uniflash_v01.csv --out experiments/week7

# TUẦN 10 — ma trận chính S1..S6 × B0..B3 × seed đánh giá 10..12 (khác seed train)
SEEDS ?= 10 11 12
SCNS  ?= S1 S2 S3 S4 S5 S6
matrix: build topo
	$(SUDO_PY) experiments/run_matrix.py --scenarios $(SCNS) \
	  --baselines B0 B1 B2 B3 --seeds $(SEEDS) --out results/raw --resume

# TUẦN 10 — tổng hợp mean ± CI95 + kiểm định (B3 vs B0/B1/B2, Holm)
analyze:
	python3 analysis/aggregate.py --raw results/raw --out results/summary.csv \
	  --compare-all --stats-out results/stats.csv
	python3 analysis/report_tables.py --summary results/summary.csv \
	  --stats results/stats.csv --out results/RESULTS.md

# TUẦN 11 — hình cho báo cáo
figures:
	python3 analysis/make_figures.py --summary results/summary.csv --raw results/raw \
	  --week7 experiments/week7 --outdir figures
	python3 analysis/weekly_figures.py --outdir figures

# Demo nhanh pipeline ML trên dữ liệu giả lập (không cần testbed)
offline-demo:
	python3 ml/make_synthetic.py --out data/uniflash_synth.csv --runs 12
	python3 ml/train_eval.py --data data/uniflash_synth.csv --out experiments/demo

clean:
	sudo mn -c 2>/dev/null || true
	rm -rf $(BUILD) logs *.pcap
	@echo "đã dọn."
