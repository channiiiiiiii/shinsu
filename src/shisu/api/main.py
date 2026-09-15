import json
import asyncio
from contextlib import suppress
import logging
import mimetypes
import os
import secrets
import sqlite3
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from shisu import __version__
from shisu.application.game import catalog, view
from shisu.infrastructure.database import Database

ROOT = Path(__file__).resolve().parents[3]
mimetypes.add_type("image/webp", ".webp")


class Login(BaseModel):
    account: Literal["player1", "player2"]
    code: str = Field(min_length=1, max_length=256)


class Command(BaseModel):
    action: Literal["feed","clean","sleep","train","pet","cure","refresh","rename","dungeon",
                    "reroll","lock","synthesize","equip_gem","equip_armor","equip_relic","buy","use",
                    "raid","raid_create","raid_join","raid_cancel","potential","enhance_relic","enhance_armor",
                    "ascend_armor","craft_relic","dismantle_relic","reincarnate"]
    request_id: UUID
    kind: Literal["relic","armor"] = "armor"
    slot: int = Field(default=0, ge=0, le=2)
    tier: int = Field(default=1, ge=1, le=5)
    dungeon: int = Field(default=1, ge=1, le=4)
    gem: Literal["hp","atk","def","spd","crit"] = "hp"
    level: int = Field(default=1, ge=1, le=10)
    index: int = Field(default=0, ge=0, le=10000)
    item: str = Field(default="small_candy", max_length=80)
    name: str = Field(default="", max_length=15)
    boss: int = Field(default=1, ge=1, le=5)
    times: int = Field(default=1, ge=1, le=10)
    room: str = Field(default="", max_length=80)
    confirmation: str = Field(default="", max_length=20)


def create_app(path=None, accounts=None, secure=None):
    @asynccontextmanager
    async def lifespan(app):
        configured = accounts if accounts is not None else json.loads(os.getenv("SHISU_ACCOUNTS", "{}"))
        if set(configured) != {"player1", "player2"}:
            raise RuntimeError("SHISU_ACCOUNTS에 player1, player2를 설정해 주세요.")
        codes = [v.get("code", "") for v in configured.values()]
        if any(len(code) < 24 for code in codes) or len(set(codes)) != 2:
            raise RuntimeError("계정마다 서로 다른 24자 이상 무작위 접속 코드가 필요합니다.")
        app.state.accounts = configured
        app.state.db = Database(path or os.getenv("SHISU_DB_PATH", str(ROOT / "data" / "shinsu.sqlite3")))
        async def sync_backups():
            from shisu.infrastructure.transfer import cloud_backup
            while True:
                await asyncio.sleep(60)
                try:
                    await run_in_threadpool(cloud_backup, app.state.db)
                except (ValueError, OSError):
                    logging.getLogger(__name__).warning("클라우드 백업 실패: 서버 설정을 확인하세요. 로컬 저장은 유지됩니다.")
        sync = asyncio.create_task(sync_backups()) if os.getenv("SHISU_CLOUD_BACKUP") == "true" else None
        try:
            yield
        finally:
            if sync:
                sync.cancel()
                with suppress(asyncio.CancelledError):
                    await sync

    app = FastAPI(title="신수", version=__version__, lifespan=lifespan)
    cookie_secure = secure if secure is not None else os.getenv("SHISU_COOKIE_SECURE", "true") == "true"
    attempts, attempt_lock = deque(maxlen=30), Lock()

    @app.middleware("http")
    async def security(request, call_next):
        if request.method == "POST" and request.headers.get("X-Shinsu-Client") != "web":
            return JSONResponse({"detail":"게임 화면에서 요청해 주세요."},status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api") else "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        return response

    def identity(request):
        user = app.state.db.user(request.cookies.get("shinsu_session", ""))
        if user not in app.state.accounts:
            raise HTTPException(401,"로그인이 필요합니다.")
        return user

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request, exc):
        logging.getLogger(__name__).error("저장소 작업 실패",exc_info=exc)
        return JSONResponse({"detail":"저장하지 못했습니다. 잠시 후 다시 시도해 주세요."},status_code=503)

    @app.get("/api/health")
    def health():
        with app.state.db.connect() as db:
            db.execute("SELECT 1")
        return {"status":"ok","version":__version__}

    @app.get("/api/account-names")
    def account_names():
        # 접속 코드는 절대 반환하지 않고, 로그인 선택지에 표시할 이름만 공개한다.
        configured = app.state.accounts
        return {account: value.get("name", account) for account, value in configured.items()}

    @app.post("/api/login")
    def login(body: Login, response: Response):
        now = time.monotonic()
        with attempt_lock:
            while attempts and attempts[0] < now - 60:
                attempts.popleft()
            if len(attempts) >= 20:
                raise HTTPException(429,"잠시 기다린 후 로그인해 주세요.")
            attempts.append(now)
        account = app.state.accounts[body.account]
        if not secrets.compare_digest(body.code.encode(), account["code"].encode()):
            raise HTTPException(401,"계정 또는 접속 코드를 확인해 주세요.")
        token = app.state.db.session(body.account)
        response.set_cookie("shinsu_session",token,httponly=True,secure=cookie_secure,samesite="strict",max_age=604800)
        return {"nickname":account["name"]}

    @app.post("/api/logout")
    def logout(request: Request, response: Response):
        app.state.db.logout(request.cookies.get("shinsu_session", ""))
        response.delete_cookie("shinsu_session")
        return {"ok":True}

    @app.get("/api/me")
    def me(request: Request):
        user = identity(request)
        return {**view(app.state.db.get(user),app.state.accounts[user]["name"]), "account": user}

    @app.get("/api/raids")
    def raids(request: Request):
        identity(request)
        return app.state.db.raid_rooms()

    @app.get("/api/catalog")
    def get_catalog(request: Request):
        identity(request)
        return catalog()

    @app.post("/api/actions")
    async def action(body: Command, request: Request):
        user = await run_in_threadpool(identity,request)
        command = body.model_dump(exclude={"request_id"})
        try:
            result = await run_in_threadpool(app.state.db.action,user,str(body.request_id),command)
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from exc
        return {"player":{**view(result["data"],app.state.accounts[user]["name"]), "account": user},"message":result["message"]}

    app.mount("/assets",StaticFiles(directory=ROOT / "web"),name="assets")

    @app.get("/",include_in_schema=False)
    def index():
        return FileResponse(ROOT / "web" / "index.html")

    @app.get("/sw.js",include_in_schema=False)
    def worker():
        return FileResponse(ROOT / "web" / "sw.js",media_type="application/javascript")

    return app


app = create_app()
