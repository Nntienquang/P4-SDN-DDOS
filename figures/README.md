# Hình kết quả theo tuần

Sinh bằng `python3 analysis/weekly_figures.py` (hoặc `make figures`). Mỗi hình kèm chú thích gợi ý để dán vào báo cáo.

## Tuần 4

![counter_realtime_S3.png](tuan04/counter_realtime_S3.png)

*Feature tính từ counter P4 theo thời gian thực (poll ~1s). Khi SYN flood bắt đầu (nền xanh lá), packet_rate và syn_rate tăng vọt, tỉ lệ ACK/SYN tụt về ~0 vì attacker không hoàn tất handshake.*

![poll_interval.png](tuan04/poll_interval.png)

*Phân bố chu kỳ poll thực tế: ~1.13s trung vị (1s ngủ + thời gian đọc counter/register). Đây là độ phân giải thời gian của hệ thống.*

## Tuần 5

![four_traffic_types.png](tuan05/four_traffic_types.png)

*packet_rate của 4 kịch bản. Điểm mấu chốt: Flash Crowd (S2) có volume ngang hoặc cao hơn SYN flood (S3) — nhìn volume không phân biệt được.*

![probe_no_defense.png](tuan05/probe_no_defense.png)

*Probe đo dịch vụ khi không phòng thủ: tấn công (S3, S4) làm tỉ lệ thành công tụt gần 0 trong pha 30–90s; Normal/Flash vẫn phục vụ được.*

## Tuần 6

![feature_distribution.png](tuan06/feature_distribution.png)

*Phân bố feature theo nhãn. packet_rate của Flash Crowd chồng lên DDoS (ngưỡng tĩnh nằm dưới cả hai) nên threshold báo nhầm; ACK/SYN thì tách rõ: người thật hoàn tất handshake, SYN flood thì không.*

![dataset_composition.png](tuan06/dataset_composition.png)

*Số window có nhãn theo kịch bản (đã loại window sát ranh giới pha).*

![baseline_flash_fpr.png](tuan06/baseline_flash_fpr.png)

*Kết quả tuần 6 (chia theo run): threshold và EWMA có Recall ~1 nhưng Flash-FPR rất cao — bằng chứng cho câu hỏi nghiên cứu RQ2.*

## Tuần 7

![model_compare.png](tuan07/model_compare.png)

*So sánh 4 phương pháp, dự đoán out-of-fold (GroupKFold theo run): ML giữ Recall ~1 và giảm Flash-FPR từ 0.76–0.95 xuống ~0.01.*

![feature_importance.png](tuan07/feature_importance.png)

*Độ quan trọng feature của RandomForest: syn_ack_ratio đứng đầu — model dựa vào HÀNH VI (hoàn tất handshake), không chỉ volume.*

![confusion_rf.png](tuan07/confusion_rf.png)

*Ma trận nhầm lẫn theo nhãn chi tiết: gần như toàn bộ Flash Crowd được giữ là lành tính.*

## Tuần 8

![online_detection_S5.png](tuan08/online_detection_S5.png)

*Model chạy thời gian thực: báo DDoS đúng trong pha tấn công và im lặng trong Flash Crowd 30–50s và 110–120s; threshold báo động suốt cả pha Flash.*

![detection_latency.png](tuan08/detection_latency.png)

*Độ trễ phát hiện online: ~2–3 chu kỳ poll. Model không chậm hơn threshold đáng kể.*

## Tuần 9

![mitigation_timeline_S5.png](tuan09/mitigation_timeline_S5.png)

*B3 leo L1→L2 trong ~3s sau khi tấn công bắt đầu và chặn đúng cổng a1, a2, a3. B0 sập về 0 suốt pha tấn công; B3 giữ được một phần dịch vụ nhưng không về 100% vì Flash Crowd đồng thời vẫn làm server quá tải và các kết nối half-open còn tồn đọng.*

![blocked_hosts.png](tuan09/blocked_hosts.png)

*Tổng số window mỗi host bị chặn trên mọi run B3. a1–a3 là host tấn công; không host hợp lệ (h1–h8) nào bị chặn.*

## Tuần 10

![lsr_attack.png](tuan10/lsr_attack.png)

*Thước đo chính: tỉ lệ request probe thành công TRONG pha tấn công.*

![user_sr_attack.png](tuan10/user_sr_attack.png)

*Thước đo độc lập với feedback: client h1–h8 không được đưa vào vòng phản hồi của B3.*

![fpr.png](tuan10/fpr.png)

*FPR theo window: threshold báo nhầm khi Flash Crowd.*

![flash_sr.png](tuan10/flash_sr.png)

*Tỉ lệ thành công của chính người dùng Flash Crowd.*

![mitigation_latency.png](tuan10/mitigation_latency.png)

*Độ trễ từ khi tấn công bắt đầu tới khi rule mitigation đầu tiên được ghi.*

## Tuần 11

![timeline_S5_all.png](tuan11/timeline_S5_all.png)

*Cùng kịch bản S5 (seed 10) dưới 4 baseline: chỉ B3 giữ được dịch vụ trong pha tấn công.*

![timeline_S3_all.png](tuan11/timeline_S3_all.png)

*Kịch bản S3 (SYN flood) dưới 4 baseline.*

![tradeoff_S5.png](tuan11/tradeoff_S5.png)

*Mỗi điểm = trung bình một baseline ở S5. B3 đạt cả hai mục tiêu: không báo nhầm Flash và giữ dịch vụ khi bị tấn công.*

