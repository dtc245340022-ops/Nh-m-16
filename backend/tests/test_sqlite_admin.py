import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlite_admin import backup_database, restore_database


class SQLiteAdminTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_database(self, path: Path, value: str) -> None:
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
            connection.execute("INSERT INTO sample (value) VALUES (?)", (value,))
            connection.commit()

    def _read_value(self, path: Path) -> str:
        with closing(sqlite3.connect(path)) as connection:
            return connection.execute("SELECT value FROM sample").fetchone()[0]

    def test_backup_creates_verified_snapshot_without_changing_source(self):
        source = self.directory / "source.db"
        backup = self.directory / "backups" / "snapshot.db"
        self._create_database(source, "source")

        self.assertEqual(backup_database(source, backup), backup.resolve())
        self.assertEqual(self._read_value(source), "source")
        self.assertEqual(self._read_value(backup), "source")

    def test_restore_to_new_path_does_not_replace_source(self):
        backup = self.directory / "backup.db"
        restored = self.directory / "restored.db"
        self._create_database(backup, "backup")

        self.assertIsNone(restore_database(backup, restored))
        self.assertEqual(self._read_value(backup), "backup")
        self.assertEqual(self._read_value(restored), "backup")

    def test_restore_refuses_existing_destination_without_replace_flag(self):
        backup = self.directory / "backup.db"
        destination = self.directory / "live.db"
        self._create_database(backup, "backup")
        self._create_database(destination, "live")

        with self.assertRaises(FileExistsError):
            restore_database(backup, destination)
        self.assertEqual(self._read_value(destination), "live")

    def test_replace_preserves_previous_database_before_restoring(self):
        backup = self.directory / "backup.db"
        destination = self.directory / "live.db"
        self._create_database(backup, "backup")
        self._create_database(destination, "live")

        preserved = restore_database(backup, destination, replace_existing=True)

        self.assertIsNotNone(preserved)
        self.assertEqual(self._read_value(destination), "backup")
        self.assertEqual(self._read_value(preserved), "live")


if __name__ == "__main__":
    unittest.main()
