# PROGRESS.md — Tiến độ đồ án CS419

> File bàn giao giữa các session Codex. Cập nhật sau mỗi nhiệm vụ.

## 1. Thông tin dự án

| Thuộc tính | Giá trị |
|---|---|
| Đề tài | Nghiên cứu ảnh hưởng của lỗi chính tả trong truy vấn tới kết quả truy xuất tài liệu |
| Dataset | BEIR SciFact (tiếng Anh) |
| Mô hình | VSM: TF-IDF + cosine; Okapi BM25 |
| Biểu diễn | Word unigram; character n-gram 3–5 |
| Lỗi truy vấn | Deletion, insertion, substitution, transposition |
| Độ đo chính | MAP trên ranking đầy đủ |
| Độ đo bổ sung | P@5, P@10, Recall@10, nDCG@10, tỷ lệ query không có kết quả |
| Ngôn ngữ code | Python |
| Đặc tả | [PROJECT_SPEC.md](PROJECT_SPEC.md) |
| Kế hoạch | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) |
| Cập nhật lần cuối | 2026-11-25 — hoàn thành README và hướng dẫn tái lập P17 |

## 2. Trạng thái hiện tại

- Giai đoạn: đã tổng hợp thực nghiệm E0–E4 và viết bản báo cáo kỹ thuật tiếng Việt.
- Môi trường Python 3.12.10 đã xác minh các dependency và chạy được bộ test bằng pytest.
- Bước tiếp theo: P18 — review và nghiệm thu cuối.

## 3. Checklist triển khai

Trạng thái: `TODO` chưa làm/chưa xác minh; `IN_PROGRESS` đang làm; `DONE` đã nghiệm thu; `BLOCKED` bị chặn. Thay dấu `—` bằng đường dẫn artifact, lệnh kiểm tra hoặc tham chiếu run khi có bằng chứng. Nếu repo đã có phần hoàn chỉnh, kiểm tra rồi cập nhật thay vì làm lại.

| ID | Nhiệm vụ | Trạng thái | Tiêu chí nghiệm thu / bằng chứng |
|---|---|---|---|
| P00 | Xác định phạm vi và soạn đặc tả | DONE | `git ls-files` xác nhận `docs/PROJECT_SPEC.md` |
| P01 | Khảo sát repo, đối chiếu đặc tả, lập kế hoạch | DONE | `git ls-files` và `rg --files --hidden` (bỏ qua `.git`, `.venv`) xác nhận cấu trúc. Kế hoạch bao phủ P02–P18 và khớp ma trận E0–E4 trong §10. |
| P02 | Thiết lập môi trường và dependency | DONE | `.venv` dùng Python 3.12.10 và pip 25.0.1. Các dependency trực tiếp được pin trong `requirements.txt`. Đã chạy `pip install --no-index -r requirements.txt` trên venv hiện có, `pip check` và `pytest -q`. |
| P03 | Tải và kiểm tra SciFact | DONE | Dữ liệu người dùng tải từ Hugging Face BEIR. `data/raw/scifact/dataset_manifest.json` có SHA-256 từng tệp. `data/processed/scifact/dataset_stats.{json,csv}` xác nhận 5.183 tài liệu, train 809 query/919 qrel, test 300 query/339 qrel, mọi nhãn bằng 1, split không giao. |
| P04 | Tiền xử lý và chọn term | DONE | `src/preprocessing.py`, `src/term_selection.py` và 3 test mẫu kiểm tra NFKC, word/char, DF/CF, ngưỡng lọc và hai loại tỷ lệ giữ lại. CLI sinh TSV/JSON cho cả word và char trên mẫu. |
| P05 | Xây dựng inverted index | DONE | `src/inverted_index.py`. Kiểm tra TF/DF/CF, độ dài, norm và lưu/tải trên mẫu. `indexes/word/index_stats.csv` có 35.731 term và 633.511 postings trên SciFact. |
| P06 | VSM TF-IDF + cosine | DONE | `src/tfidf.py`. Test tính tay cho cosine, norm toàn vector và OOV đạt. |
| P07 | Okapi BM25 | DONE | `src/bm25.py`. Test tính tay, query term lặp, độ dài trung bình bằng 0 và tham số tùy chỉnh đạt. |
| P08 | CLI và lưu ranking | DONE | `src/cli.py`. `build-index` và `search` đã chạy trên SciFact. Xác minh JSON top 5 có doc ID duy nhất, điểm dương, rank đúng thứ tự và snippet trong phần hiển thị. |
| P09 | Noise generator | DONE | `src/noise_generator.py`, `src.cli generate-noise`, `tests/test_noise.py`. Kiểm tra 51 điều kiện sinh lỗi trên 300 query test. Hai lần chạy CLI cùng seed cho JSONL và manifest giống từng byte. |
| P10 | Character n-gram retrieval | DONE | `build-index --analyzer char` xuất 84.202 term và 5.381.877 postings. Cả VSM/BM25 đọc lại char index và xuất top 5 trên truy vấn SciFact có lỗi. |
| P11 | Bộ đánh giá | DONE | `src/evaluation.py`, `tests/test_evaluation.py`. Ví dụ AP của đặc tả đạt. Đối chiếu phép tính độc lập trên 200 ranking mẫu và 20 ranking BM25 đầy đủ từ SciFact. |
| P12 | Thiết kế giao thức E0–E4 | DONE | `configs/default.yaml`, `src/experiments.py`, `tests/test_experiments.py`. CLI `plan-experiments` xuất 20 ứng viên E0, 204 lượt test và 50 khóa nhiễu dùng chung. Xác nhận tập E4 và phép ghép baseline sạch. |
| P13 | Smoke test end-to-end | DONE | `src/experiment_runner.py`, CLI `tune` và `experiment`, `tests/test_integration.py`. Corpus toy cho 20 ứng viên E0, 204 ranking, 50 bộ nhiễu và 368 dòng per-query. Xác minh checksum, query rỗng và baseline tập con E4. |
| P14 | Chạy thực nghiệm E0–E4 | DONE | `data/processed/p14-scifact-20261125/` có E0 selection, 204 rankings và manifest, 50 bộ nhiễu, 61.200 dòng metric theo query, summary và `verification.json`. |
| P15 | Tổng hợp bảng, biểu đồ và phân tích | DONE | `src/results_analysis.py`, `src/case_analysis.py` và [kết quả P15](../results/p15-scifact-20261125/analysis.md). 44 nhóm tổng hợp, 5 hình và 6 ca. Tái chạy và xác nhận 12 artifact giống từng byte. |
| P16 | Viết báo cáo | DONE | [report/report.md](../report/report.md) có tám chương, công thức, ba sơ đồ, năm hình và sáu ca. Đối chiếu các bảng với CSV nguồn. Mã môn học, thông tin và phân công nhóm chờ bổ sung trước khi nộp. |
| P17 | README và hướng dẫn tái lập | DONE | [README.md](../README.md). Đã thử nhập ZIP mẫu, thống kê, hai index/truy vấn, nhiễu, lịch chạy, tune, 204 lượt test mẫu, chạy riêng E4 và phân tích từ mẫu/kết quả P14. |
| P18 | Review và nghiệm thu cuối | TODO | Checklist đặc tả, test, kiểm tra số liệu và báo cáo, gói bàn giao |

Mở rộng sửa lỗi theo từ điển: chưa triển khai; chỉ thực hiện nếu cần theo đặc tả hoặc được người dùng duyệt. Các ID trên là kế hoạch theo dõi, không thay đổi định nghĩa thí nghiệm E0–E4 trong đặc tả.

## 4. Trạng thái thực nghiệm

Điều kiện theo §10 của đặc tả. Mọi thí nghiệm dùng M1–M4.

| Thí nghiệm | Điều kiện | Trạng thái | Run ID / config | Kết quả / log |
|---|---|---|---|---|
| E0 | Train/dev sạch, chọn analyzer và tham số | DONE | 20 ứng viên trên 809 query | `E0/tuning.csv`, `E0/selected_config.yaml` |
| E1 | Test sạch, baseline | DONE | 4 lượt | MAP M1/M2/M3/M4 lần lượt 0,587277 / 0,626186 / 0,580439 / 0,597523 |
| E2 | Mixed 10/20/30/50%, 5 seed | DONE | 80 lượt | `E1-E4/metrics/summary.csv` |
| E3 | Bốn loại lỗi riêng, 20%, 5 seed | DONE | 80 lượt | `E1-E4/metrics/summary.csv` |
| E4 | Mixed cố định 1/2 token, 5 seed, tập con có ít nhất 2 token hợp lệ và baseline sạch tương ứng | DONE | 40 lượt, 300 query đủ điều kiện | Baseline ghép E1 theo qid, đã đối chiếu cả 40 lượt |

- Dataset version/split: bản Hugging Face BEIR, train/test đã xác thực. Manifest ghi hai ref `main` quan sát được trong cache lúc kiểm tra và SHA-256 chính xác của dữ liệu dùng.
- E0 chọn `min_df=1` cho cả bốn cấu hình, BM25 word `k1=1.5,b=0.75` và BM25 char `k1=1.2,b=0.5`.
- Các đường dẫn kết quả trong bảng tính từ `data/processed/p14-scifact-20261125/`. Summary có 204 dòng, ranking JSONL đầy đủ khoảng 18,55 GB, và manifest ghi checksum dữ liệu, code, index, noise và ranking.
- Bản tổng hợp dễ tìm trong cây dự án: [results/p14-scifact-20261125/summary.csv](../results/p14-scifact-20261125/summary.csv). Đã xác minh SHA-256 trùng với CSV gốc trong `data/processed/` và đủ 204 dòng dữ liệu.

## 5. Trạng thái báo cáo

Đây là nhóm nội dung theo dõi, không phải số chương bắt buộc; đối chiếu cấu trúc báo cáo trong đặc tả.

| Nội dung | Trạng thái | Nguồn bằng chứng cần có |
|---|---|---|
| Giới thiệu, mục tiêu, phạm vi | DONE | Chương 1 |
| Cơ sở lý thuyết và tài liệu tham khảo | DONE | Chương 2 và nguồn xuất bản gốc |
| Dataset, tiền xử lý và lập chỉ mục | DONE | Chương 3, 5, 6 |
| VSM, BM25 và xử lý lỗi chính tả | DONE | Chương 4–5 |
| Thiết kế thực nghiệm và độ đo | DONE | Chương 6 |
| Kết quả, bảng và biểu đồ | DONE | Chương 7, đối chiếu P14/P15 |
| Phân tích, hạn chế và kết luận | DONE | Chương 7–8 và sáu ca truy vấn |
| Rà soát trích dẫn và định dạng | IN_PROGRESS | Đã kiểm tra nguồn và liên kết bản Markdown. Cần nhóm xác nhận mã học phần, bìa, phân công và định dạng nộp. |

## 6. Bằng chứng kiểm tra gần nhất

| Hạng mục | Lệnh / artifact | Kết quả |
|---|---|---|
| Môi trường | `py -3.12 --version`, `. .\.venv\Scripts\Activate.ps1`, `.\.venv\Scripts\python.exe --version` và `-m pip --version` | Launcher không tìm thấy bản cài trong sandbox. Đã tạo venv bằng đường dẫn trực tiếp đến Python 3.12.10 và xác minh kích hoạt cùng pip 25.0.1. |
| Unit test | `.\.venv\Scripts\python.exe -m pytest -q` | 30 test và 6 subtest đạt |
| CLI | `src.cli search` và `src.cli generate-noise --split test --noise-type mixed --rate 0.2 --seed 42` | 4 cấu hình truy xuất đã đạt trên SciFact. Artifacts nhiễu ở `data/processed/noise/test/mixed-rate0.2-seed42/`. |
| Smoke test | `.\.venv\Scripts\python.exe -m pytest -q --basetemp data/processed/smoke-p13-ed8684bb` | Đạt. Artifact ở `data/processed/smoke-p13-ed8684bb/test_tune_and_experiment_cli_e0/`. Xác minh lại checksum trên toàn bộ 204 manifest. |
| Full experiment | `src.cli tune --split train`, tiếp theo `src.cli experiment --split test --selected-config ...` trong venv | Hai lệnh thoát mã 0, stderr rỗng. `verification.log` và `verification.json` ghi đối chiếu 204 SHA-256, query/variant ID, trung bình metric và baseline theo qid. |
| Tái lập bảng/biểu đồ | `.\.venv\Scripts\python.exe -m src.results_analysis --output <thư-mục-mới>` | Đạt. Đối chiếu 44 nhóm với CSV P14, 6 ca truy vấn và 5 PNG. Tái chạy cho checksum trùng đủ 12 artifact sinh tự động. |

## 7. Quyết định và blocker

- D01: Chọn SciFact, VSM và BM25; giữ corpus/qrels không đổi khi tạo lỗi truy vấn.
- D02: MAP đầy đủ là metric chính; character n-gram là hướng khắc phục chính.
- D03: Dùng đặc tả làm nguồn yêu cầu, tránh tự mở rộng phạm vi.
- D04: Dự kiến dùng metric từng query của E1 để tính baseline sạch trên tập con E4.
- D05: Dùng Python 3.12 theo yêu cầu. Dùng `py -3.12` để chọn bản Python gốc khi launcher nhận diện được bản cài. Khi chạy trong venv, dùng `.\.venv\Scripts\python.exe` để chọn đúng interpreter.
- D06: Dùng unittest có sẵn để kiểm thử trong sandbox. Manifest ghi cả thông tin giấy phép từ [dataset card BEIR](https://huggingface.co/datasets/BeIR/scifact) và [giấy phép SciFact gốc](https://github.com/allenai/scifact/blob/master/LICENSE.md), cùng kết quả đối chiếu checksum ZIP do [BEIR công bố](https://github.com/beir-cellar/beir).
- D07: Dùng dữ liệu BEIR SciFact người dùng đã tải qua `download_scifact_hf.py`. Lưu checksum từng tệp vì dữ liệu này đến từ bản phân phối Hugging Face. Giữ nguyên dữ liệu và script tải của người dùng.
- D08: Chỉ sửa các token chữ ASCII từ 3 ký tự. Token trộn số hoặc dấu gạch dưới được giữ nguyên. Transposition yêu cầu hai ký tự kề nhau khác nhau sau lowercase. Mixed chọn đều giữa các phép khả thi cho token đã chọn. Cờ `matches_corpus_word` dùng từ vựng corpus để hỗ trợ rà mẫu.
- D09: Tập đánh giá lấy từ qrels đưa vào. Query thiếu ranking được tính là rỗng. Query thiếu qrel dương được đếm và loại khỏi mọi trung bình, gồm tỷ lệ rỗng. Nếu tập đánh giá rỗng, kết quả tổng hợp là `None`.
- Đã đối chiếu §11 với `ir-measures==0.4.3`. Năm metric khớp trên fixture gồm ranking rỗng và hit sau hạng 10, đồng thời khớp đủ 100 giá trị theo query trên 20 ranking SciFact.
- D10: E0 chọn riêng cho M1–M4 theo MAP train sạch và ưu tiên ứng viên đứng trước khi hòa. Lưới mặc định thử `min_df` 1/2, BM25 `k1` 1.2/1.5 và `b` 0.75/0.5. Báo tham số đã chọn vì các cấu hình có thể khác nhau cả về biểu diễn lẫn ngưỡng DF.
- D11: Dừng lượt chạy E0 ban đầu vì scorer từng query chậm, sau đó chạy lại toàn bộ E0 và E1–E4 bằng scorer batch NumPy trên posting thưa. Đối chiếu chính xác từng doc ID và score trên 30 query SciFact train cùng 2 ca rỗng/OOV, ở VSM/BM25 word/char. Đầu ra chuẩn dùng `E0/` và `E1-E4/`, tách khỏi thư mục staging của lượt dừng.
- P02 đã gỡ chặn nhờ các gói có sẵn trong venv. Lệnh cài requirements được xác minh trên venv hiện tại, còn cài mới từ PyPI chưa được kiểm tra trong sandbox.

## 8. Bàn giao session

- P18: rà soát checklist §16 của đặc tả, test và số liệu, sau đó chuẩn bị gói bàn giao. Bổ sung thông tin bìa và phân công thực tế vào [báo cáo](../report/report.md).

## 9. Nhật ký gần nhất

### 2026-11-25 — Nghiệm thu P17

- Viết hướng dẫn cài đặt, dữ liệu, truy vấn, thực nghiệm theo nhóm, bảng/hình và lỗi thường gặp trong `README.md`. Ghi giới hạn runner hiện yêu cầu thư mục mới và chưa bỏ qua từng run đã hoàn thành trong một đợt.
- `pip install --no-index -r requirements.txt` trên venv hiện có, `pip check`, 30 test và 6 subtest đều đạt. Launcher `py -3.12` vẫn không nhìn thấy bản cài trong sandbox, nên đã chạy bằng interpreter của venv. Chưa xác minh cài mới từ PyPI.
- Kiểm tra tái lập tại `data/processed/p17-vye8t58i/`. Đủ 204 lượt trên corpus mẫu và 44 lượt khi chọn riêng E4 kèm E1. Tái sinh đủ 12 artifact P15 từ bản P14 đã lưu với SHA-256 khớp.

### 2026-11-25 — Hoàn thành P16

- Viết báo cáo theo §14. Sinh sáu bảng từ dữ liệu P15 và tính tỷ lệ sửa E2 thực tế từ manifest nhiễu.
- Kiểm tra 34 liên kết cục bộ, 5 hình, 4 baseline E1, 40 ô điều kiện nhiễu và 6 ca. Đối chiếu công thức với scorer và nguồn trích dẫn với sách/bài báo gốc.
- Bước tiếp theo: P17.

### 2026-11-25 — Nghiệm thu P15

- Dùng Matplotlib 3.11.2 trong venv. `pip check` đạt, 30 test và 6 subtest đạt. Kết quả nằm trong `results/p15-scifact-20261125/`; giữ nguyên kết quả P14.
- Sau khi người dùng báo thư mục trống, kiểm tra lại trên đĩa thấy đủ 13 tệp. Đóng gói [P15 ZIP](../results/p15-scifact-20261125.zip) và đối chiếu nội dung từng tệp trong ZIP với bản gốc.
- Tính mean và độ lệch chuẩn mẫu qua 5 seed, chênh MAP tuyệt đối và tương đối. Phân tích 3 ca giảm mạnh nhất và 3 ca cải thiện nhất theo AP của BM25 word, mixed 20%, seed 42. So sánh cùng variant với BM25 char và đối chiếu OOV từ các bảng gốc.
- Bước tiếp theo: P16.

### 2026-11-25 — Nghiệm thu P14

- E0 mất khoảng 121 giây và E1–E4 khoảng 868 giây theo dấu thời gian stdout log. Đã đối chiếu số lượng, checksum của 204 ranking, qid/variant ID của 61.200 bản ghi và tính lại các metric tổng hợp từ per-query CSV. Giữ checksum dữ liệu gốc và 50 bộ nhiễu.
- Bước tiếp theo: P15.

### 2026-11-25 — Nghiệm thu P13

- Smoke test gọi CLI thật trên 2 tài liệu, 1 query train và 2 query test. E0 chạy trước khi test qrels tồn tại. Một query test không có hit vẫn có ranking rỗng và AP bằng 0. E4 dùng đúng tập con một query, baseline MAP 1,0 trên tập con so với 0,5 trên toàn tập mẫu cho M1.
- Xác minh đầu ra, chia sẻ bộ nhiễu, từ chối ghi đè và phát hiện `tuning.csv` bị đổi. Các giá trị trên chỉ thuộc corpus mẫu của P13.

### 2026-11-25 — Nghiệm thu P12

- Lệnh `python.exe -m src.cli plan-experiments --config configs/default.yaml --output data/processed/experiment_plan.json` trong venv đã xuất lịch E0–E4. Kiểm tra đủ 4/80/80/40 lượt test, 10 điều kiện E4 đạt số token cần sửa trên toàn tập con. `pip check` đạt.
- Bước tiếp theo: P13.

### 2026-11-25 — Nghiệm thu P11

- Kiểm tra AP sau hạng 10, qrel dương bị bỏ lỡ, ranking rỗng hoặc thiếu, query thiếu qrel dương và nDCG nhị phân. Đối chứng nội bộ khớp cả sáu chỉ số từng query với sai số tối đa cho phép `1e-12`.
- Bước tiếp theo: P12.

### 2026-11-25 — Nghiệm thu P09

- Kiểm tra ID, số token sửa, lựa chọn không lặp, checksum dữ liệu gốc và chạy lại CLI trong tiến trình riêng. Mixed 20%, seed 42 sửa 603/3.057 token (19,73%) và đổi 300/300 query. Manifest ghi phân bố số phép sửa và SHA-256.
- Rà bốn query đầu theo ID, ví dụ qid 1 có `show → shtw`, qid 100 có `stem → ste` và `randomly → randcmly`. 48/603 token sửa trùng từ trong corpus.
- Bước tiếp theo: P11.

### 2026-11-25 — Nghiệm thu P02

- Xác minh và pin `datasets==5.2.0`, `huggingface-hub==2.4.0` và `pytest==9.2.0`. Kiểm tra dependency và toàn bộ test đạt.

### 2026-11-25 — Kiểm tra dữ liệu thật và truy xuất SciFact

- Nghiệm thu P03, P05–P08 và P10. Sinh manifest, thống kê dữ liệu, hai chỉ mục và thống kê từ vựng. Chạy 9 unit test và xác nhận 4 cấu hình CLI.
- Chỉ mục word dùng 13.562.755 byte và build khoảng 1,17 giây. Chỉ mục char dùng 76.917.219 byte và build khoảng 26,03 giây. Thời gian chỉ tính xây chỉ mục trong bộ nhớ, ghi trong `indexes/{word,char}/index_stats.csv`.
- Bước tiếp theo: P09.

### 2026-11-25 — Xác thực dữ liệu và chọn term

- Thêm các module trong `src/`, kiểm thử trong `tests/` và quy tắc bỏ qua dữ liệu/vocabulary sinh ra trong `.gitignore`.
- Kiểm tra kích hoạt venv bằng lệnh PowerShell người dùng cung cấp. 5 test và luồng CLI nhập ZIP → thống kê → vocabulary word/char đạt trên mẫu.
- Ghi P02/P03 bị chặn ở bước xác minh bằng dependency và dữ liệu thật. P04 đã nghiệm thu trên mẫu.

### 2026-11-25 — Thiết lập môi trường Python cho P02

- Tạo `.venv`, thêm vào `.gitignore` và xác minh PowerShell đã kích hoạt môi trường qua `VIRTUAL_ENV`, đường dẫn interpreter và phiên bản pip.

### 2026-11-25 — P01 Khảo sát repo và lập kế hoạch

- Xác nhận repo chỉ có tài liệu và tên đặc tả hiện tại là `docs/PROJECT_SPEC.md`.
- Thêm `docs/IMPLEMENTATION_PLAN.md`, cập nhật `docs/PROGRESS.md` với giao thức E0–E4, các phụ thuộc và bằng chứng kiểm tra.
- Kiểm tra PowerShell đạt yêu cầu về độ phủ P02–P18, các dòng E0–E4, trạng thái bàn giao và liên kết Markdown.
- Bước tiếp theo: P02.

### 2026-11-25 — Khởi tạo hướng dẫn và theo dõi tiến độ

- Tạo `AGENTS.md` và `PROGRESS.md` dựa trên phạm vi đã xác định.
- Chưa sửa mã nguồn, tải dữ liệu, chạy test hoặc thực nghiệm trong lần khởi tạo này.
- Bước tiếp theo: P01.

<!-- Khi kết thúc session, thêm mục mới ở đầu nhật ký:
### YYYY-MM-DD — Pxx: tên nhiệm vụ
- Đã làm: ...
- File thay đổi: ...
- Kiểm tra: lệnh + kết quả thực tế ...
- Quyết định / blocker: ...
- Bước tiếp theo: ...
Đồng thời cập nhật các bảng và mục bàn giao ở trên. Không để nhật ký dài vô hạn.
-->
