# AGENTS.md — Quy tắc làm việc cho Codex

## 1. Mục tiêu và nguồn yêu cầu

Triển khai đồ án CS419 về truy xuất tài liệu tiếng Anh: nghiên cứu ảnh hưởng của lỗi chính tả trong truy vấn, so sánh VSM (TF-IDF + cosine) và Okapi BM25 trên BEIR SciFact bằng Python.

- Đặc tả chính: `DO_AN_1_Document_Retrieval_Specification.md` (nếu người dùng đổi tên thành `PROJECT_SPEC.md`, dùng tên mới; không tạo hai bản đặc tả mâu thuẫn).
- `PROGRESS.md` là nhật ký trạng thái và bàn giao, không thay thế đặc tả.
- Ưu tiên yêu cầu trực tiếp mới nhất của người dùng, sau đó đặc tả, sau đó các mặc định trong file này. Nếu có mâu thuẫn ảnh hưởng kết quả khoa học, nêu rõ trước khi thay đổi phạm vi.
- Không tự thay dataset, mô hình, độ đo chính hay giao thức thực nghiệm. Không mở rộng sang phân lớp văn bản.
- Nếu có `IMPLEMENTATION_PLAN.md`, dùng làm kế hoạch chi tiết; không coi kế hoạch là bằng chứng hoàn thành.

## 2. Quy trình mỗi session

1. Đọc `AGENTS.md`, `PROGRESS.md` và phần đặc tả liên quan; kiểm tra `git status` và cấu trúc repo ở mức cần thiết. Nếu chưa có Git, không tự khởi tạo khi không cần.
2. Đối chiếu nhiệm vụ hiện tại với trạng thái thực tế. Nếu người dùng chưa chỉ định nhiệm vụ, chọn bước chưa hoàn thành tiếp theo có đủ điều kiện trong `PROGRESS.md`.
3. Với nhiệm vụ nhiều bước, lập kế hoạch ngắn gồm đầu ra, file cần sửa và tiêu chí nghiệm thu. Thực hiện trong phạm vi được giao; không chỉ lập kế hoạch rồi dừng.
4. Đọc và sửa các file liên quan, ưu tiên tái sử dụng code hiện có. Không viết lại toàn bộ hệ thống nếu sửa cục bộ đủ dùng.
5. Chạy test hoặc kiểm tra phù hợp, ghi lệnh, kết quả thực tế và lỗi còn tồn tại. Không tự nhận test pass nếu chưa chạy.
6. Cập nhật `PROGRESS.md` trước khi kết thúc: trạng thái, file thay đổi, bằng chứng, quyết định, blocker và bước tiếp theo. Nếu có kế hoạch chi tiết, đồng bộ các mục tương ứng.
7. Trả lời bằng tiếng Việt, ngắn gọn: đã làm gì, kiểm tra gì, còn gì, bước tiếp theo. Không in lại toàn bộ code đã lưu trong repo trừ khi được yêu cầu.

## 3. Tiết kiệm context và quota Plus

- Dùng tìm kiếm theo tên/symbol (`rg` nếu có), đọc đoạn liên quan thay vì nạp toàn bộ repo. Chỉ mở rộng phạm vi khi thiếu bằng chứng.
- Không đọc toàn bộ corpus, qrels, index, log dài hoặc output thực nghiệm vào context; dùng thống kê, mẫu nhỏ, header và script tổng hợp. Không duyệt `.git`, `.venv`, cache, môi trường Python, binary, thư mục build nếu không liên quan.
- Không đọc lại cùng một file khi nội dung đã đủ và chưa thay đổi; không tạo bản sao tài liệu dài trong progress.
- Giới hạn số vòng thử sửa lỗi giống nhau: sau hai lần không hiệu quả, phân tích nguyên nhân, đổi cách kiểm chứng hoặc ghi blocker thay vì lặp vô hạn.
- Chạy test mục tiêu trước, smoke test trước thí nghiệm đầy đủ. Không chạy lại toàn bộ thí nghiệm khi artifact còn hợp lệ; kiểm tra config, dữ liệu và phiên bản code trước khi tái sử dụng.
- Không tải lại dữ liệu hoặc cài lại dependency nếu môi trường hiện có đáp ứng. Không tự bật nhiều agent hay tác vụ song song tốn kém.
- Gợi ý cho người dùng: Sol Medium cho triển khai thường, Sol High cho indexing/scoring, thiết kế thí nghiệm và phân tích; Luna cho công việc đơn giản; Astra chỉ khi cần review khó. Agent không tự giả định có quyền đổi model, reasoning hoặc mua thêm quota.

## 4. Các ràng buộc kỹ thuật và khoa học

- Dataset BEIR SciFact: lưu corpus, queries và qrels theo ID gốc; ghi nguồn, phiên bản/split, số lượng thực tế và cách tải. Không chỉnh sửa corpus hoặc relevance labels để cải thiện kết quả.
- Tiền xử lý tài liệu và truy vấn phải nhất quán trong mỗi cấu hình. Word unigram và character n-gram 3–5 theo đặc tả; ghi rõ tokenizer, normalization, stopwords/stemming nếu sử dụng.
- Tự hiện thực inverted index, VSM cosine và BM25; thư viện hỗ trợ xử lý dữ liệu/đánh giá được dùng nếu đặc tả cho phép, không dùng engine retrieval có sẵn thay cho phần cốt lõi bắt buộc. Có CLI truy vấn và xuất ranking.
- Kiểm chứng TF/DF/IDF, norm, document length, average length, BM25 parameters và xử lý term không tồn tại, truy vấn rỗng, tài liệu rỗng, tie-breaking. Ghi công thức và tham số thực tế.
- Noise generator: deletion, insertion, substitution, transposition; seed cố định/configurable, truy vết truy vấn gốc và nhiễu, báo mức nhiễu thực tế. Các mô hình phải dùng cùng bộ truy vấn nhiễu trong điều kiện so sánh tương ứng.
- Character n-gram là hướng giảm tác động chính; sửa chính tả theo từ điển là mở rộng nếu đặc tả yêu cầu hoặc người dùng duyệt. Không làm mở rộng trước khi baseline và thực nghiệm bắt buộc ổn định.
- Thực nghiệm E0–E4: lấy định nghĩa chính xác, mức nhiễu, cấu hình và điều kiện đối chứng từ đặc tả; không tự gán lại ý nghĩa các mã E.
- MAP trên ranking đầy đủ là độ đo chính; bổ sung P@5, P@10, Recall@10, nDCG@10 và tỷ lệ truy vấn không có kết quả. Ghi quy ước relevance, mẫu số, xử lý query không có relevant docs và missing results. Không gọi MAP@k là MAP đầy đủ; không bỏ query khó để tăng điểm.
- Không tune tham số dựa trên test qrels rồi báo như đánh giá độc lập. Nếu thiếu split phù hợp, giữ tham số định trước hoặc ghi rõ giới hạn và thiết kế validation được người dùng duyệt.
- So sánh công bằng: cùng corpus, query IDs, qrels và giao thức đo; mỗi lần thay đổi yếu tố cần nêu rõ. Lưu config, seed, run ID, ranking và metrics để tái lập.

## 5. Quy tắc code và kiểm thử

- Ưu tiên Python rõ ràng, module nhỏ, type hints cho API chính, docstring khi cần; tránh abstraction thừa. Tận dụng cấu trúc repo hiện hữu; nếu repo trống, có thể dùng `src/`, `tests/`, `data/`, `configs/`, `experiments/`, `results/`, `report/`.
- Dùng đường dẫn tương đối/configurable, UTF-8, tương thích Windows và Linux khi khả thi; không hardcode đường dẫn máy cá nhân. Ghi dependency và phiên bản Python thực tế trong README.
- Không ghi secret, token, dữ liệu riêng vào code/log. Không xóa file người dùng, reset Git, ghi đè kết quả cũ hay commit/push khi chưa được yêu cầu. Giữ nguyên thay đổi không liên quan.
- Test trên corpus toy có kết quả tính tay: tokenizer, postings, scoring, ranking, noise, metrics; thêm test edge case và kiểm tra seed tái lập. Test không phụ thuộc tải dataset lớn.
- Nếu dùng pytest, có thể chạy `python -m pytest -q` khi môi trường đã được thiết lập; lệnh chính thức phải khớp repo. Kiểm tra CLI và smoke test end-to-end trước full run.
- Không tuyên bố hoàn thành nếu không có artifact và bằng chứng nghiệm thu. Nếu bị chặn bởi mạng, quyền, dependency hoặc tài nguyên, ghi nguyên nhân thật, phần đã làm được và lệnh tiếp tục.

## 6. Kết quả và báo cáo

- Lưu kết quả có cấu trúc (CSV/JSON/TSV phù hợp), config/manifest và log theo run ID; không ghi đè run cũ. Ghi dataset/split, model, preprocessing, noise, seed, tham số, version code và thời gian chạy nếu đo được.
- Bảng và biểu đồ nên sinh bằng script từ kết quả thật; ghi rõ đơn vị, cutoff, chú thích và số query. Kiểm tra số liệu giữa file kết quả, biểu đồ và báo cáo.
- Báo cáo tiếng Việt, thuật ngữ tiếng Anh nhất quán; trình bày bài toán, dataset, cơ sở lý thuyết, phương pháp, thiết kế thí nghiệm, kết quả, phân tích, hạn chế, kết luận, tài liệu tham khảo theo đặc tả. Không tự suy diễn kết quả chưa chạy, không bịa citation, DOI hoặc số liệu. Gắn TODO rõ ràng cho phần thiếu bằng chứng.
- Phân biệt kết quả đo được, nhận xét và giả thuyết. Nếu kết quả trái kỳ vọng, phân tích thay vì sửa số liệu. Nêu giới hạn của SciFact và khả năng khái quát.
- README cần có hướng dẫn setup, tải dữ liệu, index, truy vấn, test, chạy thí nghiệm và tái tạo bảng/biểu đồ bằng lệnh đã kiểm chứng.

## 7. Quy tắc cập nhật PROGRESS.md

Giữ file ngắn, có thể đọc nhanh ở session mới. Dùng trạng thái `TODO`, `IN_PROGRESS`, `DONE`, `BLOCKED`; chỉ đánh dấu `DONE` khi có bằng chứng. Cập nhật bảng nhiệm vụ hiện hữu thay vì tạo checklist trùng. Ghi tối đa vài mục nhật ký gần nhất; nếu quá dài, chuyển lịch sử cũ sang file archive và giữ đường dẫn. Không xóa quyết định quan trọng, blocker chưa giải quyết hoặc bằng chứng nghiệm thu. Không lưu toàn bộ log/code trong progress.
