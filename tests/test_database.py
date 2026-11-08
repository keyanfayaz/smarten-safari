from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from safari_tabs.database import database_path, inspect_schema, open_database
from safari_tabs.model import QueryError


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "tabs ? # ü.db"

    def test_missing_database_is_not_created(self):
        with self.assertRaises(QueryError) as caught:
            with open_database(self.path):
                pass
        self.assertEqual(caught.exception.code, "database_missing")
        self.assertFalse(self.path.exists())

    def test_permission_denial_is_distinct_from_absent_database(self):
        with patch.object(Path, "open", side_effect=PermissionError(1, "Operation not permitted")):
            with self.assertRaises(QueryError) as caught:
                with open_database(self.path):
                    self.fail("Reader must not continue after denied access")
        self.assertEqual(caught.exception.code, "permission_denied")

    def test_discovery_does_not_hide_stat_permission_errors(self):
        with patch.object(Path, "stat", side_effect=PermissionError(1, "Operation not permitted")):
            with self.assertRaises(QueryError) as caught:
                database_path("groups")
        self.assertEqual(caught.exception.code, "permission_denied")

    def test_unsupported_schema_has_distinct_code(self):
        from safari_tabs.adapters import icloud

        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE unrelated (value TEXT)")
        with self.assertRaises(QueryError) as caught:
            icloud.read(self.path)
        self.assertEqual(caught.exception.code, "unsupported_schema")

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
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE example (title TEXT)")
            connection.execute("INSERT INTO example VALUES ('PRIVATE TITLE')")
        result = inspect_schema("groups", self.path)
        self.assertNotIn("PRIVATE TITLE", str(result))
        self.assertEqual(result["tables"][0]["name"], "example")

    def test_invalid_database_has_readable_error(self):
        self.path.write_text("not sqlite")
        with self.assertRaisesRegex(QueryError, "Cannot read"):
            inspect_schema("groups", self.path)
