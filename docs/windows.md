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

## 0. `CERTIFICATE_VERIFY_FAILED` khi pip chạy

Gặp cái này ngay ở bước `setup`, lặp 5 lần rồi bỏ cuộc:

```
SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED]
certificate verify failed: unable to get local issuer certificate'))
```

**Không phải lỗi repo.** Có thứ gì đó nằm giữa máy bạn và `pypi.org` đang ký
lại TLS bằng một certificate mà Python không tin — gần như luôn là proxy soi
gói của công ty. Trình duyệt vào PyPI được vì **Windows** tin CA nội bộ đó;
Python mang kho tin cậy riêng (`certifi`) và không tin.

Vì `setup` dựng ba môi trường, cách sửa phải áp cho **mọi** venv về sau, chứ
không phải gõ cờ cho từng lệnh.

### Cách 1 — cho Python dùng luôn kho tin cậy của Windows (khuyên dùng)

```powershell
py -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org pip_system_certs
```

Cài một lần vào Python gốc. Từ đó mọi tiến trình Python đọc CA từ Windows
certificate store, nên CA nội bộ công ty được nhận tự động — kể cả trong các
venv mà `tasks.py` tạo ra sau này. Đây là cách duy nhất ở đây **không** tắt
xác thực: bạn vẫn kiểm chứng certificate, chỉ là kiểm theo danh sách CA mà
IT công ty đã cài vào máy.

Riêng lệnh cài `pip_system_certs` vẫn phải dùng `--trusted-host` vì lúc đó
chưa có gì sửa được — đó là bài toán con gà quả trứng.

### Cách 2 — trỏ pip vào file CA của công ty

Xin IT file CA gốc (`.pem`/`.crt`), hoặc tự xuất: mở `https://pypi.org` bằng
Edge → bấm ổ khoá → **Connection is secure** → xem certificate → tab
**Certification Path** → chọn certificate **trên cùng** → Export → chọn
**Base-64 encoded X.509 (.CER)**.

Rồi ghi vào `%APPDATA%\pip\pip.ini` để áp cho mọi venv:

```ini
[global]
cert = C:\Users\<ban>\certs\corp-root-ca.pem
```

Cũng vẫn là xác thực đầy đủ. Nhiều thư viện Python khác đọc biến môi trường
thay vì `pip.ini`, nên đặt thêm cho chắc:

```powershell
setx SSL_CERT_FILE     C:\Users\<ban>\certs\corp-root-ca.pem
setx REQUESTS_CA_BUNDLE C:\Users\<ban>\certs\corp-root-ca.pem
```

### Cách 3 — bỏ qua xác thực cho riêng PyPI (biết rõ đánh đổi rồi hãy dùng)

`%APPDATA%\pip\pip.ini`:

```ini
[global]
trusted-host = pypi.org
               files.pythonhosted.org
```

Chạy được ngay, và pip vẫn kiểm hash gói theo lockfile của chính nó. Nhưng bạn
**mất khả năng phát hiện** nếu có ai đó đứng giữa đổi nội dung gói tải về. Chỉ
nên dùng khi cách 1 và 2 đều tắc, và chỉ trên máy công ty đã có proxy tin cậy.

> Đừng đặt `PYTHONHTTPSVERIFY=0` hay sửa `certifi/cacert.pem` bằng tay. Cái đầu
> tắt xác thực cho **mọi** kết nối HTTPS của Python trên máy, cái sau bị ghi đè
> lần tới `certifi` cập nhật.

### Playwright cũng đi qua proxy đó

`py tasks.py setup-html` gọi `playwright install chromium`, tải từ host khác
PyPI và dùng TLS của Node, nên nó **không** đọc `pip.ini`:

```powershell
setx NODE_EXTRA_CA_CERTS C:\Users\<ban>\certs\corp-root-ca.pem
```

Mở lại terminal rồi chạy lại `setup-html`.

### Sau khi sửa

Xoá các venv dở dang rồi làm lại từ đầu — chúng đang rỗng hoặc thiếu gói:

```powershell
Remove-Item -Recurse -Force generators\*\.venv
py -3.11 tasks.py setup
```

Kiểm tra nhanh trước khi chạy lại cả `setup`:

```powershell
py -m pip download --no-deps -d $env:TEMP\piptest pip
```

Lệnh này chạy trót lọt thì `setup` cũng sẽ trót lọt.

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
