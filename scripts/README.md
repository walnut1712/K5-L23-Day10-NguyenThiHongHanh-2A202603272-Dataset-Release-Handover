# Scripts của lab

Chạy **từ thư mục gốc repo**. Python 3.10+, chỉ thư viện chuẩn. Mọi script có `--help`. **Không sửa** các script này (xem [RULES.md](../RULES.md)); validator do nhóm tự viết trong `validator/`.

| Pha | Script | Việc | Ghi |
|---|---|---|---|
| 0 | `download_public.py` | tải 250 ảnh luyện tập + 50 ảnh `calib` (lô sạch); `--pool test` cho đề ẩn | `data_source/` |
| 0 | `run_lab.py` | tạo lô cho các seed, gắn `R-021` một lần vào seed đầu | `runs/r<seed>/`, `runs/lineage.jsonl` |
| 0 | `inject_release.py` | tạo một lô (seed thêm); `--no-faults` lô sạch trên pool `calib`; `--opaque` đề ẩn | `<out>/delivery`, `<out>/_private` |
| 1–2 | `score_findings.py` | tự đo `errors.json` + `trace.json` (F1 làm tròn); `--truth-dir` là chế độ giảng viên | `report.md` |
| 2 | `merge_review.py` | gộp lỗi luật + dòng `confirmed` của `review_log.csv` | `errors.json` |
| 1 | `pngutil.py` | đọc/ghi PNG RGB, đổi màu ↔ id segment | (thư viện) |
| 2 | `view_candidate.py` | mở một ứng viên với box detection và viền segment panoptic | ảnh overlay để review bằng mắt (Pillow) |
| 2 | `review_candidates.py` | mở từng ứng viên, nhập confirmed/rejected, ghi reviewer và ghi chú | cập nhật `review_log.csv` |
| 3–4 | `lineage.py` | ghi `decision` / `release --parent`, hỏi `impact` | `runs/lineage.jsonl` |
| 4 | `pack_release.py` | zip tái lập + sha256 | `<v2>.zip`, `<v2>.sha256` |
| 4 | `check_handover.py` | kiểm phần bàn giao, mã H1–H17 | (màn hình) |
| nộp | `export_submission.py` | `runs/` → `submission/`; `--import` cho người chấm | `submission/r<seed>/` |
| | `metrics.py` | định nghĩa nhóm lỗi và công thức điểm | (thư viện) |

Mở một ứng viên để xem ảnh phóng to với box đỏ và viền cyan của panoptic thing:

```powershell
py scripts/view_candidate.py runs/r3007/delivery runs/r3007/candidates.json --index 0 --zoom 3
```

Chỉ số `--index` bắt đầu từ 0; tăng chỉ số để xem ứng viên tiếp theo.

Để review theo từng phần và ghi thẳng vào CSV:

```powershell
py scripts/review_candidates.py runs/r3007 --reviewer "<Tên thành viên>" --start 0 --count 29 --zoom 3
```

Lặp lại với khoảng tiếp theo cho các thành viên. Với 171 ứng viên và 6 thành viên, gợi ý các khoảng: `0–28`, `29–57`, `58–86`, `87–115`, `116–144`, `145–170`.

## Mã kiểm của `check_handover.py`

| Mã | Kiểm |
|---|---|
| H1 | v1 giữ nguyên (release_id và hash nhãn) |
| H2–H3 | `errors.json` có đủ lỗi luật mức file (bộ kiểm tự tìm); mọi lỗi gán nhãn có dòng `confirmed`, ghi chú ≥ 20 ký tự và không chép giống nhau |
| H4–H7 | v2 đủ 7 phần; ảnh lỗi nhãn detection vào `rework_queue` và rời v2 (lỗi panoptic thì ở lại); ảnh rework phải có lỗi trong `errors.json`; đúng người gán/kiểm; nhãn không sửa tay |
| H8–H9 | `manifest.csv` sha256 đúng; `label_summary.csv` khớp |
| H10–H11 | `truyvet.csv` theo job; không còn cảnh rò train/val |
| H12–H13 | `README.txt` số liệu khớp; QC v1 có mẫu số, kết luận đúng ngưỡng 2% và khớp quyết định trong lineage |
| H14 | lineage: HOLD v1, release v2 có parent |
| H15 | đóng gói lại v2 ra đúng mã `.sha256` |
| H16–H17 | `trace.json`: `tier_a` và `notify` không rỗng, ảnh và người có thật; `security.md` đủ mục, ca khuôn mặt Hold và nêu ảnh cụ thể trong lô |

PASS là đúng **định dạng và nhất quán**, không có nghĩa nhãn đúng.
