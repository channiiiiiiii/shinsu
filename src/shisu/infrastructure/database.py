"""두 사람의 저장·중복 요청·세션을 SQLite로 관리한다."""
import hashlib
import hmac
import json
import os
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
                CREATE TABLE IF NOT EXISTS registered_accounts (
                    user_id TEXT PRIMARY KEY, nickname TEXT NOT NULL,
                    password_salt BLOB NOT NULL, password_hash BLOB NOT NULL,
                    created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS data_migrations (
                    id TEXT PRIMARY KEY, previous_data TEXT NOT NULL, applied REAL NOT NULL);
            ''')
            self._apply_admin_migrations(db)

    @staticmethod
    def _apply_admin_migrations(db):
        """명시적으로 승인된 운영 세이브 변경을 정확히 한 번 적용한다."""
        migration_id = "20260916-player2-kirin"
        if db.execute("SELECT 1 FROM data_migrations WHERE id=?", (migration_id,)).fetchone():
            return
        row = db.execute("SELECT data FROM players WHERE id='player2'").fetchone()
        if not row:
            return
        previous = row[0]
        data = migrate(json.loads(previous))
        pet, inventory = objects(data)
        if pet.species_key != "기린":
            ok, message = pet.change_species("기린", inventory)
            if not ok:
                raise ValueError(message)
            data.update(pet=pet.to_dict(), inventory=inventory.to_dict(), revision=data["revision"] + 1)
            db.execute("UPDATE players SET data=? WHERE id='player2'", (json.dumps(data, ensure_ascii=False),))
        db.execute("INSERT INTO data_migrations VALUES (?,?,?)", (migration_id, previous, time.time()))

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

    def change_species(self, user, species):
        """관리자가 기존 진행도를 보존한 채 한 계정의 종족만 변경한다."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM players WHERE id=?", (user,)).fetchone()
            if not row:
                raise ValueError(f"저장된 계정을 찾을 수 없습니다: {user}")
            data = migrate(json.loads(row[0]))
            pet, inventory = objects(data)
            ok, message = pet.change_species(species, inventory)
            if not ok:
                raise ValueError(message)
            data.update(pet=pet.to_dict(), inventory=inventory.to_dict(), revision=data["revision"] + 1)
            db.execute("UPDATE players SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), user))
            return message

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

    @staticmethod
    def password_hash(password, salt):
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)

    def register(self, user, nickname, password):
        salt = os.urandom(16)
        password_hash = self.password_hash(password, salt)
        try:
            with self.connect() as db:
                db.execute(
                    "INSERT INTO registered_accounts VALUES (?,?,?,?,?)",
                    (user, nickname, salt, password_hash, time.time()),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("이미 가입이 완료된 계정입니다.") from exc

    def registered_account(self, user):
        with self.connect() as db:
            return db.execute(
                "SELECT nickname,password_salt,password_hash FROM registered_accounts WHERE user_id=?",
                (user,),
            ).fetchone()

    def verify_password(self, user, password):
        row = self.registered_account(user)
        return bool(row and hmac.compare_digest(self.password_hash(password, row[1]), row[2]))

    def registered_names(self):
        with self.connect() as db:
            rows = db.execute("SELECT user_id,nickname FROM registered_accounts").fetchall()
        return dict(rows)

    def backup(self, path):
        with self.connect() as source:
            target = sqlite3.connect(path)
            try:
                source.backup(target)
            finally:
                target.close()
