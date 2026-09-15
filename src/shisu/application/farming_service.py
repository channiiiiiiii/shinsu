from __future__ import annotations

import asyncio
from collections import defaultdict
from copy import deepcopy
from typing import Awaitable, Callable, Protocol, TypeVar

from shisu.domain import farming
from shisu.domain.models import PlayerState

T = TypeVar("T")


class PlayerRepository(Protocol):
    async def get(self, user_id: str) -> PlayerState: ...
    async def save(self, player: PlayerState) -> None: ...


class FarmingService:
    def __init__(self, repository: PlayerRepository):
        self.repository = repository
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def get_player(self, user_id: str) -> PlayerState:
        return await self.repository.get(user_id)

    async def _change(self, user_id: str, action: Callable[[PlayerState], T]) -> tuple[PlayerState, T]:
        async with self._locks[user_id]:
            player = await self.repository.get(user_id)
            snapshot = deepcopy(player)
            result = action(player)
            try:
                await self.repository.save(player)
            except Exception:
                # 저장 실패 시 성공 응답을 만들지 않고 변경 전 상태로 되돌립니다.
                player.__dict__.clear()
                player.__dict__.update(deepcopy(snapshot.__dict__))
                raise
            return player, result

    async def reroll(self, user_id: str, kind: str, slot: int, tier: int):
        return await self._change(user_id, lambda player: farming.reroll_engraving(player, kind, slot, tier))

    async def toggle_lock(self, user_id: str, kind: str, slot: int):
        return await self._change(user_id, lambda player: farming.toggle_lock(player, kind, slot))

    async def synthesize(self, user_id: str, gem_type: str, level: int):
        return await self._change(user_id, lambda player: farming.synthesize_gem(player, gem_type, level))

    async def equip(self, user_id: str, gem_type: str, level: int):
        return await self._change(user_id, lambda player: farming.equip_gem(player, gem_type, level))
