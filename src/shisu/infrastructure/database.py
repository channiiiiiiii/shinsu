"""두 사람의 저장·중복 요청·세션을 SQLite로 관리한다."""
import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from shisu.application.game import act, migrate, new_save


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS players (id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS requests (user_id TEXT, key TEXT, body TEXT, response TEXT,
                    PRIMARY KEY(user_id,key));
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def load(self, db, user):
        row = db.execute("SELECT data FROM players WHERE id=?", (user,)).fetchone()
        if row:
            return migrate(json.loads(row[0]))
        data = new_save()
        db.execute("INSERT INTO players VALUES (?,?)", (user, json.dumps(data, ensure_ascii=False)))
        return data

    def get(self, user):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self.load(db, user)

    def action(self, user, key, command):
        body = json.dumps(command, sort_keys=True)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body,response FROM requests WHERE user_id=? AND key=?", (user,key)).fetchone()
            if row:
                if body != row[0]:
                    raise ValueError("같은 요청 번호로 다른 행동을 보낼 수 없습니다.")
                return json.loads(row[1])
            data, message = act(self.load(db,user), command)
            result = {"data": data, "message": message}
            db.execute("UPDATE players SET data=? WHERE id=?", (json.dumps(data,ensure_ascii=False),user))
            db.execute("INSERT INTO requests VALUES (?,?,?,?)", (user,key,body,json.dumps(result,ensure_ascii=False)))
            return result

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def session(self, user):
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (self.digest(token),user,time.time()+604800))
        return token

    def user(self, token):
        with self.connect() as db:
            row = db.execute("SELECT user_id FROM sessions WHERE hash=? AND expires>?", (self.digest(token),time.time())).fetchone()
        return row[0] if row else None

    def logout(self, token):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE hash=?", (self.digest(token),))

    def backup(self, path):
        with self.connect() as source:
            target = sqlite3.connect(path)
            try:
                source.backup(target)
            finally:
                target.close()
