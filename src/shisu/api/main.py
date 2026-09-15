from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from shisu import __version__
from shisu.application.farming_service import FarmingService
from shisu.domain.farming import stage_skill_profile, stat_bonus
from shisu.infrastructure.json_repository import JsonPlayerRepository

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = Path(os.getenv("SHISU_DATA_PATH", PROJECT_ROOT / "data" / "players.json"))
WEB_ROOT = PROJECT_ROOT / "web"

app = FastAPI(title="Shisu API", version=__version__)
service = FarmingService(JsonPlayerRepository(DATA_PATH))


class EngravingRequest(BaseModel):
    kind: str
    slot: int = Field(ge=0, le=2)
    tier: int = Field(ge=1, le=4)


class SlotRequest(BaseModel):
    kind: str
    slot: int = Field(ge=0, le=2)


class GemRequest(BaseModel):
    gem_type: str
    level: int = Field(ge=1, le=10)


def payload(player):
    result = player.to_dict()
    result["stat_bonus"] = stat_bonus(player)
    result["skill_profile"] = stage_skill_profile(player.growth_stage, player.role)
    return result


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "shisu", "version": __version__}


@app.get("/api/players/{user_id}")
async def get_player(user_id: str):
    return payload(await service.get_player(user_id))


@app.post("/api/players/{user_id}/engravings/reroll")
async def reroll(user_id: str, request: EngravingRequest):
    player, result = await service.reroll(user_id, request.kind, request.slot, request.tier)
    success, detail = result
    if not success:
        raise HTTPException(status_code=409, detail=detail)
    return {"result": detail, "player": payload(player)}


@app.post("/api/players/{user_id}/engravings/toggle-lock")
async def toggle_lock(user_id: str, request: SlotRequest):
    player, success = await service.toggle_lock(user_id, request.kind, request.slot)
    if not success:
        raise HTTPException(status_code=409, detail="각인이 없는 슬롯은 잠글 수 없습니다.")
    return payload(player)


@app.post("/api/players/{user_id}/gems/synthesize")
async def synthesize(user_id: str, request: GemRequest):
    player, success = await service.synthesize(user_id, request.gem_type, request.level)
    if not success:
        raise HTTPException(status_code=409, detail="합성 조건을 만족하지 않습니다.")
    return payload(player)


@app.post("/api/players/{user_id}/gems/equip")
async def equip(user_id: str, request: GemRequest):
    player, success = await service.equip(user_id, request.gem_type, request.level)
    if not success:
        raise HTTPException(status_code=409, detail="보유하지 않은 보석입니다.")
    return payload(player)


app.mount("/assets", StaticFiles(directory=WEB_ROOT), name="assets")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(WEB_ROOT / "index.html")
