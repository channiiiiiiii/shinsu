from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from shisu.domain.models import PlayerState


class JsonPlayerRepository:
    def __init__(self, path: Path):
        self.path = path
        self._file_lock = asyncio.Lock()

    async def get(self, user_id: str) -> PlayerState:
        async with self._file_lock:
            records = await asyncio.to_thread(self._read_all)
        data = records.get(user_id)
        if data is None:
            # 개발 MVP 기본 지급품입니다. 운영 인증 도입 시 온보딩 보상 정책으로 이동합니다.
            player = PlayerState(user_id=user_id)
            player.items.update({
                "normal_relic_engraving_stone": 20,
                "normal_armor_engraving_stone": 20,
            })
            return player
        return PlayerState.from_dict(data)

    async def save(self, player: PlayerState) -> None:
        async with self._file_lock:
            await asyncio.to_thread(self._save_sync, player)

    def _read_all(self) -> dict:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save_sync(self, player: PlayerState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        records = self._read_all()
        records[player.user_id] = player.to_dict()
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(records, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, self.path)

