"""원본 신수 규칙과 웹 명령을 연결한다."""
import time
from copy import deepcopy
from shisu.domain.legacy.pet import Pet
from shisu.domain.legacy.shop import Inventory, ITEMS_DATABASE, Shop, EXCLUSIVE_RELICS, ARMORS_DATABASE
from shisu.domain.legacy.adventure import AdventureSystem, DUNGEON_DATABASE, DUNGEON_DIFFICULTIES
from shisu.domain.legacy import farming
from shisu.domain.combat import battle, skills, effects, RAID_LEVELS, BOSS_DATABASE, RAID_DIFFICULTIES
from shisu.application.enhancement import ACTIONS as ENHANCEMENTS, quote
from shisu.application.stat_breakdown import breakdown

SAVE_VERSION = 2


def new_save():
    return {"save_version": SAVE_VERSION, "pet": Pet().to_dict(), "inventory": Inventory().to_dict(),
            "last_tick": time.time(), "revision": 0, "initial_rerolls_used": 0}


def migrate(data):
    if data.get("save_version") != SAVE_VERSION:
        raise ValueError("저장 버전을 확인해 주세요. 자동 초기화하지 않습니다.")
    migrated = deepcopy(data)
    migrated.setdefault("initial_rerolls_used", 0)
    return migrated


def objects(data):
    return Pet(custom_data=data["pet"]), Inventory(deepcopy(data["inventory"]))


def view(data, nickname):
    pet, inv = objects(data)
    return {**data, "nickname": nickname, "stats": pet.get_battle_stats(inv),
            "stat_breakdown": breakdown(pet, inv),
            "max_energy": pet.max_energy, "max_stamina": pet.max_stamina,
            "bonus": farming.stat_bonus(inv), "server_time": time.time(),
            "skills": skills(pet), "level_cap": pet.get_level_cap(), "relic_cap": pet.get_relic_max_level(),
            "enhancements": {action: quote(pet, inv, action) for action in ENHANCEMENTS}}


def act(data, command):
    data = migrate(data)
    pet, inv = objects(data)
    old_stage = pet.stage
    fx = effects(inv)
    # 분 단위 누적으로 새로고침해도 자연 회복 시간을 잃지 않는다.
    minutes = int(max(0, time.time() - data["last_tick"]) // 60)
    if minutes:
        old_hunger, old_clean = pet.hunger, pet.cleanliness
        pet.apply_offline_time(minutes)
        pet.hunger += max(0, old_hunger - pet.hunger) * fx.get("hunger_slow", 0)
        pet.cleanliness += max(0, old_clean - pet.cleanliness) * fx.get("clean_slow", 0)
        data["last_tick"] += minutes * 60
    name = command["action"]
    enhancement_before = quote(pet, inv, name) if name in ENHANCEMENTS else None
    ok, message = True, "저장했습니다."
    care = {"feed": pet.feed, "clean": pet.clean, "sleep": pet.sleep_toggle,
            "train": pet.train, "pet": pet.pet_animal, "cure": pet.cure}
    if name in care:
        energy, happy = pet.energy, pet.happiness
        old_exp, old_level = pet.exp, pet.level
        ok, message = care[name]()
        if ok:
            pet.energy += max(0, energy - pet.energy) * fx.get("energy_save", 0)
            pet.happiness = min(100, pet.happiness + max(0, pet.happiness - happy) * fx.get("happiness_gain", 0))
            if name == "train" and fx.get("train_exp"):
                earned = pet.exp - old_exp + sum(pet.calc_req_exp(level) for level in range(old_level, pet.level))
                message += "\n" + " ".join(pet.gain_exp(int(max(0, earned) * fx["train_exp"])))
    elif name == "refresh":
        message = "신수 상태를 확인했습니다."
    elif name == "rename":
        ok, message = pet.rename(command["name"])
    elif name == "pet_reroll":
        if pet.level != 1:
            raise ValueError("초기 신수 다시 뽑기는 Lv.1에서만 가능합니다.")
        if data["initial_rerolls_used"] >= 3:
            raise ValueError("초기 신수 다시 뽑기 3회를 모두 사용했습니다.")
        old_coins = pet.coins
        pet = Pet()
        pet.coins = old_coins
        inv.equipped_relic = {"species": pet.species_key, "level": 0}
        data["initial_rerolls_used"] += 1
        # 잡지식: 서버에서 다시 뽑아야 새로고침 꼼수도 운명의 여신을 속이지 못해요.
        remaining = 3 - data["initial_rerolls_used"]
        message = f"새로운 운명의 알이 깨어났습니다! {pet.emoji} {pet.name} ({pet.species_name} · {pet.personality}) · 남은 다시 뽑기 {remaining}회"
    elif name == "dungeon":
        dungeon, tier = command["dungeon"], command["tier"]
        if dungeon not in DUNGEON_DATABASE or tier not in DUNGEON_DIFFICULTIES:
            raise ValueError("지원하지 않는 던전 또는 난이도입니다.")
        if pet.is_sleeping:
            raise ValueError("신수를 깨운 뒤 모험을 시작해 주세요.")
        if tier >= 4 and not {1, 2, 3, 4}.issubset(pet.raid_clears.get(str(tier - 1), [])):
            raise ValueError("이전 난이도 레이드의 4대 보스를 먼저 토벌해 주세요.")
        coins = pet.coins
        ok, message = AdventureSystem.run_multi_dungeon(pet, inv, dungeon, tier, times=command.get("times", 1))
        bonus = int(max(0, pet.coins - coins) * fx.get("gold_gain", 0))
        pet.coins += bonus
        if bonus:
            message += f"\n각인 추가 골드 +{bonus}G"
    elif name == "raid":
        result = battle([(pet, inv)], command["boss"], command["tier"])
        data["last_battle"] = result
        message = result["message"]
    elif name == "potential":
        ok, message = pet.upgrade_potential(command["gem"], inv)
    elif name == "enhance_relic":
        ok, message, pet.coins = inv.enhance_relic(pet.coins, pet.get_relic_max_level())
    elif name == "enhance_armor":
        ok, message, pet.coins = inv.enhance_armor(pet.coins)
    elif name == "ascend_armor":
        ok, message, pet.coins = inv.ascend_armor_star(pet.coins)
    elif name == "craft_relic":
        ok, message, pet.coins = inv.craft_relic(pet.species_key, pet.coins)
    elif name == "dismantle_relic":
        ok, message = inv.dismantle_relic(command["index"])
    elif name == "reincarnate":
        if command.get("confirmation") != "환생":
            raise ValueError("초기화 항목을 확인하고 '환생'을 입력해 주세요.")
        ok, message = pet.reincarnate(inv)
    elif name == "reroll":
        if not getattr(inv, "equipped_" + command["kind"]):
            raise ValueError("먼저 해당 장비를 장착해 주세요.")
        ok, _ = farming.reroll_engraving(inv, command["kind"], command["slot"], command["tier"])
        message = "각인을 재설정했습니다." if ok else "잠금 상태 또는 각인석 수량을 확인해 주세요."
    elif name == "lock":
        ok = farming.toggle_lock(inv, command["kind"], command["slot"])
        message = "잠금 상태를 변경했습니다." if ok else "빈 슬롯은 잠글 수 없습니다."
    elif name == "synthesize":
        gem, level = command["gem"], command["level"]
        reserved = int(inv.equipped_gems[gem] == level)
        if inv.gems[gem][str(level)] - reserved < 2:
            raise ValueError("장착 중인 보석을 제외한 같은 레벨 보석 2개가 필요합니다.")
        ok = farming.synthesize_gem(inv, gem, level)
        message = "보석을 합성했습니다." if ok else "최고 레벨은 합성할 수 없습니다."
    elif name == "equip_gem":
        ok = farming.equip_gem(inv, command["gem"], command["level"])
        message = "보석을 장착했습니다." if ok else "보유한 보석을 선택해 주세요."
    elif name == "unequip_gem":
        ok = farming.unequip_gem(inv, command["gem"])
        message = "보석을 해제했습니다." if ok else "장착 중인 보석이 없습니다."
    elif name == "equip_armor":
        ok, message = inv.equip_armor(command["index"])
    elif name == "equip_relic":
        if command["index"] >= len(inv.relics_inventory):
            raise ValueError("보물이 없습니다.")
        ok, message = inv.equip_relic(inv.relics_inventory[command["index"]]["species"])
    elif name == "buy":
        if ITEMS_DATABASE.get(command["item"], {}).get("price", 0) <= 0:
            raise ValueError("이 상품은 구매할 수 없습니다.")
        ok, message = Shop.buy_item(pet, inv, command["item"], command.get("times", 1))
    elif name == "use":
        if command["item"] not in ITEMS_DATABASE:
            raise ValueError("알 수 없는 아이템입니다.")
        ok, message = Shop.use_item(pet, inv, command["item"])
    else:
        raise ValueError("지원하지 않는 행동입니다.")
    if not ok:
        raise ValueError(message)
    if enhancement_before:
        after = quote(pet, inv, name)
        field = 'stars' if name == 'ascend_armor' else 'level'
        data['last_enhancement'] = {**enhancement_before, 'success': after[field] > enhancement_before[field],
                                    'result_level': after[field], 'message': message,
                                    'after': {key: pet.get_battle_stats(inv)[key] for key in ('max_hp', 'atk', 'def', 'spd', 'crit')}}
    if pet.stage > old_stage:
        message += f"\n✨ {pet.stage}단계 진입! 스킬이 자동 강화되었습니다."
    data.update(pet=pet.to_dict(), inventory=inv.to_dict(), revision=data["revision"] + 1)
    return data, message


def catalog():
    items = deepcopy(ITEMS_DATABASE)
    for tier, label in ((1,"노말"),(2,"하드"),(3,"악몽"),(4,"신화")):
        for kind, name in (("relic","보물"),("armor","방어구")):
            items[farming.stone_item_id(kind,tier)] = {"name": f"{label} {name} 각인석", "price": 0, "desc": "각인 화면에서 사용"}
    return {"dungeons": DUNGEON_DATABASE, "difficulties": DUNGEON_DIFFICULTIES,
            "items": items, "gems": farming.GEM_VALUES,
            "bosses": BOSS_DATABASE, "raid_difficulties": RAID_DIFFICULTIES, "raid_levels": RAID_LEVELS,
            "armors": ARMORS_DATABASE, "relics": EXCLUSIVE_RELICS}
