"""표시용 스탯 출처의 실제 전투 계산 일치 검증."""
from shisu.application.game import new_save, view


def test_모든_스탯_출처의_합은_실제_전투_수치():
    data = new_save()
    data['pet']['hunger'] = 20
    data['pet']['potential_growth']['atk'] = .09
    inventory = data['inventory']
    inventory['equipped_armor'] = {'armor_id':'leather_armor','level':2,'stars':0}
    inventory['equipped_relic'] = {'species':data['pet']['species_key'],'level':2}
    inventory['armor_engravings'][0] = {'option':'def','value':5,'grade':'normal'}
    inventory['gems']['atk']['2'] = 1
    inventory['equipped_gems']['atk'] = 2

    result = view(data, '검증')
    for kind, field in (('hp','max_hp'),('atk','atk'),('def','def'),('spd','spd'),('crit','crit')):
        rows = result['stat_breakdown'][kind]
        assert sum(row['value'] for row in rows) == result['stats'][field]
        assert [row['label'] for row in rows] == ['신수 기본·성장','잠재 성장','컨디션','방어구','보물','각인','보석']
    atk = {row['label']:row['value'] for row in result['stat_breakdown']['atk']}
    assert atk['잠재 성장'] > 0
    assert atk['컨디션'] < 0
    assert atk['보석'] == 10
    defence = {row['label']:row['value'] for row in result['stat_breakdown']['def']}
    assert defence['방어구'] > 0
    assert defence['각인'] == 5
