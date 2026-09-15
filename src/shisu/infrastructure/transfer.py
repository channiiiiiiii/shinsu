"""명시적인 계정 배정으로 세이브를 이전하고 서버에서 클라우드 백업한다."""
import json
import os
import time
from copy import deepcopy
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from shisu.application.game import SAVE_VERSION, migrate, objects, view
from shisu.domain.legacy.pet import Pet
from shisu.domain.legacy.shop import Inventory


def convert_save(raw):
    if not isinstance(raw, dict):
        raise ValueError("세이브는 JSON 객체여야 합니다.")
    raw = deepcopy(raw.get("save_data", raw))
    if raw.get("save_version") == SAVE_VERSION:
        result = migrate(raw)
    else:
        if raw.get("save_version", 17) not in (17, 18) or not isinstance(raw.get("pet"), dict) or not isinstance(raw.get("inventory"), dict):
            raise ValueError("Shisu 스키마 2 또는 DAMAGOCHI 17/18 세이브를 선택하세요.")
        if not raw["pet"].get("species_key"):
            raise ValueError("신수 종족 정보가 없는 세이브입니다.")
        result = {"save_version": SAVE_VERSION, "pet": Pet(custom_data=raw["pet"]).to_dict(),
                  "inventory": Inventory(raw["inventory"]).to_dict(), "revision": 0,
                  "last_tick": time.time(), "legacy_metadata": {k:v for k,v in raw.items() if k not in ("pet","inventory")}}
    try:
        objects(result)
        view(result, "이전할 테이머")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("세이브의 신수·장비 필드를 확인하세요.") from exc
    return result


def import_save(database, account, raw, replace=False):
    if account not in ("player1", "player2"):
        raise ValueError("이전할 계정을 명시해 주세요.")
    data = convert_save(raw)
    # 덮어쓰기 전 DB 전체 백업을 남겨 잘못 배정한 계정도 복구할 수 있다.
    backup = database.path.with_name(database.path.name + f".before-import-{time.time_ns()}.bak")
    database.backup(backup)
    with database.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT data FROM players WHERE id=?", (account,)).fetchone()
        if row and not replace:
            raise ValueError("이미 저장이 있는 계정입니다. 백업 후 --replace를 명시해야 교체할 수 있습니다.")
        data["revision"] = json.loads(row[0])["revision"] + 1 if row else 0
        db.execute("INSERT INTO players VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (account,json.dumps(data,ensure_ascii=False)))
        db.execute("DELETE FROM requests WHERE user_id=?", (account,))
        db.execute("DELETE FROM sessions WHERE user_id=?", (account,))
        db.execute("UPDATE raids SET status='cancelled' WHERE status='waiting'")
    return backup


def cloud_request(table, query, payload=None):
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    secret = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if urlsplit(base).scheme != "https" or not secret:
        raise ValueError("SUPABASE_URL(HTTPS)과 서버 전용 SUPABASE_SECRET_KEY 설정이 필요합니다.")
    headers = {"apikey": secret, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"}
    if not secret.startswith("sb_secret_"):
        headers["Authorization"] = "Bearer " + secret
    body = json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
    request = Request(base+"/rest/v1/"+table+"?"+urlencode(query), data=body, headers=headers, method="POST" if body is not None else "GET")
    for attempt in range(3):
        try:
            with urlopen(request, timeout=15) as response:
                content = response.read()
                return json.loads(content) if content else None
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise ValueError(f"Supabase 요청 실패(HTTP {exc.code}). 서버 키와 테이블 설정을 확인하세요.") from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise ValueError("Supabase에 연결하지 못했습니다. 로컬 저장은 유지됩니다.") from None
        time.sleep(attempt+1)


def cloud_backup(database):
    with database.connect() as db:
        rows = db.execute("SELECT id,data FROM players ORDER BY id").fetchall()
    if not rows:
        return
    # 두 계정의 저장을 한 JSON 객체로 보내 같은 시점의 복원본을 만든다.
    cloud_request("shinsu_backups", {"on_conflict": "id"}, {"id": os.getenv("SHISU_CLOUD_SLOT", "default"),
                  "save_data": {user:json.loads(data) for user,data in rows}, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())})


def cloud_download(account, legacy_id=None):
    if legacy_id:
        rows = cloud_request("user_saves", {"user_id": "eq."+legacy_id, "select": "save_data", "limit": "1"})
    else:
        rows = cloud_request("shinsu_backups", {"id": "eq."+os.getenv("SHISU_CLOUD_SLOT", "default"), "select": "save_data", "limit": "1"})
    if not rows:
        raise ValueError("요청한 클라우드 세이브가 없습니다.")
    data = rows[0]["save_data"]
    if not legacy_id:
        if account not in data:
            raise ValueError("백업에 해당 계정이 없습니다.")
        data = data[account]
    return data
