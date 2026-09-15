import asyncio

import pytest

from shisu.application.farming_service import FarmingService
from shisu.domain.farming import (
    GEM_VALUES, add_gem, drop_decay, equip_gem, reroll_engraving,
    stage_skill_profile, stat_bonus, synthesize_gem, toggle_lock,
)
from shisu.domain.models import PlayerState


class FixedRandom:
    def choices(self, population, weights, *, k):
        return [population[0]]

    def choice(self, sequence):
        return sequence[0]

    def random(self):
        return 0.0


class MemoryRepository:
    def __init__(self, player=None, fail=False):
        self.player = player or PlayerState("tester")
        self.fail = fail

    async def get(self, user_id):
        return self.player

    async def save(self, player):
        if self.fail:
            raise RuntimeError("의도된 저장 실패")
        self.player = player


def test_각인은_3슬롯이고_동일_옵션이_중복되지_않는다():
    player = PlayerState("tester")
    player.items["normal_relic_engraving_stone"] = 20
    for slot in range(3):
        success, _ = reroll_engraving(player, "relic", slot, 1, FixedRandom())
        assert success
    options = [row["option"] for row in player.relic_engravings]
    assert len(set(options)) == 3


def test_각인_잠금_비용은_1_4_9다():
    player = PlayerState("tester")
    player.items["normal_relic_engraving_stone"] = 30
    for slot in range(3):
        assert reroll_engraving(player, "relic", slot, 1, FixedRandom())[0]
    assert player.items["normal_relic_engraving_stone"] == 27
    assert toggle_lock(player, "relic", 0)
    before = player.items["normal_relic_engraving_stone"]
    assert reroll_engraving(player, "relic", 1, 1, FixedRandom())[0]
    assert before - player.items["normal_relic_engraving_stone"] == 4
    assert toggle_lock(player, "relic", 1)
    before = player.items["normal_relic_engraving_stone"]
    assert reroll_engraving(player, "relic", 2, 1, FixedRandom())[0]
    assert before - player.items["normal_relic_engraving_stone"] == 9


def test_보석은_두개로_확정_합성하고_10레벨을_초과하지_않는다():
    player = PlayerState("tester")
    add_gem(player, "atk", 6, 2)
    assert synthesize_gem(player, "atk", 6)
    assert player.gems["atk"]["7"] == 1
    player.gems["atk"]["10"] = 2
    assert not synthesize_gem(player, "atk", 10)


def test_장착_보석과_각인은_절대값으로_합산된다():
    player = PlayerState("tester")
    player.relic_engravings[0] = {"option": "atk", "grade": "normal", "value": 5}
    add_gem(player, "atk", 2)
    assert equip_gem(player, "atk", 2)
    assert stat_bonus(player)["atk"] == 5 + GEM_VALUES["atk"][1]


def test_하위_난이도_감쇠와_성장_역할이_적용된다():
    assert [drop_decay(4, tier) for tier in (4, 3, 2, 1)] == [1.0, 0.5, 0.2, 0.05]
    assert stage_skill_profile(4, "공격형")["damage_mult"] == 1.4
    assert stage_skill_profile(4, "탱커형")["damage_mult"] < 1.4


def test_저장_실패는_성공으로_처리되지_않는다():
    player = PlayerState("tester")
    player.items["normal_relic_engraving_stone"] = 2
    service = FarmingService(MemoryRepository(player, fail=True))
    with pytest.raises(RuntimeError):
        asyncio.run(service.reroll("tester", "relic", 0, 1))
    assert player.items["normal_relic_engraving_stone"] == 2
    assert player.relic_engravings == [None, None, None]

