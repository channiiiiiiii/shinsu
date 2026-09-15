from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SAVE_VERSION = 1
GEM_TYPES = ("hp", "atk", "def", "spd", "crit")


def _empty_gems() -> dict[str, dict[str, int]]:
    return {kind: {str(level): 0 for level in range(1, 11)} for kind in GEM_TYPES}


@dataclass
class PlayerState:
    user_id: str
    save_version: int = SAVE_VERSION
    items: dict[str, int] = field(default_factory=dict)
    relic_engravings: list[dict[str, Any] | None] = field(default_factory=lambda: [None] * 3)
    armor_engravings: list[dict[str, Any] | None] = field(default_factory=lambda: [None] * 3)
    relic_engraving_locks: list[bool] = field(default_factory=lambda: [False] * 3)
    armor_engraving_locks: list[bool] = field(default_factory=lambda: [False] * 3)
    gems: dict[str, dict[str, int]] = field(default_factory=_empty_gems)
    equipped_gems: dict[str, int] = field(default_factory=lambda: {kind: 0 for kind in GEM_TYPES})
    raid_clears: dict[str, list[str]] = field(default_factory=dict)
    growth_stage: int = 1
    role: str = "공격형"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerState":
        version = int(data.get("save_version", 1))
        if version > SAVE_VERSION:
            raise ValueError(f"지원하지 않는 미래 세이브 버전입니다: {version}")
        player = cls(user_id=str(data["user_id"]))
        for name in (
            "items", "relic_engravings", "armor_engravings",
            "relic_engraving_locks", "armor_engraving_locks", "gems",
            "equipped_gems", "raid_clears", "growth_stage", "role",
        ):
            if name in data:
                setattr(player, name, data[name])
        player._normalize()
        return player

    def _normalize(self) -> None:
        for kind in ("relic", "armor"):
            rows = list(getattr(self, f"{kind}_engravings") or [])[:3]
            locks = list(getattr(self, f"{kind}_engraving_locks") or [])[:3]
            setattr(self, f"{kind}_engravings", rows + [None] * (3 - len(rows)))
            setattr(self, f"{kind}_engraving_locks", locks + [False] * (3 - len(locks)))
        normalized = _empty_gems()
        for kind in GEM_TYPES:
            for level in range(1, 11):
                normalized[kind][str(level)] = max(0, int(self.gems.get(kind, {}).get(str(level), 0)))
        self.gems = normalized
        self.equipped_gems = {
            kind: max(0, min(10, int(self.equipped_gems.get(kind, 0)))) for kind in GEM_TYPES
        }
        self.growth_stage = max(1, min(4, int(self.growth_stage)))

