from pathlib import Path
import sqlite3
import tempfile
import unittest

from safari_tabs.database import inspect_schema, open_database
from safari_tabs.model import QueryError


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "tabs ? # ü.db"

    def test_missing_database_is_not_created(self):
        with self.assertRaises(QueryError):
            with open_database(self.path):
                pass
        self.assertFalse(self.path.exists())

    def test_reads_wal_and_rejects_writes(self):
        writer = sqlite3.connect(self.path)
        self.addCleanup(writer.close)
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute("CREATE TABLE example (value TEXT)")
        writer.execute("INSERT INTO example VALUES ('committed in WAL')")
        writer.commit()
        self.assertTrue(Path(str(self.path) + "-wal").is_file())
        with open_database(self.path) as reader:
            self.assertEqual(reader.execute("SELECT value FROM example").fetchone()[0], "committed in WAL")
            with self.assertRaises(sqlite3.OperationalError):
                reader.execute("DELETE FROM example")
            writer.execute("INSERT INTO example VALUES ('newer transaction')")
            writer.commit()
            self.assertEqual(reader.execute("SELECT COUNT(*) FROM example").fetchone()[0], 1)
        self.assertEqual(writer.execute("SELECT COUNT(*) FROM example").fetchone()[0], 2)

    def test_schema_excludes_record_contents(self):
        with sqlite3.connect(self.path) as connection:
            connection.execute("CREATE TABLE example (title TEXT)")
            connection.execute("INSERT INTO example VALUES ('PRIVATE TITLE')")
        result = inspect_schema("groups", self.path)
        self.assertNotIn("PRIVATE TITLE", str(result))
        self.assertEqual(result["tables"][0]["name"], "example")

    def test_invalid_database_has_readable_error(self):
        self.path.write_text("not sqlite")
        with self.assertRaisesRegex(QueryError, "Cannot read"):
            inspect_schema("groups", self.path)
