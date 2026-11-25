# Kết quả truy xuất SciFact

E0 chọn cấu hình bằng MAP trên 809 truy vấn train sạch. Cả bốn cấu hình chọn `min_df=1`. BM25 word chọn `k1=1.5, b=0.75`, còn BM25 char chọn `k1=1.2, b=0.5`. Các so sánh BM25 word/char vì vậy là so sánh hai cấu hình đã tối ưu trên train. Các bảng E2–E4 dùng trung bình và độ lệch chuẩn mẫu trên 5 seed. Mỗi lượt dùng 300 truy vấn test. [Thống kê dữ liệu](dataset_stats.csv) · [Kết quả E0](tuning.csv) · [Bảng tổng hợp](aggregate.csv)

## Ảnh hưởng của mức nhiễu

BM25 word dẫn đầu trên truy vấn sạch với MAP 0,6262, tiếp theo là BM25 char (0,5975), VSM word (0,5873) và VSM char (0,5804). BM25 word cũng có nDCG@10 cao nhất (0,6645), còn VSM char có Recall@10 cao nhất (0,7860). [Bảng baseline E1](baseline.csv)

Ở mức mixed 50%, MAP của VSM word và BM25 word giảm lần lượt 14,14 và 14,35 điểm phần trăm. VSM char và BM25 char giảm 3,59 và 3,99 điểm phần trăm. BM25 char đạt MAP 0,5577 ở mức này, cao nhất trong bốn cấu hình. Biểu diễn char giảm ít điểm hơn word cho cả hai mô hình ở cả bốn mức mixed. Giữa VSM và BM25, thứ tự theo mức suy giảm thay đổi theo điều kiện. [Bảng E2](aggregate.csv) · [Biểu đồ MAP theo tỷ lệ nhiễu](figures/mixed_rate_map.png)

Ở E4, cả bốn cấu hình giảm MAP nhiều hơn khi sửa hai token so với một token. Mức giảm khi sửa hai token là 4,86 và 5,97 điểm phần trăm cho VSM word và BM25 word, so với 1,53 và 1,18 cho VSM char và BM25 char. Baseline được tính trên cùng tập đủ điều kiện, gồm cả 300 truy vấn trong bộ dữ liệu này. [Bảng E4](aggregate.csv) · [Biểu đồ theo số token bị sửa](figures/fixed_edits_drop.png)

## Ảnh hưởng của loại lỗi

Ở mức 20%, loại lỗi có mức giảm trung bình lớn nhất khác nhau theo cấu hình. Insertion gây giảm nhiều nhất cho VSM word (4,10 điểm phần trăm), substitution cho BM25 word (4,30), transposition cho VSM char (1,49) và deletion cho BM25 char (1,62). Các khoảng độ lệch chuẩn chồng lấn ở nhiều điều kiện. Thứ tự này mô tả điểm trung bình quan sát được qua 5 seed. [Bảng E3](aggregate.csv) · [Biểu đồ theo loại lỗi](figures/error_type_drop.png)

## Truy vấn đại diện

Giữ cố định điều kiện mixed 20%, seed 42. Xếp theo AP nhiễu trừ AP sạch của BM25 word. Lấy ba mức giảm lớn nhất và ba mức tăng lớn nhất trong nhóm ổn định hoặc cải thiện, dùng ID truy vấn để xử lý khi hòa. [Bảng ca phân tích](cases.csv) · [Chi tiết phép sửa, term và ranking](cases.json)

- **536, 237 và 692** là ba ca suy giảm mạnh nhất. Với 536, `Hypocretin → Hypccretin` làm mất term word và tài liệu qrel rơi từ hạng 1 xuống 31. BM25 char giữ tài liệu ở hạng 1, phù hợp với việc lỗi vẫn giữ một phần n-gram. Với 692, `red → led` tạo một từ có trong corpus, nên truy vấn nhiễu có thể khớp thêm các tài liệu qua từ mới.
- **54, 1266 và 127** là ba ca cải thiện nhiều nhất theo BM25 word. Ở 54, tài liệu qrel từ hạng 9 lên 1. Kết quả phù hợp với khả năng việc làm mất hai term đã thay đổi thứ tự cạnh tranh giữa các tài liệu. Ở 127, tài liệu qrel đi từ hạng 2 lên 1 với word nhưng từ 23 xuống 30 với char. Kết quả char nhiễu đặt tài liệu 293661 ở hạng 1. Tài liệu này không có qrel dương và chia sẻ các n-gram như `arg`, `argi` và `argin`. Các khớp cục bộ này là một giải thích khả dĩ cho thứ hạng, trong phạm vi đánh giá qrels của benchmark. [Chi tiết ca phân tích](cases.json)

## Chi phí và giới hạn

Char có khoảng 5,38 triệu postings và chiếm 73,35 MiB. Word có 633.511 postings và chiếm 12,93 MiB. Thời gian xây index trong bộ nhớ đo được lần lượt là 24,57 và 0,98 giây. Trung vị latency của BM25 char là 2,53 ms/truy vấn, so với 0,84 ms của BM25 word. Latency tính phần truy xuất của scorer batch, không gồm nạp index hay ghi kết quả. [Bảng chi phí](index_cost.csv) · [Chi phí index](figures/index_cost.png) · [Latency](figures/query_latency.png)

SciFact có ít qrel dương cho mỗi truy vấn và các tài liệu chưa được đánh giá có thể vẫn liên quan. Các truy vấn là nhận định khoa học, sửa lỗi theo quy tắc tổng hợp. Mức nhiễu trên biểu đồ là tỷ lệ mục tiêu. Khi làm tròn số token cần sửa, tỷ lệ thực tế có thể khác. Kết quả mô tả benchmark và giao thức này, chưa có kiểm định ý nghĩa thống kê hay bằng chứng trên lỗi gõ thực tế.

## Tái tạo bảng và hình

Chạy từ thư mục gốc dự án với một thư mục đầu ra mới.

```powershell
.\.venv\Scripts\python.exe -m src.results_analysis --output results/p15-reproduction
```
