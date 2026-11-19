# Báo cáo nhóm <<XX>>

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall): seed 3007: 0.9 / chờ review bằng mắt / 0.6
- Số ứng viên trên lô sạch (`--no-faults`): 56 cặp duy nhất `(ảnh, loại)` trên 34 ảnh; hàng đợi seed luyện tập: 171 cặp trên 116 ảnh
- Ngưỡng đã chọn và cách chọn (không dùng `_private`): ghép cùng lớp bằng bbox IoU >= 0.20; drift khi ít nhất 20% pixel segment rơi ngoài box; bất đồng lớp khi IoU >= 0.50; merge khi mỗi trong ít nhất hai box chứa 30 pixel và 15% segment. Lô sạch sinh 56 ứng viên, chủ yếu instance_merge (28), cho thấy đây là nguồn nhiễu lớn. Bất đồng lớp được đưa ra dưới cả hai giả thuyết `class_swap` và `category_swap`; reviewer phải chọn loại sau khi xem ảnh.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Báo hết ứng viên làm precision giảm: trên lô sạch, cách ghép hiện sinh ra 56 ứng viên duy nhất dù đó là lô không cài lỗi. Nếu báo tất cả trên seed luyện tập, 171 ứng viên có thể chứa cả lệch tự nhiên, tạo FP; recall có thể tăng nhưng F1 bị kéo xuống.

## 3. Quyết định và lineage
QC v1: 9/250 ảnh có lỗi luật đã phát hiện, tỷ lệ 3.6%; theo ngưỡng trên 2% nên kết luận **HOLD**. R-021 được gắn release cũ nên phải xem lại hoặc train lại sau khi dataset v2 được chốt; thay đổi dataset không tự sửa model đã học.

## 4. Hash chứng minh gì, không chứng minh gì?
Hash trong manifest chứng minh byte hiện tại của một file có khớp hay khác bản ghi; khi chạy lại trên v2, manifest cung cấp bằng chứng toàn vẹn theo từng file. Hash không chứng minh nhãn đúng, ảnh đúng nội dung, hoặc model sẽ hoạt động tốt.

## 5. Truy vết
Bộ truy vết dùng cảnh được nêu trong ticket (`scene_197`, `scene_309`) và lớp YOLO `bottle` (class_id 39). Tầng a gồm ảnh trong hai cảnh đó thuộc job guideline v1.2 và có box bottle; tier_b là ảnh bottle khác thuộc job guideline cũ, chưa thuộc hai cảnh. Guideline được lấy từ `jobs.csv`, không lấy từ metadata của từng ảnh.

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
<<>>
