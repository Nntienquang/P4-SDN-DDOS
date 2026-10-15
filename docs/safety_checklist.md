# Safety checklist — xác nhận trước mỗi buổi chạy thí nghiệm

Cả 3 thành viên ký xác nhận (ghi tên + ngày) trước khi sinh bất kỳ traffic
tấn công nào. Đây là yêu cầu đạo đức nghiên cứu của đề tài.

- [ ] Mọi traffic (kể cả flood) chỉ chạy trong Mininet/VM cô lập.
- [ ] VM dùng mạng host-only hoặc NAT; KHÔNG bridge ra mạng trường.
- [ ] Không chạy generator tấn công trên root namespace của máy thật.
- [ ] Mọi script traffic gọi traffic/safety.py; đích là IP lab private.
- [ ] Không dùng botnet, dịch vụ stresser, hay IP/đích thật.
- [ ] Rate tấn công có trần cấu hình (không có chế độ "flood tối đa").
- [ ] Sau buổi chạy: `sudo mn -c` dọn sạch; kiểm tra không còn tiến trình treo.

Người xác nhận:
- A: ____________  ngày ____
- B: ____________  ngày ____
- C: ____________  ngày ____
