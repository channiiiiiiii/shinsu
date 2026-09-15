from __future__ import annotations

import random
from typing import Any, Protocol

from .models import GEM_TYPES, PlayerState


class RandomSource(Protocol):
    def choices(self, population, weights, *, k): ...
    def choice(self, sequence): ...
    def random(self) -> float: ...


GRADES = ("normal", "advanced", "rare", "hero", "legend", "relic", "ancient")
TIER_NAMES = {1: "normal", 2: "hard", 3: "nightmare", 4: "mythic"}
GRADE_WEIGHTS = {
    1: (("normal", "advanced", "rare", "hero"), (45, 35, 15, 5)),
    2: (("advanced", "rare", "hero", "legend"), (42, 35, 18, 5)),
    3: (("rare", "hero", "legend", "relic"), (42, 35, 18, 5)),
    4: (("hero", "legend", "relic", "ancient"), (48, 33, 17, 2)),
}
RELIC_VALUES = {
    "atk": (5, 10, 20, 35, 50, 70, 90), "spd": (3, 6, 10, 16, 24, 34, 45),
    "crit": (3, 6, 10, 16, 24, 34, 45), "basic_dmg": (2, 3, 5, 7, 10, 14, 18),
    "unique_dmg": (2, 3, 5, 7, 10, 14, 18), "ultimate_dmg": (2, 4, 6, 9, 12, 15, 18),
    "crit_dmg": (3, 5, 8, 12, 16, 19, 22), "boss_dmg": (1, 2, 3, 5, 7, 9, 10),
    "first3_dmg": (2, 3, 5, 7, 10, 13, 15), "high_hp_dmg": (2, 3, 5, 7, 10, 13, 15),
    "low_hp_dmg": (3, 4, 6, 9, 12, 14, 16), "spd_adv_dmg": (2, 3, 5, 7, 10, 13, 15),
    "lifesteal": (1, 2, 3, 4, 5, 7, 8), "extra_hit": (0, 0, 2, 3, 5, 6, 8),
    "gold_gain": (1, 2, 3, 4, 5, 6, 7), "train_exp": (1, 2, 3, 4, 5, 6, 7),
    "happiness_gain": (1, 2, 3, 4, 5, 6, 7),
}
ARMOR_VALUES = {
    "hp": (30, 60, 100, 150, 220, 300, 400), "def": (5, 10, 20, 35, 50, 70, 90),
    "spd": (3, 6, 10, 16, 24, 34, 45), "dmg_red": (1, 2, 3, 4, 6, 7, 8),
    "boss_dmg_red": (1, 2, 3, 5, 7, 9, 10), "low_hp_dmg_red": (2, 3, 5, 7, 10, 13, 15),
    "first3_dmg_red": (2, 3, 5, 7, 10, 13, 15), "heal_bonus": (2, 3, 5, 7, 10, 13, 15),
    "turn_regen": (0.2, 0.3, 0.5, 0.7, 1, 1.3, 1.5), "shield_bonus": (2, 3, 5, 7, 10, 13, 15),
    "crit_dmg_red": (2, 3, 5, 7, 10, 13, 15), "half_dmg_chance": (0, 0, 2, 3, 4, 5, 6),
    "hunger_slow": (1, 2, 3, 4, 5, 6, 7), "clean_slow": (1, 2, 3, 4, 5, 6, 7),
    "energy_save": (1, 2, 3, 4, 5, 6, 7),
}
GEM_VALUES = {
    "hp": (20, 40, 70, 110, 160, 220, 290, 370, 460, 560),
    "atk": (5, 10, 18, 28, 40, 54, 70, 88, 108, 130),
    "def": (5, 10, 18, 28, 40, 54, 70, 88, 108, 130),
    "spd": (3, 6, 10, 15, 21, 28, 36, 45, 55, 66),
    "crit": (3, 6, 10, 15, 21, 28, 36, 45, 55, 66),
}


def stone_item_id(kind: str, tier: int) -> str:
    if kind not in ("relic", "armor") or tier not in TIER_NAMES:
        raise ValueError("유효하지 않은 각인석 종류 또는 티어입니다.")
    return f"{TIER_NAMES[tier]}_{kind}_engraving_stone"


def roll_engraving(kind: str, tier: int, excluded=(), rng: RandomSource = random) -> dict[str, Any]:
    values = RELIC_VALUES if kind == "relic" else ARMOR_VALUES if kind == "armor" else None
    if values is None or tier not in TIER_NAMES:
        raise ValueError("유효하지 않은 각인 요청입니다.")
    available = [option for option in values if option not in set(excluded)]
    if not available:
        raise ValueError("중복되지 않는 각인 옵션이 남아 있지 않습니다.")
    grades, weights = GRADE_WEIGHTS[tier]
    grade = rng.choices(grades, weights, k=1)[0]
    option = rng.choice(available)
    return {"option": option, "grade": grade, "value": values[option][GRADES.index(grade)]}


def reroll_engraving(player: PlayerState, kind: str, slot: int, tier: int, rng: RandomSource = random):
    if kind not in ("relic", "armor") or slot not in range(3) or tier not in TIER_NAMES:
        return False, "유효하지 않은 각인 요청입니다."
    rows = getattr(player, f"{kind}_engravings")
    locks = getattr(player, f"{kind}_engraving_locks")
    if locks[slot]:
        return False, "잠긴 슬롯은 재설정할 수 없습니다."
    cost = (1, 4, 9)[sum(locks[index] for index in range(3) if index != slot)]
    item_id = stone_item_id(kind, tier)
    if player.items.get(item_id, 0) < cost:
        return False, f"각인석이 부족합니다. 필요 수량: {cost}"
    excluded = [row["option"] for index, row in enumerate(rows) if index != slot and row]
    rolled = roll_engraving(kind, tier, excluded, rng)
    player.items[item_id] -= cost
    if player.items[item_id] == 0:
        del player.items[item_id]
    rows[slot] = rolled
    return True, rolled


def toggle_lock(player: PlayerState, kind: str, slot: int) -> bool:
    if kind not in ("relic", "armor") or slot not in range(3):
        return False
    rows = getattr(player, f"{kind}_engravings")
    locks = getattr(player, f"{kind}_engraving_locks")
    if rows[slot] is None:
        return False
    locks[slot] = not locks[slot]
    return True


def add_gem(player: PlayerState, gem_type: str, level: int, count: int = 1) -> None:
    if gem_type not in GEM_TYPES or level not in range(1, 7) or count < 1:
        raise ValueError("직접 획득 보석은 Lv.1~6만 가능합니다.")
    player.gems[gem_type][str(level)] += count


def synthesize_gem(player: PlayerState, gem_type: str, level: int) -> bool:
    if gem_type not in GEM_TYPES or level not in range(1, 10):
        return False
    if player.gems[gem_type][str(level)] < 2:
        return False
    player.gems[gem_type][str(level)] -= 2
    player.gems[gem_type][str(level + 1)] += 1
    return True


def equip_gem(player: PlayerState, gem_type: str, level: int) -> bool:
    if gem_type not in GEM_TYPES or level not in range(1, 11):
        return False
    if player.gems[gem_type][str(level)] < 1:
        return False
    player.equipped_gems[gem_type] = level
    return True


def stat_bonus(player: PlayerState) -> dict[str, int]:
    result = {kind: 0 for kind in GEM_TYPES}
    for rows in (player.relic_engravings, player.armor_engravings):
        for row in rows:
            if row and row["option"] in result:
                result[row["option"]] += row["value"]
    for gem_type, level in player.equipped_gems.items():
        if level:
            result[gem_type] += GEM_VALUES[gem_type][level - 1]
    return result


def highest_unlocked_tier(player: PlayerState) -> int:
    highest = 1
    for tier in range(2, 5):
        previous = player.raid_clears.get(str(tier - 1), [])
        if len(set(previous)) >= 4:
            highest = tier
    return highest


def drop_decay(current_tier: int, played_tier: int) -> float:
    return (1.0, 0.5, 0.2, 0.05)[min(3, max(0, current_tier - played_tier))]


def stage_skill_profile(stage: int, role: str = "") -> dict[str, float]:
    stage = max(1, min(4, int(stage)))
    multiplier = (1.00, 1.12, 1.25, 1.40)[stage - 1]
    damage = multiplier
    if any(tag in role for tag in ("방어", "수호", "탱커", "체력", "지원")):
        damage = 1.0 + (multiplier - 1.0) * 0.65
    elif any(tag in role for tag in ("스피드", "속도")):
        damage = 1.0 + (multiplier - 1.0) * 0.85
    return {"damage_mult": damage, "effect_mult": multiplier}

