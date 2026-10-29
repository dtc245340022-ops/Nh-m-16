import argparse
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path


def _check_integrity(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy database: {path}")
    with closing(sqlite3.connect(path)) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise ValueError(f"Database không hợp lệ: {result}")


def backup_database(source: Path, destination: Path) -> Path:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if source == destination:
        raise ValueError("File nguồn và file backup phải khác nhau.")
    _check_integrity(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb"):
        pass
    try:
        with (
            closing(sqlite3.connect(source)) as source_db,
            closing(sqlite3.connect(destination)) as backup_db,
        ):
            source_db.backup(backup_db)
        _check_integrity(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def restore_database(
    source: Path, destination: Path, *, replace_existing: bool = False
) -> Path | None:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if source == destination:
        raise ValueError("File backup và database đích phải khác nhau.")
    _check_integrity(source)
    destination.parent.mkdir(parents=True, exist_ok=True)

    preserved = None
    if destination.exists():
        if not replace_existing:
            raise FileExistsError(
                f"Database đích đã tồn tại; dùng --replace để xác nhận thay thế: {destination}"
            )
        preserved = destination.with_name(
            f"{destination.stem}_before_restore_{time.time_ns()}{destination.suffix}"
        )
        backup_database(destination, preserved)
    else:
        with destination.open("xb"):
            pass

    try:
        with (
            closing(sqlite3.connect(source)) as backup_db,
            closing(sqlite3.connect(destination)) as destination_db,
        ):
            backup_db.backup(destination_db)
        _check_integrity(destination)
    except Exception:
        if preserved is None:
            destination.unlink(missing_ok=True)
        else:
            with (
                closing(sqlite3.connect(preserved)) as previous_db,
                closing(sqlite3.connect(destination)) as destination_db,
            ):
                previous_db.backup(destination_db)
        raise
    return preserved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tạo backup SQLite hoặc khôi phục từ backup đã xác minh."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    backup_parser = commands.add_parser("backup", help="Tạo snapshot SQLite mới.")
    backup_parser.add_argument("source", type=Path)
    backup_parser.add_argument("destination", type=Path)

    restore_parser = commands.add_parser(
        "restore", help="Khôi phục vào file mới hoặc thay thế có backup dự phòng."
    )
    restore_parser.add_argument("source", type=Path)
    restore_parser.add_argument("destination", type=Path)
    restore_parser.add_argument(
        "--replace",
        action="store_true",
        help="Cho phép thay database đích sau khi tạo snapshot dự phòng.",
    )

    args = parser.parse_args()
    try:
        if args.command == "backup":
            result = backup_database(args.source, args.destination)
            print(f"Đã tạo và kiểm tra backup: {result}")
        else:
            preserved = restore_database(
                args.source, args.destination, replace_existing=args.replace
            )
            print(f"Đã khôi phục và kiểm tra database: {args.destination.resolve()}")
            if preserved is not None:
                print(f"Database trước khi khôi phục được giữ tại: {preserved}")
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"Thao tác SQLite thất bại: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
