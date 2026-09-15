"""미리보기와 실제 판정·소모·중복 요청의 일치 검증."""
from copy import deepcopy
import json
import pytest
from shisu.application.game import new_save, objects, act, view
from shisu.application.enhancement import quote
from shisu.domain.legacy.pet import Pet
from shisu.domain.legacy.enhancement_rules import CORES
from shisu.infrastructure.database import Database


def funded():
    data = new_save()
    data['pet']['coins'] = 1000000
    data['inventory']['equipped_relic'] = {'species': data['pet']['species_key'], 'level': 0}
    data['inventory']['equipped_armor'] = {'armor_id': 'mythic_dragon_armor', 'level': 0, 'stars': 0}
    data['inventory']['items'].update({key: 1000 for key in ('stone', 'armor_stone', 'relic_essence', 'nightmare_crystal', 'mythic_core', *CORES)})
    return data


@pytest.mark.parametrize('action,level', [('enhance_relic', n) for n in range(10)] + [('enhance_armor', n) for n in range(15)] + [('ascend_armor', n) for n in range(5)])
@pytest.mark.parametrize('roll', [0, .9999])
def test_견적과_실제강화_성공실패_일치(monkeypatch, action, level, roll):
    monkeypatch.setattr(Pet, 'get_relic_max_level', lambda self: 10)
    monkeypatch.setattr('shisu.domain.legacy.shop.random.random', lambda: roll)
    data = funded()
    key = 'equipped_relic' if action == 'enhance_relic' else 'equipped_armor'
    data['inventory'][key]['level'] = 15 if action == 'ascend_armor' else level
    if action == 'ascend_armor':
        data['inventory'][key]['stars'] = level
    pet, inv = objects(data)
    before = deepcopy(data)
    q = quote(pet, inv, action)
    assert q['available']
    assert data == before
    result, _ = act(data, {'action': action})
    receipt = result['last_enhancement']
    assert receipt['success'] == (roll < q['rate'])
    assert result['pet']['coins'] == data['pet']['coins'] - q['materials'][-1]['required']
    stats = view(result, '검증')['stats']
    assert receipt['after'] == {key: stats[key] for key in q['before']}
    assert receipt['after'] == (q['after'] if receipt['success'] else q['before'])
    assert result['inventory'][key]['level' if action != 'ascend_armor' else 'stars'] == level + int(receipt['success'])
    assert data == before


def test_실패재전송_한번만소모_부족시무변경(tmp_path, monkeypatch):
    monkeypatch.setattr('shisu.domain.legacy.shop.random.random', lambda: .9999)
    data = funded()
    data['inventory']['equipped_armor']['level'] = 14
    db = Database(tmp_path/'save.sqlite3')
    with db.connect() as sql:
        sql.execute('INSERT INTO players VALUES (?,?)', ('player1', json.dumps(data)))
    first = db.action('player1', 'one', {'action': 'enhance_armor'})
    second = db.action('player1', 'one', {'action': 'enhance_armor'})
    assert first == second
    saved = db.get('player1')
    assert saved['pet']['coins'] == 950000
    assert saved['inventory']['items']['mythic_core'] == 996
    assert saved['inventory']['items']['relic_essence'] == 985
    assert saved['inventory']['items']['armor_stone'] == 975
    assert not saved['last_enhancement']['success']
    data['pet']['coins'] = 0
    pet, inv = objects(data)
    assert not quote(pet, inv, 'enhance_armor')['available']
    snapshot = deepcopy(data)
    with pytest.raises(ValueError):
        act(data, {'action': 'enhance_armor'})
    assert data == snapshot


def test_각성확정_최대와미장착():
    data = funded()
    data['inventory']['equipped_armor'].update(level=15, stars=2)
    pet, inv = objects(data)
    q = quote(pet, inv, 'ascend_armor')
    assert q['rate'] == 1 and q['bonus_after'] == 18
    assert q['materials'][-1]['required'] == 70000
    assert q['materials'][0]['required'] == 1
    inv.equipped_armor['stars'] = 5
    assert not quote(pet, inv, 'ascend_armor')['available']
    inv.equipped_relic = None
    assert not quote(pet, inv, 'enhance_relic')['available']
