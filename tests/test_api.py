import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from shisu.api.main import create_app
from shisu.infrastructure.database import Database
from shisu.application.game import act, new_save

ACCOUNTS = {f"player{i}":{"name":f"테이머{i}","code":str(i)*32} for i in (1,2)}
HEADERS = {"X-Shinsu-Client":"web"}


def login(client, user="player1"):
    return client.post('/api/login',json={"account":user,"code":ACCOUNTS[user]["code"]},headers=HEADERS)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path/'save.sqlite3',ACCOUNTS,False)) as c:
        yield c


def test_로그인_필수와_타인_주소_차단(client):
    names=client.get('/api/account-names')
    assert names.json()=={'player1':'테이머1','player2':'테이머2'}
    assert client.get('/api/me').status_code == 401
    assert client.get('/api/players/player2').status_code == 404
    response=login(client)
    assert response.status_code==200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/api/me').json()['nickname']=='테이머1'
    assert client.post('/api/logout',headers=HEADERS).status_code==200
    assert client.get('/api/me').status_code==401


def test_전투_스탯_UI_정적_자원(client):
    script=client.get('/assets/app.js').text
    style=client.get('/assets/expansion.css').text
    assert 'statPentagon' in script
    assert '입장 레벨 Lv.' in script
    assert "hp:'#155b3a'" in script
    assert '.stat-layout' in style


def test_잘못된_코드와_사이트간_요청_차단(client):
    assert client.post('/api/login',json={'account':'player1','code':'wrong'},headers=HEADERS).status_code==401
    assert client.post('/api/login',json={'account':'player1','code':'1'*32}).status_code==403


def test_두번째_테이머_한명만_초대_가입하고_비밀번호로_로그인(tmp_path):
    path=tmp_path/'save.sqlite3'
    signup={'nickname':'마왕요니 친구','password':'safe-password-123','invite_code':ACCOUNTS['player2']['code']}
    with TestClient(create_app(path,ACCOUNTS,False)) as client:
        assert client.get('/api/signup-status').json()=={'available':True}
        wrong={**signup,'invite_code':'wrong'}
        assert client.post('/api/signup',json=wrong,headers=HEADERS).status_code==401
        response=client.post('/api/signup',json=signup,headers=HEADERS)
        assert response.status_code==200
        assert client.get('/api/me').json()['nickname']=='마왕요니 친구'
        assert client.get('/api/account-names').json()['player2']=='마왕요니 친구'
        assert client.post('/api/logout',headers=HEADERS).status_code==200
        assert login(client,'player2').status_code==401
        assert client.post('/api/login',json={'account':'player2','code':signup['password']},headers=HEADERS).status_code==200
        assert client.post('/api/signup',json=signup,headers=HEADERS).status_code==409
    with TestClient(create_app(path,ACCOUNTS,False)) as client:
        assert client.get('/api/signup-status').json()=={'available':False}
        assert client.post('/api/login',json={'account':'player2','code':signup['password']},headers=HEADERS).status_code==200
        assert client.get('/api/me').json()['nickname']=='마왕요니 친구'


def test_신수_이름_변경_검증_및_영구저장(client):
    login(client)
    renamed=client.post('/api/actions',json={'action':'rename','request_id':str(uuid4()),'name':'  달빛이  '},headers=HEADERS)
    assert renamed.status_code==200
    assert renamed.json()['player']['pet']['name']=='달빛이'
    assert renamed.json()['player']['pet']['is_custom_name'] is True
    assert client.get('/api/me').json()['pet']['name']=='달빛이'
    for name in ('   ','가'*16):
        response=client.post('/api/actions',json={'action':'rename','request_id':str(uuid4()),'name':name},headers=HEADERS)
        assert response.status_code in (409,422)
        assert client.get('/api/me').json()['pet']['name']=='달빛이'


def test_Lv1_초기_신수_리롤은_무료_3회만_가능(client):
    login(client)
    before=client.get('/api/me').json()
    responses=[client.post('/api/actions',json={'action':'pet_reroll','request_id':str(uuid4())},headers=HEADERS) for _ in range(3)]
    assert all(response.status_code==200 for response in responses)
    after=responses[-1].json()['player']
    assert after['initial_rerolls_used']==3
    assert after['pet']['level']==1
    assert after['pet']['coins']==before['pet']['coins']
    assert after['inventory']['equipped_relic']=={'species':after['pet']['species_key'],'level':0}
    retry=client.post('/api/actions',json={'action':'pet_reroll','request_id':str(uuid4())},headers=HEADERS)
    assert retry.status_code==409
    assert client.get('/api/me').json()['pet']==after['pet']
    level_two=new_save()
    level_two['pet']['level']=2
    with pytest.raises(ValueError,match='Lv.1'):
        act(level_two,{'action':'pet_reroll'})


def test_던전_보상과_중복_요청(client):
    login(client)
    before=client.get('/api/me').json()
    body={'action':'dungeon','request_id':str(uuid4())}
    first=client.post('/api/actions',json=body,headers=HEADERS)
    assert first.status_code==200, first.text
    second=client.post('/api/actions',json=body,headers=HEADERS)
    assert second.json()['player']['revision']==first.json()['player']['revision']
    after=client.get('/api/me').json()
    assert after['pet']['coins']>before['pet']['coins']
    assert sum(sum(levels.values()) for levels in after['inventory']['gems'].values())==1
    body['action']='train'
    assert client.post('/api/actions',json=body,headers=HEADERS).status_code==409


def test_두_계정_분리_재시작_유지(tmp_path):
    path=tmp_path/'save.sqlite3'
    with TestClient(create_app(path,ACCOUNTS,False)) as c:
        login(c)
        c.post('/api/actions',json={'action':'dungeon','request_id':str(uuid4())},headers=HEADERS)
        first=c.get('/api/me').json()
        login(c,'player2')
        second=c.get('/api/me').json()
        assert second['revision']==0
        assert second['pet']['coins']==1000
    with TestClient(create_app(path,ACCOUNTS,False)) as c:
        login(c)
        restored=c.get('/api/me').json()
        assert restored['pet']==first['pet']
        assert restored['inventory']==first['inventory']


def test_동시_중복_요청은_한번만_반영(tmp_path):
    db=Database(tmp_path/'save.sqlite3')
    db.get('player1')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:db.action('player1','same',{'action':'dungeon','dungeon':1,'tier':1}),range(4)))
    assert all(r==results[0] for r in results)
    assert db.get('player1')['revision']==1


def test_저장_실패시_보상과_재료_롤백(tmp_path):
    db=Database(tmp_path/'save.sqlite3')
    before=db.get('player1')
    with db.connect() as sql:
        sql.execute("CREATE TRIGGER fail_save BEFORE UPDATE ON players BEGIN SELECT RAISE(ABORT,'실패'); END")
    with pytest.raises(sqlite3.IntegrityError):
        db.action('player1','test',{'action':'dungeon','dungeon':1,'tier':1})
    assert db.get('player1')==before


def test_장착_보석을_합성으로_소모하지_않음(tmp_path):
    d=Database(tmp_path/'save.sqlite3').get('player1')
    d['inventory']['gems']['hp']['1']=2
    d['inventory']['equipped_gems']['hp']=1
    with pytest.raises(ValueError):
        act(d,{'action':'synthesize','gem':'hp','level':1})
    assert d['inventory']['gems']['hp']['1']==2


def test_백업_복원(tmp_path):
    db=Database(tmp_path/'save.sqlite3')
    before=db.get('player1')
    db.backup(tmp_path/'backup.sqlite3')
    assert Database(tmp_path/'backup.sqlite3').get('player1')==before


def test_관리자_종족변경은_진행도와강화도를_보존(tmp_path):
    db = Database(tmp_path/'save.sqlite3')
    before = db.get('player2')
    before['pet'].update(name='내 신수', is_custom_name=True, level=17, coins=54321, element='질풍')
    before['inventory']['equipped_relic'] = {'species': before['pet']['species_key'], 'level': 6}
    with db.connect() as sql:
        sql.execute('UPDATE players SET data=? WHERE id=?', (json.dumps(before, ensure_ascii=False), 'player2'))

    db.change_species('player2', '기린')
    after = db.get('player2')

    assert after['pet']['species_key'] == '기린'
    assert after['pet']['name'] == '내 신수'
    assert after['pet']['level'] == 17 and after['pet']['coins'] == 54321
    assert after['pet']['element'] == '질풍'
    assert after['inventory']['equipped_relic'] == {'species': '기린', 'level': 6}
    assert after['revision'] == before['revision'] + 1


def test_화면과_서비스워커(client):
    assert client.get('/').status_code==200
    assert client.get('/sw.js').status_code==200
    assert client.get('/assets/app.js').status_code==200
    assert client.get('/api/health').json()['status']=='ok'


def test_모든_종족_성장_이미지_제공(client):
    species=('tiger','lion','wolf','dragon','phoenix','turtle','fox','griffin','kirin','bahamut')
    for name in species:
        for stage in range(1,5):
            response=client.get(f'/assets/game-assets/species/{name}/stage{stage}.webp')
            assert response.status_code==200
            assert response.headers['content-type']=='image/webp'
            assert len(response.content)>10000


def test_서버_설정_없으면_시작_차단(tmp_path):
    with pytest.raises(RuntimeError):
        with TestClient(create_app(tmp_path/'save.sqlite3',{},False)):
            pass


def test_미래_저장_버전을_초기화하지_않음(tmp_path):
    db=Database(tmp_path/'save.sqlite3')
    data=db.get('player1')
    data['save_version']=99
    with db.connect() as sql:
        sql.execute('UPDATE players SET data=? WHERE id=?',(json.dumps(data),'player1'))
    with pytest.raises(ValueError):
        db.get('player1')
    with db.connect() as sql:
        stored=json.loads(sql.execute('SELECT data FROM players WHERE id=?',('player1',)).fetchone()[0])
    assert stored['save_version']==99


def test_운영_쿠키에_secure_설정(tmp_path):
    with TestClient(create_app(tmp_path/'save.sqlite3',ACCOUNTS,True),base_url='https://testserver') as c:
        assert 'Secure' in login(c).headers['set-cookie']
        assert c.get('/api/me').status_code==200


def test_로그인_시도_횟수_제한(client):
    for _ in range(20):
        assert client.post('/api/login',json={'account':'player1','code':'wrong'},headers=HEADERS).status_code==401
    assert login(client).status_code==429
