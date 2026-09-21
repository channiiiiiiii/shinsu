"""표시된 전투 스탯을 실제 계산 순서대로 출처별로 나눈다."""
from copy import deepcopy


STATS = {"hp": "max_hp", "atk": "atk", "def": "def", "spd": "spd", "crit": "crit"}
LABELS = ("신수 기본·성장", "잠재 성장", "컨디션", "방어구", "보물", "각인", "보석")


def breakdown(pet, inventory):
    actor, bag = deepcopy(pet), deepcopy(inventory)
    bag.equipped_armor = None
    bag.equipped_relic = None
    bag.armor_engravings = [None] * 3
    bag.relic_engravings = [None] * 3
    bag.equipped_gems = {key: 0 for key in STATS}
    actor.potential_growth = {key: 0 for key in STATS}
    actor.hunger = actor.happiness = 50
    actor.has_relic = False
    snapshots = [actor.get_battle_stats(bag)]

    actor.potential_growth = deepcopy(pet.potential_growth)
    snapshots.append(actor.get_battle_stats(bag))
    actor.hunger, actor.happiness = pet.hunger, pet.happiness
    snapshots.append(actor.get_battle_stats(bag))
    bag.equipped_armor = deepcopy(inventory.equipped_armor)
    snapshots.append(actor.get_battle_stats(bag))
    bag.equipped_relic = deepcopy(inventory.equipped_relic)
    actor.has_relic = pet.has_relic
    snapshots.append(actor.get_battle_stats(bag))
    bag.armor_engravings = deepcopy(inventory.armor_engravings)
    bag.relic_engravings = deepcopy(inventory.relic_engravings)
    snapshots.append(actor.get_battle_stats(bag))
    bag.equipped_gems = deepcopy(inventory.equipped_gems)
    snapshots.append(actor.get_battle_stats(bag))

    return {kind: [{"label": label, "value": snapshots[i][stat] if i == 0 else snapshots[i][stat] - snapshots[i - 1][stat]}
                   for i, label in enumerate(LABELS)] for kind, stat in STATS.items()}
