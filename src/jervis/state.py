from __future__ import annotations
import json,sqlite3,time
from pathlib import Path
from threading import RLock

SCHEMA="""
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE COLLATE NOCASE,honorific TEXT CHECK(honorific IN ('sir','maam') OR honorific IS NULL),role TEXT NOT NULL DEFAULT 'known',created_at REAL NOT NULL,last_seen REAL);
CREATE TABLE IF NOT EXISTS speaker_embeddings(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,embedding TEXT NOT NULL,quality REAL NOT NULL DEFAULT 1.0,created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_embeddings_user ON speaker_embeddings(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS dialogue(id INTEGER PRIMARY KEY AUTOINCREMENT,ts REAL NOT NULL,user_id TEXT,role TEXT NOT NULL,text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,ts REAL NOT NULL,kind TEXT NOT NULL,detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY,value TEXT NOT NULL);
"""

class State:
    def __init__(self,path:Path,max_dialogue=2000,max_events=5000):
        path.parent.mkdir(parents=True,exist_ok=True)
        self.max_dialogue=int(max_dialogue);self.max_events=int(max_events);self._lock=RLock()
        self._db=sqlite3.connect(path,check_same_thread=False);self._db.row_factory=sqlite3.Row
        self._db.executescript(SCHEMA);self._db.commit()
    def close(self):
        with self._lock:self._db.close()
    def event(self,kind,detail=""):
        with self._lock:
            self._db.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)",(time.time(),kind,str(detail)[:4000]))
            self._db.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT ?)",(self.max_events,));self._db.commit()
    def dialogue(self,role,text,user_id=None):
        with self._lock:
            self._db.execute("INSERT INTO dialogue(ts,user_id,role,text) VALUES(?,?,?,?)",(time.time(),user_id,role,str(text)[:12000]))
            self._db.execute("DELETE FROM dialogue WHERE id NOT IN (SELECT id FROM dialogue ORDER BY id DESC LIMIT ?)",(self.max_dialogue,));self._db.commit()
    def set_kv(self,key,value):
        with self._lock:
            self._db.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,json.dumps(value)));self._db.commit()
    def get_kv(self,key,default=None):
        with self._lock:row=self._db.execute("SELECT value FROM kv WHERE key=?",(key,)).fetchone()
        return default if row is None else json.loads(row["value"])
    def user(self,user_id):
        with self._lock:return self._db.execute("SELECT * FROM users WHERE id=?",(user_id,)).fetchone()
    def user_by_name(self,name):
        with self._lock:return self._db.execute("SELECT * FROM users WHERE name=? COLLATE NOCASE",(name,)).fetchone()
    def users(self):
        with self._lock:return list(self._db.execute("SELECT * FROM users ORDER BY name"))
    def upsert_user(self,user_id,name,honorific=None,role="known"):
        if honorific not in {None,"sir","maam"}:raise ValueError("invalid honorific")
        now=time.time()
        with self._lock:
            self._db.execute("""INSERT INTO users(id,name,honorific,role,created_at,last_seen) VALUES(?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET name=excluded.name,honorific=COALESCE(excluded.honorific,users.honorific),role=excluded.role,last_seen=excluded.last_seen""",(user_id,name.strip(),honorific,role,now,now));self._db.commit()
    def touch_user(self,user_id):
        with self._lock:self._db.execute("UPDATE users SET last_seen=? WHERE id=?",(time.time(),user_id));self._db.commit()
    def add_embedding(self,user_id,embedding,quality,limit):
        with self._lock:
            self._db.execute("INSERT INTO speaker_embeddings(user_id,embedding,quality,created_at) VALUES(?,?,?,?)",(user_id,json.dumps(embedding),float(quality),time.time()))
            self._db.execute("DELETE FROM speaker_embeddings WHERE user_id=? AND id NOT IN (SELECT id FROM speaker_embeddings WHERE user_id=? ORDER BY quality DESC,created_at DESC LIMIT ?)",(user_id,user_id,int(limit)));self._db.commit()
    def embeddings(self):
        with self._lock:rows=list(self._db.execute("SELECT user_id,embedding FROM speaker_embeddings ORDER BY user_id,quality DESC"))
        out={}
        for row in rows:out.setdefault(row["user_id"],[]).append(json.loads(row["embedding"]))
        return out
