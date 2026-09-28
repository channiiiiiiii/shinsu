"""개인 기록의 인증·계정 격리·영구 저장을 검증한다."""
from datetime import timedelta

from fastapi.testclient import TestClient
from shisu.api.main import create_app
from shisu.api.diet import DietStore, today

ACCOUNTS={f'player{i}':{'name':f'사용자{i}','code':str(i)*32} for i in (1,2)}
HEADERS={'X-Shinsu-Client':'web'}


def test_authenticated_storage(tmp_path):
    app=create_app(tmp_path/'game.db',ACCOUNTS,False)
    day=(today()-timedelta(days=today().weekday())).isoformat()
    with TestClient(app) as client:
        assert client.get('/diet').status_code==401
        assert client.get('/api/diet/settings').status_code==401
        client.post('/api/login',json={'account':'player2','code':'2'*32},headers=HEADERS)
        assert client.patch('/api/diet/day/'+day,json={'weight':89.4}).status_code==403
        result=client.patch('/api/diet/day/'+day,json={'weight':89.4,'water_ml':500,'steps':9200,'breakfast_protein_done':True,'multivitamin_done':True},headers=HEADERS)
        assert result.status_code==200
        exercise=result.json()['workouts'][0]['name']
        assert client.patch(f'/api/diet/workouts/{day}/{exercise}',json={'completed':True,'weight':60,'reps':[10,9]},headers=HEADERS).status_code==200
        before=client.get('/api/diet/day/'+day).json()
        assert before['log']['weight']==89.4 and before['percent']>0
        backup=client.get('/api/diet/backup').json()
        assert client.post('/api/diet/restore',json=backup,headers=HEADERS).status_code==200
        assert client.get('/api/diet/day/'+day).json()==before
        bad={**backup,'daily':[{'date':day,'log':{'weight':-1}}]}
        assert client.post('/api/diet/restore',json=bad,headers=HEADERS).status_code==422
        assert client.get('/api/diet/day/'+day).json()==before
        client.post('/api/login',json={'account':'player1','code':'1'*32},headers=HEADERS)
        assert client.get('/api/diet/day/'+day).status_code==403
        assert client.get('/diet').status_code==403
        assert client.get('/api/diet/backup').status_code==403
        assert client.post('/api/diet/restore',json=backup,headers=HEADERS).status_code==403
    store=DietStore(tmp_path/'diet.db')
    assert store.day('player2',day)==before


def test_weekend_future_and_averages(tmp_path):
    store=DietStore(tmp_path/'diet.db'); now=today()
    saturday=now-timedelta(days=(now.weekday()-5)%7)
    assert store.day('player1',saturday.isoformat())['workouts']==[]
    assert store.day('player1',saturday.isoformat())['total']==13
    for i in range(14):
        store.patch('player1',(now-timedelta(days=i)).isoformat(),{'weight':90+i/10})
    stats=store.stats('player1')
    assert stats['average']==90.3 and stats['previous']==91
    assert stats['change']==-0.7 and stats['average_count']==7
    app=create_app(tmp_path/'game.db',ACCOUNTS,False)
    with TestClient(app) as client:
        client.post('/api/login',json={'account':'player2','code':'2'*32},headers=HEADERS)
        future=(now+timedelta(days=1)).isoformat()
        assert client.get('/api/diet/day/'+future).json()['future']
        assert client.patch('/api/diet/day/'+future,json={'weight':89},headers=HEADERS).status_code==422
        assert client.patch('/api/diet/day/'+now.isoformat(),json={'water_ml':-250},headers=HEADERS).status_code==422
        assert client.patch('/api/diet/day/invalid',json={},headers=HEADERS).status_code==422
        settings=client.get('/api/diet/settings').json()
        settings['goal_weight']=75
        assert client.put('/api/diet/settings',json=settings,headers=HEADERS).status_code==200
        assert client.get('/api/diet/settings').json()['goal_weight']==75
