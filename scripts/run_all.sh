#!/usr/bin/env bash
# =============================================================================
# run_all.sh — Chạy TỰ ĐỘNG phần lớn đề tài (Tuần 5 -> 11) trên MÁY ẢO P4.
#
# Một lệnh làm cả chuỗi: build P4 -> thu dữ liệu -> gom dataset -> baseline ->
# train model -> chạy ma trận phòng thủ -> tổng hợp thống kê -> vẽ hình.
#
# CÁCH DÙNG (trên máy ảo, trong ~/P4-SDN-DDOS):
#     bash scripts/run_all.sh lite     # bản nhẹ cho máy yếu (khuyên chạy trước)
#     bash scripts/run_all.sh full     # bản đầy đủ (lâu, để qua giờ nghỉ)
#
# Script hỏi mật khẩu sudo MỘT LẦN (cho phần dựng mạng Mininet). Các bước còn
# lại chạy bằng quyền thường. Nếu một vài run lỗi, script vẫn đi tiếp và báo ở cuối.
# =============================================================================
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
export P4_UTILS="${P4_UTILS:-$HOME/tutorials/utils}"
MODE="${1:-lite}"

# Seed thu dữ liệu train (0..3) KHÁC seed đánh giá (10..) -> không rò rỉ.
if [ "$MODE" = "full" ]; then
    SCN="S1 S2 S3 S4 S5 S6"; TRAIN_SEEDS="0 1 2 3"; EVAL_SEEDS="10 11 12"
else
    SCN="S2 S3 S4 S5"; TRAIN_SEEDS="0 1"; EVAL_SEEDS="10 11"
fi

# dạng lệnh chạy root + giữ venv (tránh lỗi "No module named 'mininet'")
SUDO='sudo env PATH='"$PATH"' P4_UTILS='"$P4_UTILS"

say(){ echo; echo "============================================================"; \
       echo ">>> $*"; echo "============================================================"; }

say "0/7  Môi trường"
echo "ROOT=$ROOT  |  P4_UTILS=$P4_UTILS  |  MODE=$MODE"
echo "scenarios: $SCN  |  train seeds: $TRAIN_SEEDS  |  eval seeds: $EVAL_SEEDS"
python3 --version; p4c --version 2>&1 | head -1
sudo -v || { echo "Không có quyền sudo -> dừng."; exit 1; }

say "1/7  Biên dịch P4 + topology"
make build topo || { echo "LỖI build P4 — xem thông báo trên."; exit 1; }

say "2/7  Thu dữ liệu không phòng thủ (B0) để làm dataset"
$SUDO python3 experiments/run_matrix.py --scenarios $SCN --baselines B0 \
    --seeds $TRAIN_SEEDS --out results/dataset_raw --resume

say "3/7  Gom log -> dataset có nhãn (data/uniflash_v01.csv)"
python3 ml/build_dataset.py --runs results/dataset_raw/* --out data/uniflash_v01.csv

say "4/7  Baseline threshold/EWMA -> Flash-FPR (experiments/week6)"
python3 baseline/eval_baseline.py --data data/uniflash_v01.csv --out experiments/week6 \
    || echo "(baseline lỗi — thường do dataset thiếu nhãn flash; xem lại bước 2)"

say "5/7  Train model (models/rf.pkl, experiments/week7)"
python3 ml/train_eval.py --data data/uniflash_v01.csv --out experiments/week7 \
    || { echo "LỖI train — cần models/rf.pkl cho bước sau."; exit 1; }

say "6/7  Ma trận đánh giá online B0..B3 trên seed MỚI"
$SUDO python3 experiments/run_matrix.py --scenarios $SCN --baselines B0 B1 B2 B3 \
    --seeds $EVAL_SEEDS --out results/raw --resume

say "7/7  Tổng hợp thống kê + vẽ hình"
make analyze figures || echo "(phân tích/vẽ lỗi — xem thông báo trên)"

say "XONG"
echo "Kết quả chính:"
echo "  - data/uniflash_v01.csv        (dataset có nhãn — Tuần 6)"
echo "  - experiments/week6/           (Flash-FPR baseline — Tuần 6)"
echo "  - experiments/week7/           (so sánh model — Tuần 7)"
echo "  - models/rf.pkl                (model đã train)"
echo "  - results/summary.csv, results/RESULTS.md (mean ± CI95 + kiểm định — Tuần 10)"
echo "  - figures/                     (hình cho báo cáo — Tuần 11)"
echo
echo "Gửi lại cho mình nội dung 3 file để cùng đọc kết quả:"
echo "  cat experiments/week6/baseline_report.md"
echo "  cat experiments/week7/model_compare.csv"
echo "  cat results/summary.csv"
