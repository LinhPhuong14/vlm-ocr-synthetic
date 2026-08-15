# Chạy trên Windows

Repo chạy được trên Windows mà không cần WSL. Không có `make` thì dùng
`tasks.py` — **mọi task đều định nghĩa ở đó**, còn `Makefile` chỉ là lớp gọi
mỏng. `make dataset` và `python tasks.py dataset` là một.

```powershell
py -3.11 tasks.py setup
py tasks.py dataset
py tasks.py proof --dataset data\dataset60
py tasks.py                       # liệt kê task
```

Bảng đối chiếu:

| Linux / macOS | Windows |
| --- | --- |
| `make setup` | `py -3.11 tasks.py setup` |
| `make dataset N=5` | `py tasks.py dataset -n 5` |
| `make dataset DATASET=/tmp/thu` | `py tasks.py dataset -o C:\tmp\thu` |
| `make proof DATASET=…` | `py tasks.py proof --dataset …` |
| `make preview-grid LAYOUT=x` | `py tasks.py preview-grid --layout x` |
| `make check lint check-rules` | `py tasks.py check` … (một task một lần) |

---

## 1. Python 3.11 cho renderer glyph

Bắt buộc. synthtiger ghim `pillow<10`, `numpy<2`, `opencv-python<5`, và
**Python 3.12+ không thoả được** — xem [python-versions.md](python-versions.md).

```powershell
winget install Python.Python.3.11
py -0                      # kiểm tra đã thấy 3.11
py -3.11 tasks.py setup-synthdog
```

`tasks.py setup-synthdog` **tự chặn** nếu bạn chạy bằng 3.12+ và in ra đúng
lệnh cần gõ, thay vì để pip nổ giữa chừng với một thông báo khó hiểu.

Hai renderer kia không kén, `py tasks.py setup-html` và `setup-genalog` chạy
bằng Python nào cũng được (3.9+).

## 2. Trình duyệt cho renderer HTML

Trong container Linux của repo đã có sẵn bản build ở `/opt/pw-browsers`, nên
`find_chromium()` trong `generators/html/render.py` trả về đường dẫn đó và
**không được** chạy `playwright install`. Trên Windows không có gì ở đó,
`find_chromium()` trả `None`, và Playwright tự lo — nhưng phải tải một lần:

```powershell
py tasks.py setup-html          # đã tự chạy `playwright install chromium`
```

## 3. GTK cho renderer genalog

WeasyPrint cần Pango và cairo. Trên Linux là gói hệ thống; trên Windows phải
cài **GTK3 runtime**:

- Tải [tirl/gtk-for-windows-runtime-environment-installer](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases)
- Cài xong **mở lại terminal** để `PATH` cập nhật.

Kiểm tra:

```powershell
generators\genalog\.venv\Scripts\python -c "import weasyprint; print('ok')"
```

Báo lỗi `cannot load library 'libgobject-2.0-0'` nghĩa là GTK chưa có trên
`PATH`. Đây là yêu cầu của WeasyPrint chứ không phải của repo — xem
[tài liệu WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows).

## 4. Tesseract cho `proof`

```powershell
winget install UB-Mannheim.TesseractOCR
```

Chọn **Vietnamese** trong phần language data lúc cài, và thêm thư mục cài đặt
vào `PATH` (mặc định `C:\Program Files\Tesseract-OCR`).

```powershell
tesseract --list-langs      # phải thấy `vie`
```

Không có Tesseract thì chỉ `proof` không chạy; sinh dữ liệu vẫn bình thường.

---

## Những chỗ đã sửa để chạy được trên Windows

Ghi lại để người sau không vô tình phá:

**Đường dẫn tới interpreter của venv.** `bin/python` trên POSIX,
`Scripts\python.exe` trên Windows. `tools/paths.py::venv_python` giải quyết
chỗ này, và nó **dò trên đĩa** chứ không hỏi hệ điều hành đang chạy — vì bạn có
thể soi repo từ WSL trong khi venv do Python bản Windows tạo ra. `BACKENDS`
trong `tools/generate_dataset.py` dùng hàm đó, trước đây nó hardcode
`.venv/bin/python`.

**`make check` cũ dùng `git ls-files | xargs`** — `cmd.exe` không có `xargs`.
Giờ là `tasks.py::check`, gọi `git ls-files` bằng `subprocess` rồi
`compileall.compile_file`.

**`make clean` cũ dùng `rm -rf` và `**/__pycache__`.** Giờ là `shutil.rmtree`,
và **bỏ qua `.git`, `.venv`, `node_modules`** — bản đầu tiên viết bằng
`rglob("__pycache__")` đã chui vào cả virtualenv mà xoá cache của
site-packages.

**Xuống dòng.** `.gitattributes` đặt `* text=auto eol=lf` và đánh dấu ảnh/font
là `binary`. Không có nó, một lần commit từ Windows có thể đưa CRLF vào file
YAML hoặc corpus — **không thấy được trong diff**, mà phía Linux đọc ra chuỗi
có `\r` ở cuối.

**Không có đường dẫn tuyệt đối kiểu POSIX trong code.** Mọi thứ đi qua
`pathlib`. Ngoại lệ duy nhất là danh sách `CHROMIUM_CANDIDATES` — chỉ là các
đường dẫn *ứng viên*, không tồn tại thì bỏ qua.

## Còn hạn chế gì trên Windows

- Chưa chạy CI trên Windows, nên đây là "thiết kế để chạy được" chứ chưa phải
  "đã kiểm chứng từng bản Windows". Gặp lỗi thì mở issue kèm output của
  `py tasks.py check`.
- Đường dẫn dài: bật `git config --system core.longpaths true` nếu clone vào
  thư mục sâu.
- `py tasks.py setup` gọi cả ba; muốn bỏ genalog (để khỏi cài GTK) thì chạy
  riêng `setup-synthdog` và `setup-html`, rồi
  `py tasks.py dataset` với `--frameworks synthdog html` qua
  `tools\generate_dataset.py`.
