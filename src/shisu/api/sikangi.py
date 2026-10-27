"""식품안전기사 학습 기록과 관리자 읽기 전용 조회를 제공한다."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, StrictBool

ConceptId = Annotated[str, StringConstraints(pattern=r'^l(?:[1-9]|1[0-2])$')]
QuestionId = Annotated[str, StringConstraints(pattern=r'^q(?:[1-9]|1[0-6])$')]
Day = Annotated[str, StringConstraints(pattern=r'^\d{4}-\d{2}-\d{2}$')]
Memo = Annotated[str, StringConstraints(max_length=4000)]


class Attempt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: QuestionId
    correct: StrictBool
    time: int = Field(ge=0, le=100000000000000)


class Session(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ids: list[QuestionId] = Field(min_length=1, max_length=16)
    index: int = Field(ge=0, le=15)
    selected: int | None = Field(default=None, ge=0, le=3)
    answered: StrictBool = False
    score: int = Field(ge=0, le=16)


class StudyState(BaseModel):
    model_config = ConfigDict(extra='forbid')
    read: list[ConceptId] = Field(default_factory=list, max_length=12)
    saved: list[ConceptId] = Field(default_factory=list, max_length=12)
    notes: dict[ConceptId, Memo] = Field(default_factory=dict, max_length=12)
    results: dict[QuestionId, StrictBool] = Field(default_factory=dict, max_length=16)
    history: list[Attempt] = Field(default_factory=list, max_length=100)
    daily: dict[Day, Annotated[int, Field(ge=0, le=1000000)]] = Field(default_factory=dict, max_length=10000)
    goal: int = Field(default=5, ge=1, le=50)
    target: date | None = None
    session: Session | None = None


def install(app, identity, root):
    def profile(request):
        account = identity(request)
        registered = app.state.db.registered_account(account)
        name = registered[0] if registered else app.state.accounts[account]['name']
        return {'account': account, 'name': name, 'role': 'admin' if account == 'player2' else 'learner'}

    @contextmanager
    def connect():
        db = sqlite3.connect(app.state.db.path.with_name('sikangi.db'), timeout=10)
        try:
            db.execute('CREATE TABLE IF NOT EXISTS study_records (account TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at TEXT NOT NULL)')
            with db:
                yield db
        finally:
            db.close()

    def record(account):
        with connect() as db:
            row = db.execute('SELECT state, updated_at FROM study_records WHERE account=?', (account,)).fetchone()
        return {'state': json.loads(row[0]) if row else None, 'updated_at': row[1] if row else None}

    @app.get('/api/sikangi/me')
    def me(request: Request):
        return profile(request)

    @app.get('/api/sikangi/state')
    def get_state(request: Request):
        return record(identity(request))

    @app.put('/api/sikangi/state')
    def put_state(request: Request, body: StudyState):
        account = identity(request)
        if body.session and (body.session.index >= len(body.session.ids) or body.session.score > len(body.session.ids)):
            raise HTTPException(422, '풀이 진행 상태를 확인해 주세요.')
        data = body.model_dump(mode='json')
        data['target'] = data['target'] or ''
        updated = datetime.now(timezone.utc).isoformat()
        with connect() as db:
            db.execute('INSERT INTO study_records VALUES (?, ?, ?) ON CONFLICT(account) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at',
                       (account, json.dumps(data, ensure_ascii=False), updated))
        return {'saved': True, 'updated_at': updated}

    @app.get('/api/sikangi/admin/learner')
    def learner_record(request: Request):
        if profile(request)['role'] != 'admin':
            raise HTTPException(403, '관리자만 학습자 기록을 조회할 수 있습니다.')
        registered = app.state.db.registered_account('player1')
        name = registered[0] if registered else app.state.accounts['player1']['name']
        return {'account': 'player1', 'name': name, **record('player1')}

    @app.get('/sikangi', include_in_schema=False)
    @app.get('/sikangi/', include_in_schema=False)
    def page(request: Request):
        identity(request)
        return FileResponse(root / 'sikangi' / 'index.html')

    @app.get('/sikangi/{filename}', include_in_schema=False)
    def asset(filename: str, request: Request):
        identity(request)
        # 잡지식: 허용 목록을 쓰면 학습 자료 옆 서버 파일이 주소로 새는 일을 막을 수 있어요.
        if filename not in {'app.js', 'styles.css'}:
            raise HTTPException(404, '학습실 파일을 찾을 수 없습니다.')
        return FileResponse(root / 'sikangi' / filename)
