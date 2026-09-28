"""기존 인증과 영구 디스크를 사용하는 개인 체크리스트."""
import copy
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

ITEMS = {
    'breakfast_protein_done': '테이크핏 내 몸에 핏한 단백질 플랜 맥스 딸기맛 1병',
    'breakfast_fruit_done': 'Dole 냉동 파인애플 100~150g',
    'lunch_done': '점심 일반식 · 약 700~850 kcal', 'lunch_protein_done': '단백질 반찬 챙기기',
    'multivitamin_done': '종합비타민 1알', 'omega3_done': '오메가3 1알',
    'dinner_rice_done': '오뚜기 발아흑미 즉석잡곡밥 210g',
    'dinner_chicken_done': '굽네 크리스피 닭가슴살 고추바사삭 1팩',
    'dinner_extra_chicken_done': '추가 닭가슴살 1팩 · 선택',
    'dinner_broccoli_done': '냉동 브로콜리 150g',
    'magnesium_done': '종근당건강 칼슘·마그네슘·비타민D·아연 2알',
}
ROUTINES = [
    [('벤치프레스',4,'6~10회'),('인클라인 덤벨프레스',3,'8~12회'),('체스트프레스 머신',3,'10~12회'),('케이블 플라이',3,'12~15회'),('케이블 푸시다운',3,'10~15회'),('경사 걷기',1,'25~30분')],
    [('랫풀다운',4,'8~12회'),('시티드 케이블로우',3,'8~12회'),('머신로우',3,'10~12회'),('페이스풀',3,'12~15회'),('덤벨컬',3,'10~12회'),('해머컬',2,'10~12회'),('경사 걷기',1,'25~30분')],
    [('스쿼트 또는 레그프레스',4,'8~12회'),('레그컬',3,'10~15회'),('레그익스텐션',3,'10~15회'),('루마니안 데드리프트',3,'8~12회'),('카프레이즈',3,'12~20회'),('가벼운 유산소',1,'15~20분')],
    [('머신 숄더프레스',4,'8~12회'),('사이드 레터럴레이즈',4,'12~15회'),('리버스 펙덱',3,'12~15회'),('체스트프레스',3,'10~12회'),('랫풀다운',3,'10~12회'),('경사 걷기',1,'25~30분')],
    [('레그프레스',3,'10~12회'),('체스트프레스',3,'10~12회'),('랫풀다운',3,'10~12회'),('시티드로우',2,'10~12회'),('사이드 레터럴레이즈',2,'12~15회'),('유산소',1,'30~40분')], [], [],
]
DEFAULTS = dict(height=183, age=29, sex='male', start_weight=90, goal_weight=78,
    start_date='2026-09-28', goal_date='2026-12-25', calorie_min=2000, calorie_max=2200,
    protein_min=150, protein_max=170, water_min_ml=2500, water_goal_ml=3000,
    steps_min=8000, steps_goal=10000, items=ITEMS,
    routines=[[dict(name=n, sets=s, reps=r) for n,s,r in day] for day in ROUTINES])


def today():
    return datetime.now(timezone(timedelta(hours=9))).date()


def valid_date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return parsed
    except (ValueError, TypeError):
        raise HTTPException(422, '날짜는 YYYY-MM-DD 형식으로 입력하세요.')


def number(value, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high or (integer and int(value) != value):
        raise HTTPException(422, '입력값의 범위와 숫자 형식을 확인하세요.')
    return value


def settings_checked(raw):
    if not isinstance(raw, dict) or set(raw) != set(DEFAULTS):
        raise HTTPException(422, '설정 항목이 올바르지 않습니다.')
    for key in ('height','age','start_weight','goal_weight','calorie_min','calorie_max','protein_min','protein_max','water_min_ml','water_goal_ml','steps_min','steps_goal'):
        number(raw[key], 1, 100000, key not in ('height','start_weight','goal_weight'))
    if raw['sex'] not in ('male','female') or valid_date(raw['goal_date']) <= valid_date(raw['start_date']) or raw['start_weight'] <= raw['goal_weight']:
        raise HTTPException(422, '시작·목표 날짜와 체중을 확인하세요.')
    for a,b in [('calorie_min','calorie_max'),('protein_min','protein_max'),('water_min_ml','water_goal_ml'),('steps_min','steps_goal')]:
        if raw[a] > raw[b]:
            raise HTTPException(422, '최솟값이 목표 상한보다 큽니다.')
    if not isinstance(raw['items'],dict) or set(raw['items']) != set(ITEMS) or any(not isinstance(v,str) or not v.strip() or len(v)>200 for v in raw['items'].values()):
        raise HTTPException(422, '식단과 영양제 이름을 확인하세요.')
    routines = raw['routines']
    if not isinstance(routines,list) or len(routines)!=7 or routines[5:] != [[],[]]:
        raise HTTPException(422, '루틴은 월~금 운동과 주말 휴식으로 구성하세요.')
    for day in routines[:5]:
        if not isinstance(day,list) or not 1<=len(day)<=20:
            raise HTTPException(422, '운동 개수를 확인하세요.')
        names=[]
        for item in day:
            if not isinstance(item,dict) or set(item)!= {'name','sets','reps'} or any(not isinstance(item[k],str) or not item[k].strip() or len(item[k])>100 for k in ('name','reps')):
                raise HTTPException(422, '운동 이름과 목표 횟수를 확인하세요.')
            number(item['sets'],1,10,True)
            names.append(item['name'])
        if len(names)!=len(set(names)):
            raise HTTPException(422, '하루 운동 이름은 중복할 수 없습니다.')
    return raw


def blank_day():
    return dict(weight=None, water_ml=0, steps=0, **{key:False for key in ITEMS})


def check_day(raw):
    if not isinstance(raw,dict) or set(raw)-set(blank_day()):
        raise HTTPException(422, '알 수 없는 기록 항목입니다.')
    for k,v in raw.items():
        if k in ITEMS and type(v) is not bool:
            raise HTTPException(422, '체크 항목은 참 또는 거짓이어야 합니다.')
        if k=='weight' and v is not None:
            number(v,20,400)
        if k in ('water_ml','steps'):
            number(v,0,20000 if k=='water_ml' else 200000,True)
    return raw


def check_workout(raw):
    if not isinstance(raw,dict) or set(raw)-{'completed','weight','reps'}:
        raise HTTPException(422,'운동 기록 항목이 올바르지 않습니다.')
    if 'completed' in raw and type(raw['completed']) is not bool:
        raise HTTPException(422,'완료 여부를 확인하세요.')
    if 'weight' in raw and raw['weight'] is not None:
        number(raw['weight'],0,1000)
    if 'reps' in raw:
        if not isinstance(raw['reps'],list) or len(raw['reps'])>10:
            raise HTTPException(422,'세트 기록을 확인하세요.')
        for v in raw['reps']:
            if v is not None:
                number(v,0,500,True)
    return raw


class DietStore:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS settings (account TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS daily_logs (account TEXT, date TEXT, payload TEXT NOT NULL, updated_at TEXT, PRIMARY KEY(account,date))')
            db.execute('CREATE TABLE IF NOT EXISTS workout_logs (account TEXT, date TEXT, exercise TEXT, payload TEXT NOT NULL, PRIMARY KEY(account,date,exercise))')

    def connect(self):
        return sqlite3.connect(self.path,timeout=15)

    def settings(self,user):
        with self.connect() as db:
            row=db.execute('SELECT payload FROM settings WHERE account=?',(user,)).fetchone()
        return json.loads(row[0]) if row else copy.deepcopy(DEFAULTS)

    def day(self,user,day):
        parsed=valid_date(day)
        settings=self.settings(user)
        with self.connect() as db:
            row=db.execute('SELECT payload FROM daily_logs WHERE account=? AND date=?',(user,day)).fetchone()
            saved={n:json.loads(p) for n,p in db.execute('SELECT exercise,payload FROM workout_logs WHERE account=? AND date=?',(user,day))}
        data={**blank_day(),**(json.loads(row[0]) if row else {})}
        workouts=[{**item,**saved.get(item['name'],dict(completed=False,weight=None,reps=[]))} for item in settings['routines'][parsed.weekday()]]
        keys=[k for k in ITEMS if k!='dinner_extra_chicken_done']
        total=len(keys)+3+len(workouts)
        done=sum(data[k] for k in keys)+(data['weight'] is not None)+(data['water_ml']>=settings['water_min_ml'])+(data['steps']>=settings['steps_min'])+sum(w['completed'] for w in workouts)
        return dict(date=day,log=data,workouts=workouts,done=done,total=total,percent=round(done/total*100),recorded=bool(row or saved),future=parsed>today())

    def patch(self,user,day,raw,exercise=None):
        if valid_date(day)>today():
            raise HTTPException(422,'미래 날짜는 계획만 확인할 수 있습니다.')
        table='daily_logs' if exercise is None else 'workout_logs'
        if exercise is None:
            check_day(raw)
        else:
            plan=self.day(user,day)['workouts']
            if exercise not in [w['name'] for w in plan]:
                raise HTTPException(404,'해당 날짜의 운동이 없습니다.')
            check_workout(raw)
            if len(raw.get('reps',[]))>next(w['sets'] for w in plan if w['name']==exercise):
                raise HTTPException(422,'목표 세트 수를 초과했습니다.')
        # 잡지식: 물 한 잔도 트랜잭션으로 저장하면 동시 요청에 기록이 섞이지 않아요.
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if exercise is None:
                row=db.execute('SELECT payload FROM daily_logs WHERE account=? AND date=?',(user,day)).fetchone()
            else:
                row=db.execute('SELECT payload FROM workout_logs WHERE account=? AND date=? AND exercise=?',(user,day,exercise)).fetchone()
            data=json.loads(row[0]) if row else {}
            data.update(raw)
            if table=='daily_logs':
                db.execute('INSERT INTO daily_logs VALUES (?,?,?,?) ON CONFLICT(account,date) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',(user,day,json.dumps(data),datetime.now(timezone.utc).isoformat()))
            else:
                db.execute('INSERT INTO workout_logs VALUES (?,?,?,?) ON CONFLICT(account,date,exercise) DO UPDATE SET payload=excluded.payload',(user,day,exercise,json.dumps(data)))
        return self.day(user,day)

    def logs(self,user,start,end):
        valid_date(start); valid_date(end)
        with self.connect() as db:
            days=[r[0] for r in db.execute('SELECT date FROM daily_logs WHERE account=? AND date BETWEEN ? AND ? UNION SELECT date FROM workout_logs WHERE account=? AND date BETWEEN ? AND ? ORDER BY date',(user,start,end,user,start,end))]
        return [self.day(user,d) for d in days]

    def stats(self,user):
        settings=self.settings(user); now=today()
        logs=self.logs(user,'1900-01-01',now.isoformat())
        weights=[(valid_date(d['date']),d['log']['weight']) for d in logs if d['log']['weight'] is not None]
        def avg(a,b):
            values=[w for d,w in weights if a<=d<=b]
            return round(sum(values)/len(values),2) if values else None
        current=weights[-1][1] if weights else settings['start_weight']
        recent=avg(now-timedelta(days=6),now); previous=avg(now-timedelta(days=13),now-timedelta(days=7))
        monday=now-timedelta(days=now.weekday())
        week=[self.day(user,(monday+timedelta(days=i)).isoformat()) for i in range(now.weekday()+1)]
        return dict(today=now.isoformat(),current=current,average=recent,average_count=sum(now-timedelta(days=6)<=d<=now for d,w in weights),previous=previous,change=round(recent-previous,2) if recent is not None and previous is not None else None,lost=round(settings['start_weight']-current,2),remaining=round(current-settings['goal_weight'],2),progress=max(0,min(100,round((settings['start_weight']-current)/(settings['start_weight']-settings['goal_weight'])*100))),days_left=(valid_date(settings['goal_date'])-now).days,weights=[dict(date=d.isoformat(),weight=w,average=avg(d-timedelta(days=6),d)) for d,w in weights],week=dict(days=len(week),percent=round(sum(d['percent'] for d in week)/len(week)),workout=sum(bool(d['workouts']) and all(w['completed'] for w in d['workouts']) for d in week),workout_total=sum(bool(d['workouts']) for d in week),breakfast=sum(d['log']['breakfast_protein_done'] and d['log']['breakfast_fruit_done'] for d in week),dinner=sum(all(d['log'][k] for k in ('dinner_rice_done','dinner_chicken_done','dinner_broccoli_done')) for d in week),water=sum(d['log']['water_ml']>=settings['water_min_ml'] for d in week),steps=round(sum(d['log']['steps'] for d in week)/len(week))))

    def backup(self,user):
        with self.connect() as db:
            daily=[dict(date=d,log=json.loads(p)) for d,p in db.execute('SELECT date,payload FROM daily_logs WHERE account=?',(user,))]
            workouts=[dict(date=d,exercise=n,log=json.loads(p)) for d,n,p in db.execute('SELECT date,exercise,payload FROM workout_logs WHERE account=?',(user,))]
        return dict(version=1,settings=self.settings(user),daily=daily,workouts=workouts)

    def restore(self,user,raw):
        if not isinstance(raw,dict) or set(raw)!={'version','settings','daily','workouts'} or raw['version']!=1:
            raise HTTPException(422,'지원하지 않는 백업입니다.')
        settings_checked(raw['settings'])
        seen=set()
        for collection in ('daily','workouts'):
            if not isinstance(raw[collection],list) or len(raw[collection])>50000:
                raise HTTPException(422,'백업 기록 개수를 확인하세요.')
            for row in raw[collection]:
                if not isinstance(row,dict) or set(row)!=({'date','log'} if collection=='daily' else {'date','exercise','log'}):
                    raise HTTPException(422,'백업 기록 형식이 올바르지 않습니다.')
                parsed=valid_date(row['date'])
                if parsed>today():
                    raise HTTPException(422,'미래 기록은 복원할 수 없습니다.')
                if collection=='daily':
                    check_day(row['log']); key=(collection,row['date'])
                else:
                    check_workout(row['log']); key=(collection,row['date'],row['exercise'])
                    if not isinstance(row['exercise'],str) or not row['exercise'].strip() or len(row['exercise'])>100:
                        raise HTTPException(422,'백업 운동 이름을 확인하세요.')
                if key in seen:
                    raise HTTPException(422,'중복 백업 기록입니다.')
                seen.add(key)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM daily_logs WHERE account=?',(user,))
            db.execute('DELETE FROM workout_logs WHERE account=?',(user,))
            db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(user,json.dumps(raw['settings'])))
            db.executemany('INSERT INTO daily_logs VALUES (?,?,?,?)',[(user,r['date'],json.dumps(r['log']),datetime.now(timezone.utc).isoformat()) for r in raw['daily']])
            db.executemany('INSERT INTO workout_logs VALUES (?,?,?,?)',[(user,r['date'],r['exercise'],json.dumps(r['log'])) for r in raw['workouts']])
        return {'success':True}


def install(app,identity,root):
    router=APIRouter(prefix='/api/diet')
    def owner(request):
        user=identity(request)
        if user != 'player2':
            raise HTTPException(403, '다이어트는 차니 전용입니다.')
        return user
    def context(request):
        user=owner(request)
        return DietStore(app.state.db.path.with_name('diet.db')),user
    @router.get('/settings')
    def settings(request:Request):
        store,user=context(request); return store.settings(user)
    @router.put('/settings')
    def update_settings(request:Request,body:dict):
        store,user=context(request); settings_checked(body)
        with store.connect() as db:
            db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(user,json.dumps(body)))
        return body
    @router.get('/day/{day}')
    def get_day(day:str,request:Request):
        store,user=context(request); return store.day(user,day)
    @router.patch('/day/{day}')
    def patch_day(day:str,request:Request,body:dict):
        store,user=context(request); return store.patch(user,day,body)
    @router.get('/workouts/{day}')
    def workouts(day:str,request:Request):
        store,user=context(request); return store.day(user,day)['workouts']
    @router.patch('/workouts/{day}/{exercise}')
    def patch_workout(day:str,exercise:str,request:Request,body:dict):
        store,user=context(request); return store.patch(user,day,body,exercise)
    @router.get('/logs')
    def logs(request:Request,start:str='1900-01-01',end:str='2100-12-31'):
        store,user=context(request); return store.logs(user,start,end)
    @router.get('/stats')
    def stats(request:Request):
        store,user=context(request); return store.stats(user)
    @router.get('/backup')
    def backup(request:Request):
        store,user=context(request)
        return JSONResponse(store.backup(user),headers={'Content-Disposition':f'attachment; filename=christmas_cut_backup_{today():%Y%m%d}.json'})
    @router.post('/restore')
    def restore(request:Request,body:dict):
        store,user=context(request); return store.restore(user,body)
    app.include_router(router)
    @app.get('/diet',include_in_schema=False)
    @app.get('/diet/{page:path}',include_in_schema=False)
    def page(request:Request,page:str=''):
        owner(request)
        return FileResponse(root/'web'/'diet.html')
