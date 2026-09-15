"""원본 신수 규칙과 웹 명령을 연결한다."""
import time
from copy import deepcopy
from shisu.domain.legacy.pet import Pet
from shisu.domain.legacy.shop import Inventory, ITEMS_DATABASE, Shop
from shisu.domain.legacy.adventure import AdventureSystem, DUNGEON_DATABASE, DUNGEON_DIFFICULTIES
from shisu.domain.legacy import farming

SAVE_VERSION = 2


def new_save():
    return {"save_version": SAVE_VERSION, "pet": Pet().to_dict(), "inventory": Inventory().to_dict(),
            "last_tick": time.time(), "revision": 0}


def migrate(data):
    if data.get("save_version") != SAVE_VERSION:
        raise ValueError("저장 버전을 확인해 주세요. 자동 초기화하지 않습니다.")
    return deepcopy(data)


def objects(data):
    return Pet(custom_data=data["pet"]), Inventory(deepcopy(data["inventory"]))


def view(data, nickname):
    pet, inv = objects(data)
    return {**data, "nickname": nickname, "stats": pet.get_battle_stats(inv),
            "max_energy": pet.max_energy, "max_stamina": pet.max_stamina,
            "bonus": farming.stat_bonus(inv), "server_time": time.time()}


def act(data, command):
    data = migrate(data)
    pet, inv = objects(data)
    # 분 단위 누적으로 새로고침해도 자연 회복 시간을 잃지 않는다.
    minutes = int(max(0, time.time() - data["last_tick"]) // 60)
    if minutes:
        pet.apply_offline_time(minutes)
        data["last_tick"] += minutes * 60
    name = command["action"]
    ok, message = True, "저장했습니다."
    care = {"feed": pet.feed, "clean": pet.clean, "sleep": pet.sleep_toggle,
            "train": pet.train, "pet": pet.pet_animal, "cure": pet.cure}
    if name in care:
        ok, message = care[name]()
    elif name == "refresh":
        message = "신수 상태를 확인했습니다."
    elif name == "dungeon":
        dungeon, tier = command["dungeon"], command["tier"]
        if dungeon not in DUNGEON_DATABASE or tier not in DUNGEON_DIFFICULTIES:
            raise ValueError("지원하지 않는 던전 또는 난이도입니다.")
        if pet.is_sleeping:
            raise ValueError("신수를 깨운 뒤 모험을 시작해 주세요.")
        ok, message = AdventureSystem.run_multi_dungeon(pet, inv, dungeon, tier, times=1)
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
    elif name == "equip_armor":
        ok, message = inv.equip_armor(command["index"])
    elif name == "equip_relic":
        if command["index"] >= len(inv.relics_inventory):
            raise ValueError("보물이 없습니다.")
        ok, message = inv.equip_relic(inv.relics_inventory[command["index"]]["species"])
    elif name == "buy":
        if command["item"] != "small_candy":
            raise ValueError("이 상품은 구매할 수 없습니다.")
        ok, message = Shop.buy_item(pet, inv, command["item"], 1)
    elif name == "use":
        if command["item"] not in ITEMS_DATABASE:
            raise ValueError("알 수 없는 아이템입니다.")
        ok, message = Shop.use_item(pet, inv, command["item"])
    else:
        raise ValueError("지원하지 않는 행동입니다.")
    if not ok:
        raise ValueError(message)
    data.update(pet=pet.to_dict(), inventory=inv.to_dict(), revision=data["revision"] + 1)
    return data, message


def catalog():
    return {"dungeons": DUNGEON_DATABASE, "difficulties": DUNGEON_DIFFICULTIES,
            "items": ITEMS_DATABASE, "gems": farming.GEM_VALUES}
