"""두 사람의 저장·중복 요청·세션을 SQLite로 관리한다."""
import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from shisu.application.game import act, migrate, new_save, objects
from shisu.domain.combat import battle, check_entry


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
                CREATE TABLE IF NOT EXISTS raids (id TEXT PRIMARY KEY, host TEXT NOT NULL,
                    boss INTEGER NOT NULL, tier INTEGER NOT NULL, status TEXT NOT NULL,
                    created REAL NOT NULL, result TEXT);
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
            if command["action"].startswith("raid_"):
                result = self.raid_action(db, user, command)
                db.execute("INSERT INTO requests VALUES (?,?,?,?)", (user,key,body,json.dumps(result,ensure_ascii=False)))
                return result
            data, message = act(self.load(db,user), command)
            result = {"data": data, "message": message}
            db.execute("UPDATE players SET data=? WHERE id=?", (json.dumps(data,ensure_ascii=False),user))
            db.execute("INSERT INTO requests VALUES (?,?,?,?)", (user,key,body,json.dumps(result,ensure_ascii=False)))
            return result

    def raid_rooms(self):
        with self.connect() as db:
            rows = db.execute("SELECT id,host,boss,tier,status,created,result FROM raids WHERE created>? ORDER BY created DESC LIMIT 20", (time.time()-86400,)).fetchall()
        return [dict(zip(("id", "host", "boss", "tier", "status", "created", "result"), row)) for row in rows]

    def raid_action(self, db, user, command):
        now = time.time()
        db.execute("UPDATE raids SET status='expired' WHERE status='waiting' AND created<?", (now-900,))
        data = self.load(db, user)
        if command["action"] == "raid_create":
            pet, inv = objects(data)
            check_entry(pet, command["boss"], command["tier"])
            if db.execute("SELECT 1 FROM raids WHERE host=? AND status='waiting'", (user,)).fetchone():
                raise ValueError("이미 대기 중인 방이 있습니다.")
            db.execute("INSERT INTO raids VALUES (?,?,?,?,?,?,NULL)", (secrets.token_urlsafe(12),user,command["boss"],command["tier"],"waiting",now))
            return {"data": data, "message": "협동 레이드 방을 만들었습니다. 상대가 참가하면 전투가 시작됩니다. 대기 시간은 15분입니다."}
        row = db.execute("SELECT host,boss,tier,status,created FROM raids WHERE id=?", (command["room"],)).fetchone()
        if not row or row[3] != "waiting" or row[4] < now-900:
            raise ValueError("종료되었거나 만료된 레이드 방입니다.")
        host, boss, tier = row[:3]
        if command["action"] == "raid_cancel":
            if host != user:
                raise ValueError("방장만 대기를 취소할 수 있습니다.")
            db.execute("UPDATE raids SET status='cancelled' WHERE id=?", (command["room"],))
            return {"data": data, "message": "협동 레이드 대기를 취소했습니다."}
        if command["action"] != "raid_join" or host == user:
            raise ValueError("다른 테이머의 방에 참가해 주세요.")
        other = self.load(db, host)
        data, _ = act(data, {"action": "refresh"})
        other, _ = act(other, {"action": "refresh"})
        host_pet, host_inv = objects(other)
        pet, inv = objects(data)
        result = battle([(host_pet, host_inv), (pet, inv)], boss, tier)
        for owner, save, fighter, inventory in ((host,other,host_pet,host_inv), (user,data,pet,inv)):
            save.update(pet=fighter.to_dict(), inventory=inventory.to_dict(), revision=save["revision"]+1, last_battle=result)
            db.execute("UPDATE players SET data=? WHERE id=?", (json.dumps(save,ensure_ascii=False),owner))
        db.execute("UPDATE raids SET status='finished',result=? WHERE id=?", (json.dumps(result,ensure_ascii=False),command["room"]))
        db.execute("UPDATE raids SET status='cancelled' WHERE status='waiting' AND host IN (?,?)", (host,user))
        return {"data": data, "message": result["message"]}

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
