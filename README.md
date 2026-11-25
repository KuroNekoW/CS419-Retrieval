# Truy xuất tài liệu khi truy vấn có lỗi chính tả

Đồ án so sánh VSM TF-IDF + cosine và Okapi BM25 trên BEIR SciFact. Mỗi mô hình dùng hai biểu diễn, word unigram và character n-gram 3–5. Corpus có 5.183 tài liệu, 809 truy vấn train và 300 truy vấn test. [Báo cáo](report/report.md) · [Kết quả từng lượt](results/p14-scifact-20261125/summary.csv) · [Bảng, hình và phân tích](results/p15-scifact-20261125/analysis.md)

## 1. Cài đặt

Chạy các lệnh từ thư mục gốc dự án. Ví dụ dưới đây dùng PowerShell. Phiên bản Python đã kiểm chứng là **3.12.10**. Các gói trực tiếp được pin trong [requirements.txt](requirements.txt).

```powershell
py -3.12 --version
py -3.12 -m venv .venv
$py = '.\.venv\Scripts\python.exe'
& $py -m pip install -r requirements.txt
& $py -m pip check
& $py -m pytest -q
```

`$py` trỏ thẳng tới interpreter của dự án và có thể dùng trong cửa sổ PowerShell chưa kích hoạt venv. Nếu đã có `.venv`, dùng lại venv đó. Trên Linux/macOS, tạo bằng `python3.12 -m venv .venv` rồi dùng `./.venv/bin/python` thay cho `& $py`.

## 2. Chuẩn bị dữ liệu

Với dữ liệu chưa có sẵn, chọn một trong hai lệnh sau. Lệnh đầu tải ZIP chính thức từ BEIR. Lệnh thứ hai nhập một bản ZIP BEIR đã tải cục bộ.

```powershell
& $py -m src.data_loader
# Hoặc
& $py -m src.data_loader --archive 'C:\Downloads\scifact.zip'
```

Loader giữ nguyên ID, kiểm tra corpus, truy vấn, qrels và sự tách biệt giữa train/test. Tải trực tiếp kiểm tra checksum công bố bởi BEIR. Khi nhập ZIP cục bộ, manifest ghi SHA-256 và kết quả đối chiếu checksum BEIR. Kết quả P14 trong repo dùng bản phân phối BEIR trên Hugging Face, được tải bằng [download_scifact_hf.py](download_scifact_hf.py). Manifest dữ liệu ghi checksum của bốn tệp thực tế đã dùng. Chạy script Hugging Face trong bản sao dự án có thư mục dữ liệu mới vì script tự ghi vào `data/raw/scifact/`.

Nếu đã có dữ liệu, xác minh và tạo thống kê bằng lệnh sau.

```powershell
& $py -m src.dataset_stats
```

`--path` của loader và thống kê đổi thư mục dữ liệu mặc định `data/raw/scifact/`. `--output` của thống kê đổi thư mục xuất JSON và CSV, mặc định `data/processed/scifact/`. Các thư mục dữ liệu thô, dữ liệu xử lý và index nằm trong `.gitignore`. Nếu cần đúng bản dữ liệu P14, giữ cả corpus, truy vấn, qrels và manifest gốc cùng nhau.

## 3. Truy vấn thử và smoke test

Dùng thư mục index mới khi muốn chạy lại các lệnh build.

```powershell
& $py -m src.cli build-index --analyzer word --indexes indexes/demo
& $py -m src.cli build-index --analyzer char --indexes indexes/demo
& $py -m src.cli search --indexes indexes/demo --analyzer word --model bm25 --query 'vitamin reduces cancre risk' --top-k 5
& $py -m src.cli search --indexes indexes/demo --analyzer char --model vsm --query 'vitamin reduces cancre risk' --top-k 5
& $py -m src.cli generate-noise --split test --noise-type mixed --rate 0.2 --seed 42 --output data/processed/demo-noise
& $py -m pytest -q tests/test_integration.py
```

- `build-index` có `--data`, `--min-df` (mặc định 1) và `--max-df-ratio` (mặc định 1,0). Mỗi analyzer có `index.json`, thống kê và danh sách term.
- `search` đọc cùng `--indexes` và `--analyzer` đã build. CLI có `--k1` và `--b` cho BM25, mặc định 1,2 và 0,75. Có thể dùng `--output <file.json>` để lưu ranking vào tệp mới.
- `generate-noise` yêu cầu `--split train|test` và một trong `--rate` (từ 0 đến 1) hoặc `--fixed-k 1|2`. Các loại lỗi là deletion, insertion, substitution, transposition và mixed. Kết quả có JSONL và manifest.
- Smoke test dùng corpus toy. Nó chạy qua E0 và toàn bộ lịch E1–E4 để kiểm tra file xuất, truy vấn rỗng, bộ nhiễu dùng chung và baseline E4.

## 4. Tái lập thực nghiệm E0–E4

[configs/default.yaml](configs/default.yaml) định nghĩa M1 VSM word, M2 BM25 word, M3 VSM char và M4 BM25 char. E0 so sánh 20 ứng viên trên train sạch theo MAP. E2–E4 dùng seed 42–46. E4 dùng cùng tập truy vấn đủ hai token khả thi cho cả hai mức và tính baseline E1 theo đúng ID của tập đó. MAP dùng toàn bộ hit có điểm dương hữu hạn. Các metric phụ sử dụng cutoff 5 và 10.

Chọn tên thư mục chưa tồn tại cho mỗi đợt chạy. Lần chạy P14 lưu khoảng 18,55 GB ranking JSONL. Dung lượng này chưa gồm index, metric và các tệp tạm.

```powershell
$run = 'data/processed/reproduction'
& $py -m src.cli plan-experiments --config configs/default.yaml --output "$run/experiment_plan.json"
& $py -m src.cli tune --split train --config configs/default.yaml --output "$run/E0"
& $py -m src.cli experiment --split test --config configs/default.yaml --selected-config "$run/E0/selected_config.yaml" --output "$run/E1-E4"
```

Kiểm tra mã thoát của từng lệnh trước khi chuyển bước. `tune` tạo `tuning.csv`, index ứng viên và `selected_config.yaml`. `experiment` kiểm tra tính nhất quán của cấu hình, mã nguồn, dữ liệu train và index trước khi chạy test. Nếu nguồn hoặc giao thức thay đổi, tạo một lượt E0 mới cho phiên bản hiện tại.

| Vị trí trong `$run` | Nội dung |
|---|---|
| `E0/tuning.csv`, `E0/selected_config.yaml` | MAP train và tham số được chọn |
| `E0/indexes/` | Index, số liệu từ vựng, danh sách term word/char |
| `E1-E4/noise/` | 50 bộ truy vấn nhiễu với manifest |
| `E1-E4/runs/`, `E1-E4/manifests/` | 204 ranking JSONL và manifest chứa checksum |
| `E1-E4/metrics/summary.csv` | Một dòng cho mỗi lượt |
| `E1-E4/metrics/per_query.csv` | Metric, OOV và latency theo truy vấn |

Để chạy lại một nhóm, thêm `--groups E2`, `--groups E3` hoặc `--groups E4` vào lệnh `experiment` và chọn đầu ra riêng. Khi chạy nhóm nhiễu, runner tự chạy kèm E1 để lấy baseline. Runner hiện công bố đầu ra theo cả đợt và yêu cầu thư mục mới. Việc tự bỏ qua từng run đã hoàn tất trong một đợt chưa được hỗ trợ.

## 5. Tạo lại bảng, biểu đồ và phụ lục báo cáo

Các CSV và PNG nhỏ của P15 được lưu trong [results/p15-scifact-20261125](results/p15-scifact-20261125/analysis.md). Để tạo lại từ kết quả P14 đã lưu trên máy, dùng lệnh đầu. Để tạo từ đợt chạy mới ở bước 4, dùng lệnh thứ hai.

```powershell
& $py -m src.results_analysis --output results/p15-from-archive
# Hoặc phân tích một lượt đã chạy đủ E0–E4
& $py -m src.results_analysis --run $run --output results/p15-reproduction
```

`--run` mặc định trỏ tới `data/processed/p14-scifact-20261125`. Nếu dùng đường dẫn dữ liệu hoặc thống kê khác mặc định, truyền `--data` và `--dataset-stats`. Script xuất baseline, trung bình và độ lệch chuẩn qua seed, chi phí index, 5 biểu đồ PNG cùng 6 ca truy vấn ở CSV/JSON. Xem [báo cáo Markdown](report/report.md) bằng trình xem hỗ trợ Mermaid và công thức toán để đọc sơ đồ, công thức và hình. Các giá trị latency phản ánh máy và điều kiện chạy.

## 6. Xử lý lỗi thường gặp

| Triệu chứng | Cách kiểm tra hoặc xử lý |
|---|---|
| `py -3.12` không tìm thấy bản cài | Chạy trong tài khoản Windows đã cài Python 3.12, hoặc dùng `.\.venv\Scripts\python.exe` nếu venv có sẵn. |
| PowerShell chặn `Activate.ps1` | Chạy trực tiếp interpreter `.\.venv\Scripts\python.exe`. |
| Sandbox báo `WinError 10013` khi tải | Tải ZIP bằng phiên có mạng, rồi chạy `src.data_loader --archive <file>`. |
| Thư mục hoặc tệp kết quả đã tồn tại | Chọn `--output` hoặc `--indexes` mới. |
| Experiment từ chối checksum E0 | Kiểm tra đang dùng đúng code, cấu hình và dữ liệu của lượt tune. Khi đã thay đổi một trong các đầu vào, chạy tune lại ở thư mục mới. |
| Script phân tích báo thiếu ranking hoặc seed | Dùng đường dẫn đến đợt có đủ E0 và E1–E4. Bảng phân tích trường hợp đọc ranking cùng variant của bốn lượt đã chọn. |
| Chỉ thấy CSV, hình và báo cáo sau khi lấy mã nguồn | Các bản công bố nhỏ nằm dưới `results/`. Với dữ liệu và ranking đầy đủ, dùng artifact cục bộ của P14 hoặc chạy lại bước 2–5. |

Tiến độ, bằng chứng kiểm thử và các quyết định thực nghiệm được ghi trong [docs/PROGRESS.md](docs/PROGRESS.md).
