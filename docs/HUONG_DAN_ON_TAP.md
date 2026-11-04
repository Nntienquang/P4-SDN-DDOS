# Hướng dẫn ôn tập & chuẩn bị bảo vệ

> Mục tiêu: sau 5 buổi, mỗi thành viên **tự giải thích được** hệ thống, **tự chạy
> được** demo, và **trả lời được** các câu hỏi hội đồng bằng số liệu của chính
> nhóm. Mọi con số dưới đây lấy từ `docs/BAO_CAO_KET_QUA.md` và
> `results/RESULTS.md`, đo trên testbed ngày 03/11/2026.

---

## Phần 1 — Lộ trình 5 buổi (~2 giờ/buổi)

### Buổi 1 — Bức tranh tổng thể

**Đọc:** `docs/BAO_CAO_KET_QUA.md` mục 1–2; slide 1–6 kèm ghi chú lời nói.

**Tự làm:** vẽ lại trên giấy, không nhìn tài liệu, vòng
*data plane → feature → phát hiện → chặn → feedback*. Mỗi khối ghi một câu "nó
làm gì" và "file nào".

**Tự kiểm tra:** giải thích cho người ngoài ngành trong 1 phút vì sao Flash Crowd
làm khó phòng thủ DDoS.

### Buổi 2 — Data plane P4 và controller

**Đọc code:**
- `p4/telemetry.p4`: phần `apply { … }` trong `MyIngress`; tìm `port_ctr`,
  `port_filter`, `proto_filter`, `rl_meter`.
- `controller/read_stats.py`: đọc counter bằng một lệnh wildcard.
- `controller/features.py`: `compute_features()`, `port_rates()`, `suspect_ports()`.

**Chạy:** `make test` (67 PASS). Mở `scripts/test_offline.py`, đọc nhóm test
`[feature theo cổng - tuần 9]`.

**Tự kiểm tra:** vì sao counter đếm TRƯỚC bảng lọc? Vì sao phải lấy hiệu hai lần
đọc mới ra tốc độ?

### Buổi 3 — Dữ liệu và máy học

**Đọc:** `ml/build_dataset.py` (hàm `label_at`, `is_transition`),
`ml/train_eval.py` (đoạn GroupKFold), `experiments/week7/model_report.md`.

**Chạy** (vài giây, dùng dữ liệu đã thu):
```bash
make dataset week6 week7
```
So số in ra với `experiments/week6/baseline_report.md` và
`experiments/week7/model_report.md`. Phải giống nhau, vì dữ liệu không đổi.

**Tự kiểm tra:** chia ngẫu nhiên theo dòng thì sai ở đâu? Feature nào quan trọng
nhất, và vì sao điều đó hợp lý về mặt mạng?

### Buổi 4 — Mitigation và demo trực tiếp

**Đọc:** `mitigation/policy.py` (hàm `update`: hysteresis, feedback, đổi
mark → drop), `mitigation/mitigator.py`.

**Chạy demo** (máy ảo, 2 terminal):
```bash
# Terminal A
make run SCENARIO=configs/scenarios/S5.yaml
# Terminal B — ngay khi A in "[run_net] server HTTP:80 ..."
sudo -E python3 controller/detector.py --p4info build/telemetry.p4.p4info.txtpb \
  --bmv2 build/telemetry.json --model models/rf.pkl \
  --mitigation targeted --feedback --out logs/demo.csv
```
Quan sát lần lượt: `ok` trong pha Flash (giây 30–50) → `DDoS` →
`L1-ratelimit` → `L2-drop chặn:a1,a2,a3` → hạ dần về `L0-monitor` sau giây 110.

**Tự kiểm tra:** mỗi người tự chạy demo một lần, không nhìn hướng dẫn.

### Buổi 5 — Kết quả, thống kê, hạn chế; tập trả lời

**Đọc:** `results/RESULTS.md` (bảng A–D), `docs/BAO_CAO_KET_QUA.md` mục 7–8,
`docs/NHAT_KY_SUA_LOI_tuan4_11.md`.

**Tập:** một người đóng vai hội đồng, hỏi ngẫu nhiên các câu ở Phần 2; người trả
lời phải nêu được **con số** và **file/hình** làm bằng chứng.

**Phân vai gợi ý (nhóm 3 người):**
- người 1: data plane P4 + controller (câu 1–8)
- người 2: dữ liệu + máy học (câu 9–15)
- người 3: mitigation + thí nghiệm + thống kê (câu 16–26)
- cả nhóm: câu 27–30

---

## Phần 2 — Câu hỏi hội đồng hay hỏi

Mỗi câu: **gợi ý trả lời** (nói bằng lời của mình, đừng đọc thuộc) và
**bằng chứng** để chỉ vào.

### A. Bài toán và kiến trúc

**1. Flash Crowd khác DDoS ở điểm nào, nếu volume giống nhau?**
Khác ở **hành vi**: người thật hoàn tất bắt tay TCP và đọc phản hồi, nên mỗi SYN
kéo theo nhiều gói ACK. SYN flood gửi SYN rồi bỏ đi.
*Bằng chứng:* ACK/(SYN+1) trung vị ~9–10 với Flash, ~0,6 với DDoS (Hình 6.1).

**2. Vì sao dùng P4 thay vì OpenFlow thông thường?**
P4 cho tự định nghĩa counter theo nhu cầu: số gói SYN và ACK **theo từng cổng
vào**, bitmap ước lượng số nguồn. OpenFlow chỉ có counter theo flow rule đã cài
sẵn. P4 cũng cho đặt logic chặn (bảng, meter) ngay trong data plane.
*Bằng chứng:* `p4/telemetry.p4`.

**3. Controller đọc dữ liệu từ switch thế nào, bao lâu một lần?**
Qua P4Runtime (gRPC), đọc wildcard 2 counter mỗi chu kỳ; register bitmap đọc qua
`simple_switch_CLI` (Thrift). Chu kỳ thực tế trung vị 1,13 s (đặt 1 s, cộng thời
gian đọc).
*Bằng chứng:* `controller/read_stats.py`, Hình 4.2.

**4. Vì sao chặn theo cổng vào, không theo IP nguồn?**
IP nguồn giả mạo được rất dễ; cổng vào của switch biên thì không. Ở switch biên,
mỗi cổng ≈ một máy, nên chặn cổng là chặn đúng máy tấn công.
*Đã kiểm chứng:* thí nghiệm bổ sung S3S cho attacker dùng `hping3 --rand-source`.
B3 vẫn chặn đúng a1–a3 và giữ LSR **89,6%**, trong khi rate-limit thô (B1, B2)
chỉ còn ~2% và không phòng thủ còn 1,7%.
*Lưu ý khi trả lời:* mới có 3 run và chỉ với SYN flood; chưa thử giả mạo MAC.
*Bằng chứng:* `docs/BAO_CAO_KET_QUA.md` mục 7.4, Hình 9.2.

**5. Vì sao counter đếm trước khi lọc?**
Để controller vẫn thấy kẻ tấn công **đang** gửi trong lúc bị chặn. Nếu đếm sau,
tấn công "biến mất" khỏi số liệu, controller tưởng đã hết, gỡ rule, rồi tấn công
quay lại: hệ thống bật tắt liên tục.

**6. Topology có gì, nút cổ chai ở đâu?**
1 switch BMv2, 1 server (link 10 Mbps — nút cổ chai), probe, 8 host hợp lệ
h1–h8, 3 host tấn công a1–a3. Server: `traffic/web_server.py`, backlog 128.

**7. Tấn công gây hại bằng cơ chế nào?**
SYN flood lấp hàng đợi kết nối half-open của server; UDP flood lấp băng thông
link server 10 Mbps. Ngoài ra BMv2 chỉ xử lý được ~1,5–2 nghìn gói/s.
*Bằng chứng:* `docs/NHAT_KY_SUA_LOI_tuan4_11.md` mục D.

**8. Hệ thống tốn bao nhiêu tài nguyên?**
CPU detector ~2,2%; model đoán ~16 ms mỗi window (so với chu kỳ 1 s); tối đa
3 rule trong bảng.
*Bằng chứng:* Bảng C trong `results/RESULTS.md`.

### B. Dữ liệu và máy học

**9. Nhãn của dữ liệu lấy từ đâu? Có bị "tự chấm điểm" không?**
Nhãn lấy từ `ground_truth.json`, do bộ sinh traffic ghi pha nào chạy lúc nào,
**không** suy từ detector. Thời điểm của mỗi window = `wall − t0`, theo đồng hồ
tuyệt đối.
*Bằng chứng:* `ml/build_dataset.py`.

**10. Window "transition" là gì, sao phải loại?**
Window rơi đúng ranh giới hai pha (nửa normal nửa tấn công) có nhãn không rõ
ràng. Loại khi train và khi tính metric (144/2 754 window).

**11. Làm sao biết model không "học thuộc"?**
Hai lớp bảo vệ:
- GroupKFold theo **lần chạy**: model luôn bị chấm trên lần chạy nó chưa thấy.
- Ma trận online dùng **seed 10–14**, khác hẳn seed 0–3 dùng để train.
*Bằng chứng:* `experiments/week7/cv_folds.csv`; `docs/BAO_CAO_KET_QUA.md` mục 2.

**12. Vì sao chọn RandomForest, khi LR cho kết quả ngang bằng?**
Trên dữ liệu lab, hai model ngang nhau (Flash-FPR 0,010, F1 0,994), vì dữ liệu gần
như tách tuyến tính theo `syn_ack_ratio`. RF được chọn vì chịu được quan hệ phi
tuyến khi dữ liệu thật phức tạp hơn và cho feature importance. Đây cũng là
**một hạn chế**: chưa chứng minh được lợi ích của model phi tuyến.

**13. Feature nào quan trọng nhất? Có hợp lý không?**
`syn_ack_ratio` (0,35), rồi packet_rate (0,20), source_entropy (0,12). Hợp lý:
đó chính là dấu hiệu "có hoàn tất bắt tay không".
*Bằng chứng:* Hình 7.2.

**14. Model có bắt được tấn công kiểu mới không?**
Một phần: với SYN flood giả mạo IP (S3S), số nguồn ước lượng nhảy lên ~580–955,
giá trị model chưa từng thấy lúc train, nhưng model vẫn bắt được 100% (chậm hơn
0,6–0,9 s). Còn tấn công khác loại thì chưa được kiểm chứng. Mới thử SYN và UDP flood. HTTP flood hoàn tất bắt tay sẽ
có `syn_ack_ratio` giống người thật và rất có thể **qua mặt** model. Đây là hướng
phát triển: thêm feature theo flow/tầng ứng dụng.

**15. Threshold báo nhầm bao nhiêu, và vì sao?**
Offline: Flash-FPR 0,761 (threshold), 0,949 (EWMA). Online: 98% ở S2, 92,5% ở S5,
và 35,7% FPR ở S6 (tải nền chỉ tăng tự nhiên). Lý do: ngưỡng chỉ nhìn volume,
mà Flash Crowd có volume ngang hoặc cao hơn DDoS.

### C. Mitigation và kết quả

**16. Vì sao B1 và B2 cho LSR gần như nhau, dù B2 phát hiện tốt hơn hẳn?**
Vì cả hai **chặn thô**: mọi gói SYN/UDP, của cả người thật lẫn kẻ tấn công, đi
chung hạn mức 300 gói/s, nên người thật bị bóp như nhau. Đây là phát hiện chính
của đề tài: *phát hiện đúng là điều kiện cần, chặn đúng nguồn mới là điều kiện đủ*.
*Bằng chứng:* Bảng A, slide 14.

**17. Vì sao B3 ở S5 chỉ đạt 58%, trong khi S3/S4 gần 100%?**
Ở S5, Flash Crowd đồng thời **tự nó** đã làm server quá tải: ngay cả B0 (không
có chặn nhầm nào) cũng chỉ ~40% request Flash thành công. B3 loại được kẻ tấn
công nhưng không tạo thêm năng lực cho server.
*Bằng chứng:* Bảng B (S5-B0 user Flash OK 39,9%), Hình 9.1.

**18. Dịch vụ có hồi phục ngay khi chặn không?**
Không tức thời. Khi drop cổng attacker, gói RST của attacker cũng bị chặn, nên
các kết nối half-open trên server phải chờ hết timeout. Thử riêng đo được ~6–10 s
hồi phục ở mức thấp; trong ma trận, S3/S4 vẫn đạt ~99% vì phát hiện nhanh.

**19. Vì sao có L1 rate-limit rồi mới L2 drop?**
Để thận trọng: nếu nghi nhầm, L1 chỉ giới hạn chứ không cắt hẳn. Nhóm cũng ghi
nhận trung thực: 50 gói/s mỗi cổng **không đủ** cứu server trước SYN flood, nên
L2 mới thật sự hiệu quả. Feedback giúp leo L2 nhanh khi LSR tụt.

**20. Feedback hoạt động thế nào? Có "gian lận" không, khi probe vừa là tín hiệu vừa là thước đo?**
Detector đọc `logs/probe.csv`, tính LSR 5 giây gần nhất (request OK và ≤ 1 s).
LSR < 0,9 khi đang tấn công thì leo mức ngay. Đúng là có thiên lệch, nên nhóm đo
thêm tỉ lệ thành công của **client h1–h8**, không nằm trong vòng phản hồi, và
kết luận không đổi: 94,7% / 100% / 51,1% (B3) so với 17–36% (B1/B2).
*Bằng chứng:* cột "Client hợp lệ OK" trong Bảng A.

**21. B3 có chặn nhầm người thật không?**
Không. Trên toàn bộ run B3, chỉ a1–a3 bị chặn.
*Bằng chứng:* Hình 9.2 (`figures/tuan09/blocked_hosts.png`).

**22. Ở S2, B1 báo nhầm 98% mà người dùng Flash vẫn 100% thành công — mâu thuẫn không?**
Không mâu thuẫn. Flash Crowd chỉ tạo ~120 SYN/s, dưới hạn mức chung 300, nên dù
rate-limit đã bật cũng không gói nào bị drop. Báo nhầm chỉ gây hại khi trùng với
tấn công (S5), lúc người thật phải chia hạn mức với attacker.

### D. Thống kê và độ tin cậy

**23. Mỗi cấu hình chạy mấy lần? Đơn vị thống kê là gì?**
3 lần (S1, S2, S6) và 5 lần (S3, S4, S5). Đơn vị là **một lần chạy**, không phải
window, vì các window trong cùng lần chạy phụ thuộc nhau.

**24. Kết quả có ý nghĩa thống kê không?**
Có. Với LSR và tỉ lệ client OK trong pha tấn công, 18/18 so sánh B3 với B0, B1,
B2 đều **tách hoàn toàn** (mọi run B3 tốt hơn mọi run kia). Welch t-test hiệu
chỉnh Holm: p < 0,001. CI95 của hiệu không chứa 0, ví dụ S5 B3−B2:
+0,39 [0,32; 0,46].

**25. Vì sao Mann-Whitney chỉ đạt p = 0,07?**
Giới hạn toán học: với 5 run mỗi nhóm, p nhỏ nhất Mann-Whitney có thể có là
0,0079, nhân Holm cho 9 phép so sánh thành ~0,07, kể cả khi hai nhóm tách hoàn
toàn. Muốn dưới 0,05 cần ≥ 7 run mỗi nhóm. Vì vậy Welch là kiểm định chính, MW
là kiểm tra bổ trợ.

**26. Kết quả có tái lập được không?**
Có: `make collect dataset week6 week7 matrix analyze figures`. Seed cố định,
cường độ biến thiên theo seed được ghi trong `ground_truth.json` của mỗi run.
*Bằng chứng:* `docs/BAO_CAO_KET_QUA.md` mục 9.

### E. Hạn chế và câu hỏi khó

**27. BMv2 là switch phần mềm. Kết quả có ý nghĩa với mạng thật không?**
Kết quả về **độ chính xác** (báo nhầm) và **tính chọn lọc** (chặn đúng ai) phụ
thuộc logic, nên chuyển được sang phần cứng. Kết quả về **thông lượng và độ trễ**
thì không, vì BMv2 chỉ ~1,5–2 nghìn gói/s. Cần thử trên switch P4 phần cứng.

**28. Nếu switch lõi, một cổng gom hàng nghìn người dùng thì sao?**
Chặn cổng sẽ gây hại tập thể. Đề tài giả định switch biên. Hướng mở rộng: kết
hợp cổng vào với IP nguồn hoặc flow, và triển khai ở nhiều switch biên.

**29. Sao không dùng CDN/WAF có sẵn?**
CDN/WAF là lớp bảo vệ ở tầng ứng dụng hoặc ở nhà cung cấp, tốn chi phí, và không
phải mạng nào cũng đặt được trước nó. Đề tài nghiên cứu phòng thủ **ngay trong
mạng** (data plane có thể lập trình), bổ sung chứ không thay thế các lớp đó.
*Lưu ý:* nhóm nên tự đọc thêm các công trình liên quan để so sánh cụ thể khi
viết phần tổng quan.

**30. Kết quả ban đầu và kết quả cuối khác nhau, chuyện gì đã xảy ra?**
Lần chạy đầu tiên có lỗi testbed (mạng không thông, mitigation không chặn gói
nào, nhãn lệch ~9 giây), nên toàn bộ kết quả đó bị loại. Sau khi sửa, nhóm chạy
lại từ đầu; 2 run bị hỏng do máy ngủ cũng được phát hiện tự động và chạy lại.
*Bằng chứng:* `docs/NHAT_KY_SUA_LOI_tuan4_11.md`. Nói thẳng điều này là điểm
cộng về tính trung thực.

---

## Phần 3 — Checklist trước ngày bảo vệ

- [ ] Điền tên thành viên và GVHD trên slide bìa.
- [ ] Mỗi người tự chạy được demo Buổi 4 trên máy ảo.
- [ ] Tắt chế độ ngủ của máy thật; cắm sạc laptop khi demo.
- [ ] Chuẩn bị video quay sẵn demo, phòng khi máy lỗi lúc bảo vệ.
- [ ] Mỗi người trả lời trôi chảy ít nhất các câu thuộc phần mình phụ trách.
- [ ] Báo cáo theo mẫu trường có phần tổng quan tài liệu và tài liệu tham khảo
      (phần này nhóm tự viết).
- [ ] `git pull` bản mới nhất trước khi demo; chạy `make test` (67 PASS).
