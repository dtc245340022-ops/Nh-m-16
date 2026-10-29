# Hệ thống quản lý hội nghị khoa học có tích hợp AI

Ứng dụng quản lý hội nghị khoa học với Backend FastAPI, giao diện React + Vite,
cơ sở dữ liệu SQLite và các chức năng AI sử dụng Gemini API.

## Chức năng chính

- Đăng nhập bằng JWT và phân quyền theo vai trò.
- Quản lý hội nghị, bài báo và tác giả.
- Quản lý hồ sơ phản biện, phân công và đánh giá.
- Quản lý phiên trình bày, đăng ký tham dự và thống kê.
- AI tóm tắt bài báo và gợi ý phản biện từ danh sách ứng viên trong hệ thống.
- API tài liệu hóa bằng Swagger UI tại `/docs`.

## Công nghệ và yêu cầu

- Windows 10/11.
- Python 3.14 (phiên bản đã dùng để kiểm thử dự án).
- Node.js 22.12 trở lên và npm (khuyến nghị Node.js 22 LTS).
- Gemini API key chỉ cần thiết nếu muốn sử dụng chức năng AI. Các API quản lý
  thông thường không cần gọi Gemini.

Cài Python từ [python.org/downloads](https://www.python.org/downloads/) và
Node.js từ [nodejs.org](https://nodejs.org/) (chọn bản 22 LTS). Sau khi cài, mở
một cửa sổ PowerShell mới và kiểm tra:

```powershell
py -3.14 --version
node --version
npm --version
```

## Cài đặt lần đầu

Mở PowerShell tại thư mục dự án:

```powershell
cd C:\HeThongQuanLyHoiNghiAI
```

### 1. Cài đặt Backend

Cài Python 3.14, sau đó tạo môi trường ảo và cài thư viện:

```powershell
cd C:\HeThongQuanLyHoiNghiAI\backend
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Tạo file cấu hình riêng từ mẫu. Lệnh sau không ghi đè `.env` nếu file đã tồn tại:

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

Mở `backend\.env` và cấu hình `JWT_SECRET_KEY` bằng giá trị ngẫu nhiên dài tối
thiểu 32 ký tự. Có thể tạo giá trị ngẫu nhiên bằng:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Không đưa giá trị secret hoặc `GEMINI_API_KEY` vào README, mã nguồn, ảnh chụp
màn hình hay GitHub. `GEMINI_API_KEY` có thể để trống nếu chưa dùng AI. Không
chia sẻ file `.env`.

### 2. Khởi tạo SQLite và dữ liệu mẫu

```powershell
.\.venv\Scripts\python.exe .\init_db.py
```

Cơ sở dữ liệu được lưu tại `backend\conference.db`. Script dùng
`Base.metadata.create_all()` và thêm dữ liệu mẫu khi chưa có; không xóa bảng,
không thay mật khẩu người dùng đã tồn tại. Trước khi chạy lại trên một database
đang sử dụng, hãy tạo bản sao lưu theo mục **Sao lưu và khôi phục SQLite**.

### 3. Cài đặt Frontend

Mở một cửa sổ PowerShell khác:

```powershell
cd C:\HeThongQuanLyHoiNghiAI\frontend
npm ci
```

## Khởi động ứng dụng

Khởi động Backend trong cửa sổ PowerShell thứ nhất:

```powershell
cd C:\HeThongQuanLyHoiNghiAI\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

- API: <http://127.0.0.1:8001>
- Kiểm tra trạng thái: <http://127.0.0.1:8001/api/health>
- Swagger UI: <http://127.0.0.1:8001/docs>

Khởi động Frontend trong cửa sổ PowerShell thứ hai:

```powershell
cd C:\HeThongQuanLyHoiNghiAI\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Mở <http://127.0.0.1:5173>. Vite chuyển tiếp các đường dẫn `/api` tới
`http://127.0.0.1:8001` theo cấu hình trong `frontend\vite.config.js`.

## Tài khoản và dữ liệu mẫu

`backend\init_db.py` tạo các tài khoản mẫu nếu email tương ứng chưa có:

| Email | Vai trò |
|---|---|
| `organizer@example.com` | Ban tổ chức |
| `author@example.com` | Tác giả |
| `reviewer@example.com` | Phản biện |

Mật khẩu không được ghi trong tài liệu này. Hãy lấy thông tin đăng nhập qua kênh
phân phối an toàn dành cho buổi trình diễn; không dùng các tài khoản mẫu cho môi
trường có dữ liệu thật.

Dữ liệu mẫu gồm hội nghị “Hội nghị Khoa học Công nghệ 2027”, phiên trình bày về
trí tuệ nhân tạo, một bài báo ứng dụng học máy, hồ sơ và đánh giá phản biện, đăng
ký tham dự và thông báo mẫu. Việc khởi tạo có tính lặp an toàn đối với các bản
ghi mẫu đã tồn tại.

## Kiểm thử và kiểm tra chất lượng

Các lệnh Backend dùng SQLite tạm của bộ test, không cần xóa hoặc tạo lại
`backend\conference.db`:

```powershell
cd C:\HeThongQuanLyHoiNghiAI\backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kiểm tra lint Frontend:

```powershell
cd C:\HeThongQuanLyHoiNghiAI\frontend
npm run lint
```

Build Frontend:

```powershell
cd C:\HeThongQuanLyHoiNghiAI\frontend
npm run build
```

## Sao lưu và khôi phục SQLite

### Tạo bản sao lưu

Đóng gói bằng SQLite backup API để tạo snapshot nhất quán. Ví dụ dưới đây tạo
tên file mới theo thời gian và dừng nếu file đích đã tồn tại:

```powershell
cd C:\HeThongQuanLyHoiNghiAI
$backup = "backups\conference_$(Get-Date -Format yyyyMMdd_HHmmss).db"
New-Item -ItemType Directory -Force backups | Out-Null
@'
import sqlite3
import sys
from pathlib import Path
from contextlib import closing

source_path = Path(sys.argv[1]).resolve()
backup_path = Path(sys.argv[2]).resolve()
if not source_path.is_file():
    raise SystemExit(f"Không tìm thấy database nguồn: {source_path}")
backup_path.parent.mkdir(parents=True, exist_ok=True)
with backup_path.open("xb"):
    pass
with (
    closing(sqlite3.connect(source_path)) as source,
    closing(sqlite3.connect(backup_path)) as backup,
):
    source.backup(backup)
    result = backup.execute("PRAGMA integrity_check").fetchone()[0]
if result != "ok":
    raise SystemExit(f"Bản sao lưu không hợp lệ: {result}")
print(f"Đã tạo và kiểm tra bản sao lưu: {backup_path}")
'@ | .\backend\.venv\Scripts\python.exe - backend\conference.db $backup
```

Giữ bản sao lưu ở nơi an toàn, giới hạn quyền truy cập và không đưa nó lên GitHub.
`.gitignore` loại trừ thư mục `backups`.

### Kiểm tra khôi phục vào một file riêng

Khôi phục thử nghiệm vào một file mới, không ghi đè database đang dùng. Chọn
đúng đường dẫn backup ở lệnh đầu; lệnh Python sẽ báo lỗi nếu file đích đã tồn tại.

```powershell
cd C:\HeThongQuanLyHoiNghiAI
$backup = "backups\conference_YYYYMMDD_HHMMSS.db"
$restore = "backend\conference_restore_validation.db"
@'
import sqlite3
import sys
from pathlib import Path
from contextlib import closing

backup_path = Path(sys.argv[1]).resolve()
restore_path = Path(sys.argv[2]).resolve()
if not backup_path.is_file():
    raise SystemExit(f"Không tìm thấy bản sao lưu: {backup_path}")
with closing(sqlite3.connect(backup_path)) as backup:
    result = backup.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"Bản sao lưu không hợp lệ: {result}")
with restore_path.open("xb"):
    pass
with (
    closing(sqlite3.connect(backup_path)) as backup,
    closing(sqlite3.connect(restore_path)) as restored,
):
    backup.backup(restored)
    result = restored.execute("PRAGMA integrity_check").fetchone()[0]
if result != "ok":
    raise SystemExit(f"Bản khôi phục không hợp lệ: {result}")
print(f"Khôi phục thử nghiệm thành công, database gốc không bị thay đổi: {restore_path}")
'@ | .\backend\.venv\Scripts\python.exe - $backup $restore
```

Lệnh trên chỉ tạo bản khôi phục kiểm tra; ứng dụng hiện được cấu hình cố định
dùng `backend\conference.db`. Không đổi tên hoặc chép đè file này để khôi phục
khi backend còn chạy. Nếu cần phục hồi môi trường đang sử dụng, hãy dừng backend,
tạo thêm một bản sao lưu database hiện tại, kiểm tra bản khôi phục ở đường dẫn
riêng trước, rồi thực hiện thay thế thủ công theo quy trình được người quản trị
phê duyệt.

## Git và tệp không được chia sẻ

`.gitignore` loại trừ cấu hình bí mật `.env`, database `conference.db`, các file
WAL/SHM, bản sao lưu, môi trường Python `.venv`, `node_modules`, cache Python và
thư mục build Frontend. Chỉ commit `.env.example` với giá trị mẫu không bí mật.
