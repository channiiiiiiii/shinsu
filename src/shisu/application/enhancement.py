"""저장 상태를 변경하지 않는 강화 견적과 성공 후 전투 스탯."""
from copy import deepcopy
from shisu.domain.legacy.shop import ARMORS_DATABASE, EXCLUSIVE_RELICS, ITEMS_DATABASE
from shisu.domain.legacy.enhancement_rules import RELIC_RATES, ARMOR_RATES, STAR_GOLD, CORES, relic_cost, armor_cost

ACTIONS = ('enhance_relic', 'enhance_armor', 'ascend_armor')
STATS = ('max_hp', 'atk', 'def', 'spd', 'crit')


def quote(pet, inv, action):
    relic = action == 'enhance_relic'
    ascend = action == 'ascend_armor'
    equipment = inv.equipped_relic if relic else inv.equipped_armor
    result = {'action': action, 'available': False, 'materials': [], 'reason': '', 'rate': 0,
              'name': '보물' if relic else '방어구', 'level': 0, 'stars': 0}
    if not equipment:
        result['reason'] = '장비를 먼저 장착해 주세요.'
        return result
    level, stars = equipment.get('level', 0), equipment.get('stars', 0)
    info = EXCLUSIVE_RELICS[equipment['species']] if relic else ARMORS_DATABASE[equipment['armor_id']]
    result.update(name=info['name'], level=level, stars=stars)
    costs = []
    stones = inv.items.get('stone', 0) + inv.items.get('armor_stone', 0)
    if relic:
        if level >= min(10, pet.get_relic_max_level()):
            result['reason'] = '최대 강화 단계' if level >= 10 else f'레이드 관문 상한 +{pet.get_relic_max_level()}'
            return result
        stone, essence, crystal, gold = relic_cost(level)
        costs = [('강화석', stones, stone), ('보물 정수 (종족 정수 우선)', inv.species_essences.get(equipment['species'], 0) + inv.items.get('relic_essence', 0), essence)]
        if crystal:
            costs.append(('악몽의 결정', inv.items.get('nightmare_crystal', 0), crystal))
        result['rate'] = RELIC_RATES[level]
    elif ascend:
        if level < 15 or (not info.get('is_mythic', False) and info.get('max_enhance', 15) < 15):
            result['reason'] = '+15 신화 방어구 필요'
            return result
        if stars >= 5:
            result['reason'] = '★5 MAX'
            return result
        core = next((key for key in CORES if inv.items.get(key, 0) >= 1), None)
        costs = [(ITEMS_DATABASE[core]['name'] if core else '고대 핵 (전용 또는 범용)', inv.items.get(core, 0), 1)]
        gold = STAR_GOLD[stars]
        result.update(rate=1, bonus_before=stars * 6, bonus_after=(stars + 1) * 6)
    else:
        if level >= info.get('max_enhance', 15):
            result['reason'] = '최대 강화 단계'
            return result
        stone, essence, crystal, mythic, gold = armor_cost(level)
        costs = [('강화석', stones, stone)]
        if level >= 5:
            costs.append(('보물 정수', inv.items.get('relic_essence', 0), essence))
        for name, key, required in [('악몽의 결정', 'nightmare_crystal', crystal), ('신화의 핵', 'mythic_core', mythic)]:
            if required:
                costs.append((name, inv.items.get(key, 0), required))
        result['rate'] = ARMOR_RATES[level]
    costs.append(('골드', pet.coins, gold))
    result['materials'] = [dict(name=name, owned=owned, required=required) for name, owned, required in costs]
    result['available'] = all(owned >= required for _, owned, required in costs)
    if not result['available']:
        result['reason'] = '재료 부족'
    preview = deepcopy(inv)
    target = preview.equipped_relic if relic else preview.equipped_armor
    target['stars' if ascend else 'level'] = (stars if ascend else level) + 1
    before, after = pet.get_battle_stats(inv), pet.get_battle_stats(preview)
    result['before'] = {key: before[key] for key in STATS}
    result['after'] = {key: after[key] for key in STATS}
    return result
