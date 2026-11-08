from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from safari_tabs import mcp
from safari_tabs.adapters import catalog, groups


class CatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "fixture.db"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE bookmarks (
                id INTEGER PRIMARY KEY,parent INTEGER,type INTEGER DEFAULT 1,title TEXT,url TEXT,
                order_index INTEGER DEFAULT 0,subtype INTEGER DEFAULT 0,hidden INTEGER DEFAULT 0,
                special_id INTEGER DEFAULT 0,external_uuid TEXT,deleted INTEGER DEFAULT 0,date_closed REAL
            )""")
            db.executemany("INSERT INTO bookmarks (id,parent,title,subtype,external_uuid) VALUES (?,?,?,?,?)", [
                (0,None,"Root",0,"root"), (10,0,"",2,"DefaultProfile"),
                (20,0,"Work",2,"profile-work"), (30,0,"Empty profile",2,"profile-empty"),
                (100,0,"Tools",0,"group-a"), (200,20,"Tools",0,"group-b"),
                (110,100,"Auxiliary",1,"auxiliary"), (300,None,"Recovered",0,"recovered"),
                (301,300,"Recovered group",0,"recovered-group"), (400,0,"Hidden",0,"hidden"),
                (500,0,"Closed",0,"closed"), (600,0,"Deleted profile",2,"deleted-profile"),
                (601,600,"Deleted ancestor",0,"deleted-descendant"),
                (700,701,"Cycle",0,"cycle-a"), (701,700,"Cycle",0,"cycle-b"),
                (900,None,"Local",0,"local"), (901,None,"Private",0,"private"),
                (2,None,"pinned",0,"pins"), (3,None,"privatePinned",0,"private-pins"),
            ])
            db.execute("UPDATE bookmarks SET hidden=1 WHERE id IN (300,400,900,901,2,3)")
            db.execute("UPDATE bookmarks SET special_id=6 WHERE id=300")
            db.execute("UPDATE bookmarks SET date_closed=123 WHERE id=500")
            db.execute("UPDATE bookmarks SET deleted=1 WHERE id=600")
            db.executemany("INSERT INTO bookmarks (id,parent,type,title,url,order_index) VALUES (?,?,0,?,?,?)", [
                (1000,100,"First group tab","https://example.test/a",1),
                (1001,110,"Auxiliary tab","https://example.test/aux",0),
                (2000,200,"Other profile tab","https://example.test/b",0),
                (3000,301,"Recovered tab","https://example.test/recovered",0),
                (5000,500,"Closed tab","https://example.test/closed",0),
                (9000,900,"Local tab","https://example.test/local",0),
                (9010,901,"Private tab","https://example.test/private",0),
                (20_000,2,"Pinned tab","https://example.test/pin",0),
                (30_000,3,"Private pinned tab","https://example.test/private-pin",0),
            ])
            db.execute("""CREATE TABLE windows (id INTEGER,uuid TEXT,active_tab_group_id INTEGER,
                active_profile_id INTEGER,private_tab_group_id INTEGER,date_closed REAL,is_last_session INTEGER)""")
            db.executemany("INSERT INTO windows VALUES (?,?,?,?,?,?,?)", [
                (5,"window-a",900,10,901,None,1), (6,"window-b",901,10,901,None,1),
                (7,"window-c",200,20,None,None,1), (8,"closed-window",900,10,901,123,1),
                (9,"missing-group",999,10,None,None,1),
            ])

    def test_named_groups_have_profiles_and_exclude_internal_records(self):
        snapshot = groups.read(self.path)
        self.assertEqual({scope.id for scope in snapshot.scopes}, {"100","200"})
        self.assertEqual({scope.profile_id for scope in snapshot.scopes}, {"10","20"})
        self.assertEqual({tab.id for tab in snapshot.tabs}, {"1000","1001","2000"})
        self.assertEqual(next(tab.group_id for tab in snapshot.tabs if tab.id == "1001"), "100")
        self.assertEqual(snapshot.context["default_profile_id"], "10")

    def test_profile_inventory_preserves_empty_profiles(self):
        snapshot = catalog.read_profiles(self.path)
        self.assertEqual({scope.id for scope in snapshot.scopes}, {"10","20","30"})
        self.assertEqual({(tab.scope_id,tab.group_id) for tab in snapshot.tabs}, {("10","100"),("20","200")})

    def test_start_pages_without_urls_remain_tabs(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany("INSERT INTO bookmarks (id,parent,type,title,url) VALUES (?,?,0,?,?)", [
                (1002,100,"Start Page",""), (1003,100,"Start Page",None),
            ])
        snapshot = groups.read(self.path)
        self.assertEqual([tab.title for tab in snapshot.tabs if tab.id in ("1002", "1003")],
                         ["Start Page", "Start Page"])

    def test_session_uses_stored_ids_and_explicit_group_profile_links(self):
        snapshot = catalog.read_session(self.path)
        self.assertEqual({scope.id for scope in snapshot.scopes}, {"5","6","7","9"})
        private = next(scope for scope in snapshot.scopes if scope.id == "6")
        self.assertTrue(private.is_private)
        self.assertEqual((private.group_id,private.profile_id,private.window_uuid), ("901","10","window-b"))
        self.assertEqual([tab.title for tab in snapshot.tabs if tab.scope_id == "5"], ["Pinned tab","Local tab"])
        self.assertEqual([tab.title for tab in snapshot.tabs if tab.scope_id == "6"], ["Private pinned tab","Private tab"])
        self.assertEqual(len([tab for tab in snapshot.tabs if tab.scope_id == "7"]), 1)
        self.assertTrue(any("previous session" in warning for warning in snapshot.warnings))

    def test_mcp_profile_filter_disambiguates_duplicate_group_names(self):
        with patch.dict(mcp.ADAPTERS, {"groups": lambda: groups.read(self.path)}):
            data = mcp.call_tool("read_safari_tabs", {"source":"groups", "scope_name":"Tools", "profile_id":"20"})
        self.assertEqual([tab["title"] for tab in data["tabs"]], ["Other profile tab"])
        self.assertEqual(data["tabs"][0]["profile_name"], "Work")
        self.assertNotIn("url", data["tabs"][0])
        json.dumps(data)
