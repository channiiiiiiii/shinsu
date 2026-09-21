"""개인·협동 레이드의 성장 스킬, 각인, 전투 및 보상 규칙."""
import random
from copy import deepcopy

from .legacy.adventure import BOSS_DATABASE, BOSS_STAT_TABLE, RAID_DIFFICULTIES, BOSS_SKILLS_DATABASE, choose_boss_action
from .legacy.species import SPECIES_SKILLS
from .legacy import farming

RAID_LEVELS = {1: 1, 2: 30, 3: 50, 4: 70, 5: 99}
CORE_IDS = {1: "ent", 2: "dragon", 3: "ifrit", 4: "guardian", 5: "omega"}


def effects(inv):
    result = {}
    for kind in ("relic", "armor"):
        if not getattr(inv, "equipped_" + kind):
            continue
        for row in getattr(inv, kind + "_engravings"):
            if row:
                result[row["option"]] = result.get(row["option"], 0) + row["value"] / 100
    return result


def skills(pet):
    """원본을 복사해 계산하므로 재접속으로 성장 배율이 중첩되지 않는다."""
    stage = max(1, min(4, pet.stage))
    role = {"현무": "방어", "사자": "방어", "늑대": "스피드", "그리핀": "스피드"}.get(pet.species_key, pet.role)
    profile = farming.stage_skill_profile(stage, role)
    result = deepcopy(SPECIES_SKILLS[pet.species_key])
    for key, skill in result.items():
        skill["skill_id"] = key
        skill["name"] = ("", "", "각성 · ", "초월 · ")[stage - 1] + skill["name"]
        if "atk_ratio" in skill:
            skill["atk_ratio"] *= profile["damage_mult"]
        for field in ("heal_hp_pct", "regen_turn_pct", "lifesteal_pct", "buff_def", "buff_atk", "buff_spd", "dmg_reduction", "shield_pct", "pen_def", "spd_bonus", "buff_all"):
            if field in skill:
                skill[field] = min(0.8, skill[field] * profile["effect_mult"])
        skill["desc"] += f" · {stage}단계: 피해 ×{profile['damage_mult']:.2f}, 효과 ×{profile['effect_mult']:.2f}"
    if pet.species_key in ("늑대", "그리핀") and stage >= 3:
        result["basic2"]["hits"] = result["basic2"].get("hits", 1) + 1
    if pet.species_key == "현무":
        result["unique"]["shield_pct"] = (0.15, 0.18, 0.22, 0.25)[stage - 1]
    return result


def check_entry(pet, boss, tier):
    if boss not in BOSS_DATABASE or tier not in RAID_LEVELS:
        raise ValueError("레이드 선택을 확인해 주세요.")
    if pet.is_sleeping or getattr(pet, "is_critically_injured", False):
        raise ValueError("수면 또는 치명상 상태에서는 레이드에 입장할 수 없습니다.")
    if pet.level < RAID_LEVELS[tier]:
        raise ValueError(f"이 난이도는 Lv.{RAID_LEVELS[tier]}부터 입장할 수 있습니다.")
    clears = pet.raid_clears
    if tier > 1 and not {1, 2, 3, 4}.issubset(clears.get(str(tier - 1), [])):
        raise ValueError("이전 난이도의 4대 보스를 먼저 토벌해 주세요.")
    if boss == 5 and (tier != 5 or not {1, 2, 3, 4}.issubset(clears.get("5", []))):
        raise ValueError("오메가는 고대 4대 보스 토벌 후 입장할 수 있습니다.")
    probe = deepcopy(pet)
    needed = probe.consume_energy(BOSS_DATABASE[boss]["energy_cost"], "raid")
    if pet.stamina < needed:
        raise ValueError(f"모험 기력이 부족합니다. 필요 기력: {needed}")


def reward(pet, inv, boss, tier):
    base, diff = BOSS_DATABASE[boss], RAID_DIFFICULTIES[tier]
    first, kills, logs = pet.record_raid_clear(tier, boss)
    gold = int(base["base_gold"] * diff["gold_mult"] * (1 + effects(inv).get("gold_gain", 0)))
    exp = int(base["base_exp"] * diff["exp_mult"])
    if pet.species_key == "바하무트":
        gold = int(gold * 1.05)
        exp = int(exp * 1.10)
    pet.coins += gold
    pet.total_dungeon_clears += 1
    logs += pet.gain_exp(exp)
    logs += pet.gain_affection(6 if pet.species_key == "호랑이" else 4)
    soul = ("soul_normal", "soul_hard", "soul_nightmare", "soul_mythic", "soul_mythic")[tier - 1]
    count = random.randint(1, 3) if tier <= 2 else random.randint(1, 2) if tier <= 4 else random.randint(2, 4)
    inv.add_item(soul, count)
    logs.append(f"혼 +{count}개")
    inv.add_item("armor_stone", (2, 3, 5, 8, 15)[tier - 1])
    if tier >= 3:
        inv.add_item({3: "nightmare_crystal", 4: "mythic_core", 5: "ancient_core"}[tier], random.randint(1, 2))
    if tier == 5 and kills % 10 == 0:
        inv.add_item("ancient_core_" + CORE_IDS[boss], 1)
        logs.append("10회 토벌 전용 핵 +1개")
    armor = {1: "leather_armor", 2: "crystal_armor", 3: "celestial_armor"}.get(tier)
    if tier >= 4:
        armor = {1: "mythic_life_armor", 2: "mythic_celestial_armor", 3: "mythic_dragon_armor", 4: "mythic_gale_armor", 5: "mythic_abyss_armor"}[boss]
    if first or random.random() < 0.25:
        inv.add_armor(armor)
        logs.append("방어구 획득")
    if first and not inv.relics_inventory and not inv.equipped_relic:
        inv.add_relic(pet.species_key)
        logs.append("첫 토벌 종족 보물 획득")
    elif random.random() < 0.15:
        inv.add_relic(pet.species_key)
        logs.append("종족 보물 획득")
    if farming.roll_stone_drop(inv, pet, "relic", min(tier, 4)):
        logs.append("보물 각인석 +1개")
    return f"{pet.name}: +{gold:,}G / +{exp:,} EXP\n" + " · ".join(logs)


def battle(party, boss, tier, choices=None, max_turns=None, rng=None):
    """두 참가자가 같은 보스 HP를 공격한다. 계산 중 외부 입출력은 없다."""
    rng = rng or random
    for pet, inv in party:
        check_entry(pet, boss, tier)
    base = BOSS_DATABASE[boss]
    target = deepcopy(BOSS_STAT_TABLE[tier][boss])
    max_hp = hp = target["hp"]
    fighters, logs = [], []
    for index, (pet, inv) in enumerate(party):
        pet.consume_energy(base["energy_cost"], "raid")
        pet.hunger = max(0, pet.hunger - 20)
        pet.cleanliness = max(0, pet.cleanliness - 20)
        pet.total_adventures += 1
        stats = pet.get_battle_stats(inv)
        fx = effects(inv)
        fx["heal_bonus"] = fx.get("heal_bonus", 0) + stats.get("heal_bonus", 0)
        fx["turn_regen"] = fx.get("turn_regen", 0) + stats.get("regen_hp_pct", 0)
        fx["low_hp_dmg_red"] = fx.get("low_hp_dmg_red", 0) + stats.get("low_hp_dmg_red", 0)
        if pet.species_key == "기린":
            for stat in ("max_hp", "current_hp", "atk", "def", "spd"):
                stats[stat] = int(stats[stat] * (1.08 if stats.get("relic_is_10") else 1.03))
        fighters.append({"index": index, "pet": pet, "inv": inv, "stats": stats, "hp": stats["current_hp"], "shield": 0,
                         "skills": skills(pet), "effects": fx, "cooldowns": {}, "buffs": {}, "debuffs": {},
                         "revived": False, "saved": False, "passive_healed": False, "stunned": False, "burn": 0})
    revived, boss_shield, boss_reflect = False, 0, 0
    boss_buffs, boss_debuffs, phases = {}, {}, set()
    boss_stunned, boss_burn, stacks, warning, ult_used = False, 0, 0, False, False
    boss_cds = {"skill_a": 0, "skill_b": 0, "ultimate": 0}
    patterns = BOSS_SKILLS_DATABASE[boss]
    def progress(turn):
        return {"ongoing": True, "boss": boss, "tier": tier, "turns": turn,
                "boss_hp": hp, "boss_max_hp": max_hp,
                "fighters": [{"name": f["pet"].name, "hp": max(0, f["hp"]), "max_hp": f["stats"]["max_hp"],
                              "cooldowns": f["cooldowns"], "stunned": f["stunned"]} for f in fighters],
                "log": logs[-12:]}
    if max_turns == 0:
        return progress(0)
    # 잡지식: 턴 상한은 회복형 보스와 탱커의 무한 줄다리기를 막아준다.
    for turn in range(1, 101):
        if hp <= 0 or not any(f["hp"] > 0 for f in fighters):
            break
        previous_hp = hp
        boss_buffs = {k: (v, n-1) for k,(v,n) in boss_buffs.items() if n>1}
        boss_debuffs = {k: (v, n-1) for k,(v,n) in boss_debuffs.items() if n>1}
        if boss == 3:
            stacks = min(patterns["trait"]["max_stack_map"][tier], stacks + (2 if tier == 5 and hp/max_hp<=0.25 else 1))
        if boss_burn:
            hp = max(0, hp - int(max_hp * 0.01))
            boss_burn -= 1
        hp = min(max_hp, hp + int(max_hp * boss_buffs.get("regen", (0,0))[0]))
        if tier == 5:
            phase = patterns.get("ancient_phase", {})
            if hp/max_hp <= phase.get("req_hp_pct", 0):
                hp = min(max_hp, hp + int(max_hp * phase.get("regen_ratio", 0)))
                boss_buffs["def"] = (phase.get("def_buff", 0), 2)
            for key, phase in patterns.get("ancient_phases", {}).items():
                if key != "final_pattern" and key not in phases and hp/max_hp <= phase["req_hp_pct"]:
                    phases.add(key)
                    target["atk"] = int(target["atk"] * (1 + phase.get("atk_buff",0)))
                    target["spd"] = int(target["spd"] * (1 + phase.get("spd_buff",0)))
                    logs.append(phase["name"])
        for f in sorted(fighters, key=lambda f: f["stats"]["spd"], reverse=True):
            if f["hp"] <= 0:
                continue
            pet, st, fx = f["pet"], f["stats"], f["effects"]
            f["buffs"] = {k: (v, n - 1) for k, (v, n) in f["buffs"].items() if n > 1}
            f["debuffs"] = {k: (v, n - 1) for k, (v, n) in f["debuffs"].items() if n > 1}
            f["cooldowns"] = {k: max(0, v - 1) for k, v in f["cooldowns"].items()}
            if f["stunned"]:
                f["stunned"] = False
                logs.append(f"{turn}턴 · {pet.name} 행동 불가")
                continue
            kind = choices[turn-1][f["index"]] if choices is not None else "ultimate" if turn >= 3 and not f["cooldowns"].get("ultimate") else "unique" if not f["cooldowns"].get("unique") else "basic2" if turn % 2 == 0 else "basic1"
            if kind not in f["skills"] or f["cooldowns"].get(kind, 0) or (kind == "ultimate" and turn < 3):
                raise ValueError("사용할 수 없는 스킬입니다. 쿨타임을 확인해 주세요.")
            sk = f["skills"][kind]
            f["cooldowns"][kind] = sk.get("cooldown", 0)
            duration = sk.get("duration", 2)
            if sk.get("cleanse"):
                f["debuffs"].clear()
                f["burn"] = 0
            for key, source in (("resist","resist_buff"),("dodge","buff_dodge"),("double","buff_double"),("crit","buff_crit"),("reflect","reflect_pct"),("regen","regen_turn_pct"),("penalty","penalty_dmg_taken"),("pen_def","pen_def")):
                if source in sk:
                    f["buffs"][key] = (sk[source], duration)
            for stat in ("atk", "def", "spd"):
                debuff = sk.get("debuff_"+stat, sk.get("debuff_all", 0))
                if stat == "def":
                    debuff = max(debuff, sk.get("debuff_enemy_def", 0))
                if debuff:
                    boss_debuffs[stat] = (debuff, duration)
            if rng.random() < sk.get("debuff_atk_chance", 0):
                boss_debuffs["atk"] = (0.1, 2)
            if rng.random() < sk.get("slow_chance", 0):
                boss_debuffs["spd"] = (0.15, 2)
            if rng.random() < sk.get("stun_chance", 0):
                boss_stunned = True
            if rng.random() < sk.get("burn_chance", 0):
                boss_burn = duration
            for stat in ("atk", "def", "spd"):
                value = sk.get("buff_" + stat, sk.get("buff_all", 0))
                if value:
                    f["buffs"][stat] = (value, duration)
            if sk.get("dmg_reduction"):
                f["buffs"]["reduction"] = (sk["dmg_reduction"] * (1 + fx.get("shield_bonus", 0)), duration)
            f["shield"] += int(st["max_hp"] * sk.get("shield_pct", 0) * (1 + fx.get("shield_bonus", 0)))
            healing = sk.get("heal_hp_pct", 0)
            if f["hp"] / st["max_hp"] <= 0.3:
                healing += sk.get("clutch_heal", 0)
            f["hp"] = min(st["max_hp"], f["hp"] + int(st["max_hp"] * healing * (1 + fx.get("heal_bonus", 0))))
            if pet.species_key == "기린" and kind == "ultimate":
                for ally in fighters:
                    if ally["hp"] > 0:
                        ally["hp"] = min(ally["stats"]["max_hp"], ally["hp"] + int(ally["stats"]["max_hp"] * 0.15 * farming.stage_skill_profile(pet.stage)["effect_mult"] * (1 + fx.get("heal_bonus", 0))))
            ratio = f["hp"] / st["max_hp"]
            speed = st["spd"] * (1 + f["buffs"].get("spd", (0, 0))[0])
            speed *= 1 - f["debuffs"].get("spd", (0,0))[0]
            enemy_speed = target["spd"] * (1 + boss_buffs.get("spd", (0,0))[0]) * (1 - boss_debuffs.get("spd", (0,0))[0])
            bonus = fx.get("boss_dmg", 0) + fx.get("basic_dmg" if kind.startswith("basic") else kind + "_dmg", 0)
            bonus += fx.get("first3_dmg", 0) if turn <= 3 else 0
            bonus += fx.get("high_hp_dmg", 0) if ratio >= 0.5 else 0
            bonus += fx.get("low_hp_dmg", 0) if ratio <= 0.3 else 0
            bonus += fx.get("spd_adv_dmg", 0) + sk.get("spd_bonus", 0) + sk.get("first_strike_bonus", 0) if speed > enemy_speed else 0
            bonus += sk.get("execute_bonus", 0) if hp/max_hp <= 0.3 else 0
            if pet.species_key == "호랑이" and ratio >= 0.7:
                bonus += 0.06
            if pet.species_key == "늑대" and speed > enemy_speed:
                bonus += 0.16 if st.get("relic_is_10") else 0.06
            if pet.species_key == "드래곤" and ratio <= 0.4:
                bonus += 0.08
            if pet.species_key == "구미호":
                bonus += 0.07
            if pet.species_key == "바하무트":
                bonus += 0.18 if st.get("relic_is_10") else 0.08
            if turn == 1:
                bonus += st.get("first_hit_bonus", 0)
                if pet.species_key == "그리핀" and st.get("relic_is_10"):
                    bonus += 0.2
            attack = st["atk"] * (1 + f["buffs"].get("atk", (0, 0))[0])
            attack *= 1 - f["debuffs"].get("atk", (0,0))[0]
            if st.get("personality_trait") == "brave_crisis" and ratio <= 0.5:
                attack *= 1.1
            if st.get("personality_trait") == "early_burst":
                attack *= 1.15 if turn <= 3 else 0.95
            if pet.species_key == "드래곤" and st.get("relic_is_10") and ratio <= 0.3:
                attack *= 1.2
            extra = fx.get("extra_hit", 0) + sk.get("extra_hit_chance", 0) + sk.get("double_hit_chance", 0) + f["buffs"].get("double", (0,0))[0]
            if st.get("effect") == "double_strike":
                extra += min(0.4, speed/(speed+900))
            hits = sk.get("hits", 1) + int(rng.random() < min(1, extra))
            if sk.get("speed_diff_hit") and speed > enemy_speed * (1+sk["speed_diff_hit"]):
                hits += 1
            damage = 0
            for hit_index in range(hits):
                critical = rng.random() < min(0.7, st["crit"] / (st["crit"] + 900) + sk.get("crit_bonus", 0) + f["buffs"].get("crit", (0,0))[0] + (0.15 if st.get("effect")=="crit" else 0))
                mult = 2 + fx.get("crit_dmg", 0) + (0.2 if st.get("personality_trait")=="calm_crit" else 0) if critical else 1
                enemy_def = target["def"] * (1+boss_buffs.get("def",(0,0))[0]) * (1-boss_debuffs.get("def",(0,0))[0])
                penetration = min(0.8, max(sk.get("pen_def", 0), f["buffs"].get("pen_def",(0,0))[0]))
                hit = max(0, int((attack * sk.get("atk_ratio", 0) - enemy_def * 0.35 * (1 - penetration)) * mult * (1 + bonus) * rng.uniform(0.9, 1.1)))
                if speed > enemy_speed and hit_index == hits-1:
                    hit = int(hit * (1+sk.get("spd_finisher",0)))
                if critical:
                    hit += int(attack * sk.get("crit_extra_atk", 0))
                    if pet.species_key == "호랑이" and st.get("relic_is_10") and rng.random()<0.15:
                        hit = int(hit*1.5)
                if boss == 1 and tier >= 4 and hit < max_hp * 0.01:
                    hit = 0
                if boss == 5 and attack < target["def"] * 0.6:
                    hit = 0
                elif boss == 5 and attack < target["def"] * 0.8:
                    hit //= 2
                damage += hit
            damage = int(damage * (1 - boss_shield))
            hp = max(0, hp - damage)
            f["hp"] -= int(damage * boss_reflect)
            steal = sk.get("lifesteal_pct", 0) + (0.18 if st.get("effect") == "lifesteal" else 0)
            if pet.species_key == "구미호" and st.get("relic_is_10"):
                steal *= 1.5
            if f["hp"] > 0:
                f["hp"] = min(st["max_hp"], f["hp"] + int(min(st["max_hp"] * 0.2, damage * steal * (1 + fx.get("lifesteal", 0))) * (1 + fx.get("heal_bonus", 0))))
            logs.append(f"{turn}턴 · {pet.name} / {sk['name']} · {damage:,} 피해 · 보스 {hp:,}/{max_hp:,}")
            if hp <= 0:
                break
        if hp <= 0:
            if tier >= 4 and boss in (1, 3, 5) and not revived:
                revived = True
                hp = int(max_hp * (1 if boss == 5 else 0.5))
                target["atk"] = int(target["atk"] * 1.25)
                logs.append("보스가 각성하여 다시 일어났습니다!")
            else:
                break
        boss_cds = {k: max(0, v - 1) for k, v in boss_cds.items()}
        move = choose_boss_action(boss, tier, hp/max_hp, turn, boss_cds["skill_a"], boss_cds["skill_b"], ult_used, warning, {"hellfire_stacks":stacks}, rng=rng)
        if boss_stunned:
            boss_stunned = False
            move = "stunned"
        if move == "warning_ult":
            warning = True
            logs.append(f"{base['name']}의 궁극기 예고!")
        elif move == "ultimate":
            warning, ult_used = False, True
        pattern = patterns.get(move, {})
        if boss == 5 and tier == 5 and hp/max_hp<=0.1 and "final_pattern" not in phases:
            phases.add("final_pattern")
            pattern = patterns["ancient_phases"]["final_pattern"]
        boss_cds[move] = pattern.get("cooldown", 3)
        hp = min(max_hp, hp + int(max_hp * pattern.get("heal_ratio", 0)))
        hp = min(max_hp, hp + int(max(0, previous_hp-hp)*pattern.get("rewind_ratio",0)))
        for key, source in (("atk","atk_buff"),("def","def_buff"),("spd","spd_buff"),("shield","dmg_red"),("reflect","reflect_ratio"),("regen","regen_ratio")):
            if source in pattern:
                boss_buffs[key] = (pattern[source], pattern.get("duration",pattern.get("regen_turns",3)))
        boss_shield = min(0.8, boss_buffs.get("shield", (0,0))[0])
        boss_reflect = boss_buffs.get("reflect", (0,0))[0]
        if boss == 2:
            boss_reflect = max(boss_reflect, patterns["trait"]["reflect_map"][tier])
            if move == "ultimate":
                boss_buffs["reflect"] = (pattern["reflect_ratio_map"][tier],2)
                boss_reflect = pattern["reflect_ratio_map"][tier]
        stacks += pattern.get("stack_add",0)
        alive = [f for f in fighters if f["hp"] > 0]
        if not alive:
            break
        victims = [] if move in ("stunned","warning_ult") else alive if move == "ultimate" or pattern.get("burn_turns") else [rng.choice(alive)]
        for f in victims:
            st, fx = f["stats"], f["effects"]
            resist = min(0.9, st.get("armor_resist",0)+f["buffs"].get("resist",(0,0))[0])
            if rng.random() < pattern.get("stun_chance_map",{}).get(tier,0)*(1-resist):
                f["stunned"] = True
            for stat, value in (("spd", pattern.get("slow_rate",0)),("def",pattern.get("def_shred",0))):
                chance = pattern.get("slow_chance",1) if stat=="spd" else pattern.get("shred_chance",1)
                if value and rng.random()<chance*(1-resist):
                    f["debuffs"][stat] = (value, pattern.get("slow_turns",pattern.get("shred_turns",2)))
            for stat in ("atk","def","spd"):
                value = pattern.get("all_stat_debuff",pattern.get("debuff_val",0))
                if value:
                    f["debuffs"][stat] = (value*(1-resist),pattern.get("duration",2))
            if pattern.get("burn_turns") or rng.random()<pattern.get("burn_chance",0)*(1-resist):
                f["burn"] = pattern.get("burn_turns",2)
            if tier==5 and boss==4 and hp/max_hp<=0.3 and rng.random()<0.2:
                f["cooldowns"] = {k:v+1 for k,v in f["cooldowns"].items()}
            dodge = f["buffs"].get("dodge",(0,0))[0] + (0.1 if st.get("personality_trait")=="dodge_boost" else 0)
            if rng.random()<dodge:
                logs.append(f"{f['pet'].name} 회피!")
                continue
            reduction = fx.get("dmg_red", 0) + fx.get("boss_dmg_red", 0) + st.get("armor_dmg_red", 0) + f["buffs"].get("reduction", (0, 0))[0]
            reduction += fx.get("first3_dmg_red", 0) if turn <= 3 else 0
            reduction += fx.get("low_hp_dmg_red", 0) if f["hp"] <= st["max_hp"] * 0.3 else 0
            if st.get("effect")=="shield":
                reduction += 0.25
            if f["pet"].species_key=="현무":
                reduction += 0.05
            if f["pet"].species_key=="사자" and st.get("relic_is_10") and f["hp"]<=st["max_hp"]*0.5:
                reduction += 0.1
            critical = rng.random() < target.get("crit", 100) / (target.get("crit", 100) + 900)
            attack = target["atk"]*(1+boss_buffs.get("atk",(0,0))[0])*(1-boss_debuffs.get("atk",(0,0))[0])
            if boss==3:
                attack *= 1+stacks*pattern.get("bonus_per_stack_map",{}).get(tier,0.03)
            if target["spd"]>st["spd"]:
                attack *= 1+pattern.get("spd_bonus",0)
            defence = st["def"]*(1+f["buffs"].get("def",(0,0))[0])*(1-f["debuffs"].get("def",(0,0))[0])
            if f["hp"]<=st["max_hp"]*0.3 and f["pet"].species_key=="현무" and st.get("relic_is_10"):
                defence *= 1.2
            raw = max(0, attack * pattern.get("ratio", 0) - defence * 0.35 * (1-pattern.get("def_ignore",0)))
            damage = int(raw * (2 * (1 - fx.get("crit_dmg_red", 0)) if critical else 1) * (1 - min(0.85, reduction)))
            if rng.random() < fx.get("half_dmg_chance", 0):
                damage //= 2
            if st.get("personality_trait")=="indomitable" and rng.random()<0.2:
                damage //= 2
            damage = int(damage*(1+f["buffs"].get("penalty",(0,0))[0]))
            if pattern.get("extra_turn") or rng.random()<pattern.get("extra_turn_chance_map",{}).get(tier,0):
                damage += int(max(5,attack-defence*0.35)*(1-min(0.85,reduction)))
            absorbed = min(f["shield"], damage)
            f["shield"] -= absorbed
            f["hp"] -= damage - absorbed
            hp = max(0,hp-int((damage-absorbed)*f["buffs"].get("reflect",(0,0))[0]))
            if f["hp"]<=0 and f["pet"].species_key=="불사조" and st.get("relic_is_10") and not f["saved"]:
                f["saved"] = True
                f["hp"] = 1
            if f["hp"] <= 0 and f["pet"].species_key == "불사조" and not f["revived"]:
                f["revived"] = True
                f["hp"] = int(st["max_hp"] * 0.25)
            logs.append(f"{base['name']} / {pattern.get('name', '기본 공격')} → {f['pet'].name} {damage - absorbed:,} 피해")
        for f in fighters:
            if f["hp"] > 0:
                st, fx = f["stats"], f["effects"]
                if f["burn"]:
                    f["hp"] -= int(st["max_hp"]*0.02*(1-st.get("burn_dmg_red",0)))
                    f["burn"] -= 1
                regen = fx.get("turn_regen",0)+f["buffs"].get("regen",(0,0))[0]
                regen += 0.015 if st.get("effect")=="hp_regen" else 0
                regen += 0.02 if st.get("personality_trait")=="gentle_regen" else 0
                if f["pet"].species_key=="불사조" and 0<f["hp"]<=st["max_hp"]*0.3 and not f["passive_healed"]:
                    f["passive_healed"] = True
                    regen += 0.08
                if f["hp"]>0:
                    f["hp"] = min(st["max_hp"], f["hp"] + int(st["max_hp"] * regen * (1 + fx.get("heal_bonus", 0))))
        if max_turns is not None and turn >= max_turns and hp > 0 and any(f["hp"] > 0 for f in fighters):
            return progress(turn)
    won = hp <= 0 and any(f["hp"] > 0 for f in fighters)
    summaries = []
    for f in fighters:
        pet, inv = f["pet"], f["inv"]
        if won:
            pet.health = max(10, int(max(0, f["hp"]) / f["stats"]["max_hp"] * 100))
            summaries.append(reward(pet, inv, boss, tier))
        else:
            pet.stamina = max(0, pet.stamina - 20) if tier == 1 else 0
            pet.health = max(10, pet.health - (10 if tier == 1 else 20))
            pet.happiness = max(0, pet.happiness - (5 if tier == 1 else 25))
            if tier >= 3 and f["hp"] <= 0:
                if inv.items.get("life_gem", 0):
                    inv.remove_item("life_gem", 1)
                elif rng.random() < pet.calculate_injury_rate(tier)[0]:
                    pet.is_critically_injured = True
                    pet.health = 1
            summaries.append(f"{pet.name}: 패배, 건강 {pet.health} / 기력 {pet.stamina}")
    return {"won": won, "boss": boss, "tier": tier, "turns": turn, "log": logs,
            "message": ("토벌 성공!\n" if won else "토벌 실패.\n") + "\n".join(summaries)}
