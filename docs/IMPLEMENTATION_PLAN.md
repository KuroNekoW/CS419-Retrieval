# Kế hoạch triển khai đồ án truy xuất tài liệu

Dùng [đặc tả](PROJECT_SPEC.md) để xác định yêu cầu và [PROGRESS.md](PROGRESS.md) để theo dõi nghiệm thu. Repo hiện có đặc tả, hai PDF môn học và tài liệu bàn giao. Các đường dẫn dưới đây là đầu ra dự kiến.

## Thứ tự thực hiện và nghiệm thu

| Bước | Phụ thuộc | Đầu ra và điều kiện nghiệm thu |
|---|---|---|
| P02 | P01 | Thiết lập Python và `requirements.txt` với phiên bản đã kiểm chứng, `.gitignore` cho môi trường và dữ liệu sinh ra. Kiểm tra tạo venv, cài dependency và chạy pytest trong venv. |
| P03 | P02 | `src/data_loader.py`, `src/dataset_stats.py`. Tải SciFact theo §3, lưu nguồn, ngày, SHA-256, phiên bản và giấy phép đã đối chiếu. Kiểm tra trùng/thiếu ID, trường rỗng, qrels, score và train/test tách biệt. Xuất manifest và thống kê JSON/CSV theo split. |
| P04–P05 | P03 | `src/preprocessing.py`, `src/term_selection.py`, `src/inverted_index.py`. Dùng NFKC, lowercase, token ASCII chữ/số, giữ số và mặc định giữ stopword. Làm word unigram trước. Xuất DF/CF, lý do lọc, danh sách term giữ lại và tỷ lệ giữ distinct term. Kiểm tra postings, độ dài sau lọc, avgdl gồm tài liệu rỗng, norm toàn vector và tính nhất quán sau lưu/tải. |
| P06–P08 | P05 | `src/tfidf.py`, `src/bm25.py`, `src/retrieval.py`, `src/cli.py`. Tự tính log-TF, IDF có smoothing và cosine theo §7.1. BM25 theo §7.2 với mặc định k1=1.2, b=0.75, mỗi query term phân biệt góp một lần. Tính điểm qua postings, kiểm thử bằng ví dụ tính tay, query rỗng/OOV và tie theo doc ID chuỗi tăng dần. CLI đọc index đã lưu, trả doc ID/rank/score cùng tiêu đề và snippet cho demo. |
| P09 | P04 | `src/noise_generator.py`. Sinh bốn phép sửa trên token chữ ASCII đủ điều kiện, chọn vị trí không hoàn lại, áp dụng quy tắc làm tròn §8.2 và lưu metadata gốc/nhiễu theo qid. Kiểm thử từng phép, truy vấn thiếu token, tỷ lệ 0 và tính tái lập với SHA-256 từ seed, qid và điều kiện. |
| P10 | P04–P08 | Tích hợp character n-gram 3–5 trong từng token, giữ tần suất lặp và dùng tiền tố `short:` cho token ngắn. Tái sử dụng index/scorer, dùng thống kê riêng của char index, kiểm thử CLI và xuất vocabulary/index stats cho cả word và char. |
| P11 | P08 | `src/evaluation.py`. Tính MAP trên mọi hit có điểm dương hữu hạn, P@5, P@10, Recall@10, nDCG@10 và tỷ lệ query rỗng theo §11. Dùng qrel dương, ghi số query bị loại vì thiếu qrel dương, giữ query không có hit. P@k chia k và AP chia tổng số tài liệu liên quan. Kiểm tra fixture tính tay và đối chiếu công cụ tham chiếu. |
| P12–P13 | P09–P11 | `configs/default.yaml`, `src/experiments.py`. Chốt config và schema theo §10, §12.2. Chạy smoke test trên corpus toy qua load → index → query sạch/nhiễu → retrieval → evaluation → xuất kết quả. Kiểm tra query rỗng vẫn có bản ghi và scorer dùng chung biến thể nhiễu. |
| P14 | P03, P13 | Chạy E0 trước, lưu lựa chọn dev rồi chạy E1–E4. Lưu ranking, metric từng query, tổng hợp, log và manifest theo run ID với checksum dữ liệu/index/noise, config, phiên bản mã, môi trường và cutoff. Kiểm tra độ phủ từng điều kiện và số query trước khi tổng hợp. |
| P15–P18 | P14 | Sinh bảng và biểu đồ từ CSV thật, tính mean/std qua seed và drop tuyệt đối/tương đối. Chọn ít nhất 3 case giảm mạnh và 3 case ổn định/cải thiện nếu đủ. Hoàn thiện báo cáo tiếng Việt theo §14, README với lệnh đã chạy, slide, phân công và demo. Rà soát kết quả, rubric và toàn bộ checklist §16. |

## Giao thức thực nghiệm

M1 là VSM word, M2 là BM25 word, M3 là VSM char, M4 là BM25 char. Cả bốn dùng cùng corpus, qrels theo split và biến thể truy vấn cho mỗi điều kiện. Giữ cả hai index để tái sử dụng giữa các lượt. Dùng seed 42–46 cho E2–E4.

| Thí nghiệm | Điều kiện và kiểm soát | Lượt đánh giá dự kiến |
|---|---|---|
| E0 | Train/dev sạch cho M1–M4. Chốt tiêu chí trước khi chạy, mặc định MAP dev sạch. Lưu tuning.csv và selected_config.yaml trước khi chạy test. | Theo số cấu hình dev |
| E1 | Test sạch, mỗi cấu hình chạy một lần. | 4 |
| E2 | Test mixed, tỷ lệ 10/20/30/50% trên số token đủ điều kiện. Ghi tỷ lệ thực tế, số query đổi và phân bố số token bị sửa. | 80 |
| E3 | Test riêng deletion, insertion, substitution và transposition, tỷ lệ 20%. | 80 |
| E4 | Test mixed với đúng 1 hoặc 2 token bị sửa. Dùng tập query có ít nhất 2 token đủ điều kiện cho cả hai mức. Tính lại baseline sạch từ kết quả từng query của E1 trên tập con này và ghi số query bị loại. | 40 lượt nhiễu và 4 giá trị baseline tập con từ E1 |

Tổng E1–E4 là 204 lượt chạy cấu hình. Tại P12, xác nhận quy tắc xác định tập con E4 và kiểm tra qid khớp khi lấy baseline. E5 và sửa chính tả theo từ điển là mở rộng. Xác nhận mã môn học (CS416 trong đề cương, CS419 trong tên file), nhóm và quy định nộp bài ở mốc hoàn thiện báo cáo.

P12 đã mã hóa lịch chạy trong `configs/default.yaml` và `src/experiments.py`. E0 có 20 ứng viên và chọn riêng cho từng M1–M4 theo MAP trên truy vấn train sạch. Khi hòa điểm, chọn cấu hình đầu tiên trong lưới đã định, ưu tiên mặc định. Các cấu hình sau E0 có thể dùng ngưỡng DF khác nhau, vì vậy so sánh word/char sẽ báo rõ tham số được chọn. Kế hoạch có 50 khóa nhiễu dùng chung cho bốn mô hình. Runner ở P13 ghi `tuning.csv` và `selected_config.yaml` trong bước tune. Khi chạy test, runner xác minh cấu hình và checksum, sau đó lấy baseline E4 bằng cách lọc ranking E1 theo đúng qid của tập con. Smoke test đã chạy đủ ma trận trên corpus toy.
