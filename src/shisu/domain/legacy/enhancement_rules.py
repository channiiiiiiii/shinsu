"""강화 판정과 화면 미리보기가 공유하는 실제 비용과 확률."""
RELIC_RATES = (1, 1, 1, .9, .8, .7, .6, .5, .35, .2)
ARMOR_RATES = (1, 1, 1, .95, .9, .85, .75, .65, .55, .45, .35, .25, .18, .12, .08)
STAR_GOLD = (30000, 50000, 70000, 90000, 120000)
CORES = ('ancient_core_ent', 'ancient_core_dragon', 'ancient_core_ifrit',
         'ancient_core_guardian', 'ancient_core_omega', 'ancient_core')


def relic_cost(level):
    return ((level + 1) * 2, level + 1, {8: 1, 9: 2}.get(level, 0),
            {8: 25000, 9: 35000}.get(level, (level + 1) * 2500))


def armor_cost(level):
    special = {10: (12, 6, 1, 0, 20000), 11: (15, 8, 2, 0, 25000),
               12: (18, 10, 3, 0, 30000), 13: (22, 12, 0, 2, 40000),
               14: (25, 15, 0, 4, 50000)}
    return special.get(level, (level + 1, max(1, (level + 1) // 2), 0, 0, (level + 1) * 1500))
