"""식품안전기사 학습 기록과 관리자 읽기 전용 조회를 제공한다."""
import json
import sqlite3
import re
import os
import tempfile
import zipfile
import shutil
from pathlib import Path
from uuid import uuid4
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, StrictBool
from starlette.concurrency import run_in_threadpool

ConceptId = Annotated[str, StringConstraints(pattern=r'^l[1-9]\d{0,2}$')]
QuestionId = Annotated[str, StringConstraints(pattern=r'^(?:q\d{1,3}|g\d{3}|wg\d{3}|[pw]\d{4}-\d-\d{3})$')]
Day = Annotated[str, StringConstraints(pattern=r'^\d{4}-\d{2}-\d{2}$')]
Memo = Annotated[str, StringConstraints(max_length=4000)]


class Attempt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: QuestionId
    correct: StrictBool
    time: int = Field(ge=0, le=100000000000000)
    method: Literal['automatic', 'manual'] = 'automatic'


class Session(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ids: list[QuestionId] = Field(min_length=1, max_length=100)
    index: int = Field(ge=0, le=99)
    selected: int | None = Field(default=None, ge=0, le=3)
    answered: StrictBool = False
    score: int = Field(ge=0, le=100)
    hideChoices: StrictBool = False
    revealed: StrictBool = False


class ExamSession(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ids: list[QuestionId] = Field(min_length=80, max_length=80)
    answers: dict[QuestionId, Annotated[int, Field(ge=0, le=3)]] = Field(default_factory=dict, max_length=80)
    flagged: list[QuestionId] = Field(default_factory=list, max_length=80)
    index: int = Field(ge=0, le=79)
    startedAt: int = Field(ge=0)
    deadline: int = Field(ge=0)
    origin: Literal['past', 'generated', 'mixed']
    round: str = Field(max_length=20)


class ExamResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^e\d{1,20}$')
    ids: list[QuestionId] = Field(min_length=80, max_length=80)
    answers: dict[QuestionId, Annotated[int, Field(ge=0, le=3)]] = Field(max_length=80)
    scores: dict[str, Annotated[int, Field(ge=0, le=100)]] = Field(max_length=4)
    average: float = Field(ge=0, le=100)
    passed: StrictBool
    time: int = Field(ge=0)
    origin: Literal['past', 'generated', 'mixed']
    elapsed: int = Field(ge=0, le=7200)


class StudyState(BaseModel):
    model_config = ConfigDict(extra='forbid')
    read: list[ConceptId] = Field(default_factory=list, max_length=100)
    saved: list[ConceptId] = Field(default_factory=list, max_length=100)
    notes: dict[ConceptId, Memo] = Field(default_factory=dict, max_length=100)
    results: dict[QuestionId, StrictBool] = Field(default_factory=dict, max_length=4000)
    history: list[Attempt] = Field(default_factory=list, max_length=1000)
    daily: dict[Day, Annotated[int, Field(ge=0, le=1000000)]] = Field(default_factory=dict, max_length=10000)
    goal: int = Field(default=5, ge=1, le=50)
    target: date | None = None
    session: Session | None = None
    saved_questions: list[QuestionId] = Field(default_factory=list, max_length=4000)
    qnotes: dict[QuestionId, Memo] = Field(default_factory=dict, max_length=4000)
    mastery: dict[QuestionId, Annotated[int, Field(ge=0, le=1000000)]] = Field(default_factory=dict, max_length=4000)
    repetitions: dict[QuestionId, Annotated[int, Field(ge=0, le=1000000)]] = Field(default_factory=dict, max_length=4000)
    responses: dict[QuestionId, Memo] = Field(default_factory=dict, max_length=1000)
    grades: dict[QuestionId, Literal['correct', 'partial', 'wrong']] = Field(default_factory=dict, max_length=1000)
    exam_session: ExamSession | None = None
    exams: list[ExamResult] = Field(default_factory=list, max_length=50)


class ImportedQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: QuestionId
    s: Literal['safety', 'chemistry', 'process', 'micro']
    l: ConceptId
    title: str = Field(min_length=1, max_length=20000)
    choices: list[Annotated[str, StringConstraints(max_length=10000)]] = Field(max_length=4)
    answer: int | None = Field(ge=0, le=3)
    explain: str = Field(max_length=30000)
    origin: Literal['past']
    type: Literal['choice', 'written'] = 'choice'
    year: int = Field(ge=2000, le=2100)
    round: int = Field(ge=1, le=5)
    number: int = Field(ge=1, le=100)
    pdfPage: int = Field(ge=1, le=3000)
    source: str = Field(max_length=300)
    current: StrictBool
    image: str = Field(max_length=100)
    answerImage: str | None = Field(default=None, max_length=100)
    modelAnswer: str | None = Field(default=None, max_length=20000)


class ImportedBank(BaseModel):
    model_config = ConfigDict(extra='forbid')
    questions: list[ImportedQuestion] = Field(min_length=1, max_length=5000)


def install(app, identity, root):
    content = json.loads((root / 'sikangi' / 'bank.json').read_text(encoding='utf-8'))
    catalog = {question['id']: question for question in content['questions']}
    base_subjects = ['safety', 'chemistry', 'process', 'micro']
    for number in range(1, 17):
        catalog[f'q{number}'] = {'s': base_subjects[(number - 1) // 4], 'answer': [2, 1, 2, 0, 1, 2, 0, 1, 2, 0, 2, 3, 0, 1, 2, 3][number - 1]}
    concept_ids = {f'l{i}' for i in range(1, 13)} | {lesson['id'] for lesson in content['lessons']}
    imported = {'version': None, 'questions': [], 'directory': None}

    def storage_root():
        return app.state.db.path.with_name('sikangi-content')

    def refresh_bank():
        pointer = storage_root() / 'active.json'
        if not pointer.exists():
            return
        version = json.loads(pointer.read_text(encoding='utf-8'))['version']
        if version == imported['version']:
            return
        if not re.fullmatch(r'[0-9a-f]{32}', version):
            raise HTTPException(503, '문제은행 저장 상태를 확인해 주세요.')
        directory = storage_root() / version
        bank = json.loads((directory / 'bank.json').read_text(encoding='utf-8'))
        for question in imported['questions']:
            catalog.pop(question['id'], None)
        catalog.update({question['id']: question for question in bank['questions']})
        imported.update(version=version, questions=bank['questions'], directory=directory)

    def install_package(package):
        destination = storage_root() / uuid4().hex
        destination.mkdir(parents=True)
        try:
            with zipfile.ZipFile(package) as archive:
                entries = archive.infolist()
                if len(entries) > 10001 or len({item.filename for item in entries}) != len(entries) or sum(item.file_size for item in entries) > 120 * 1024 * 1024:
                    raise ValueError('문제은행 파일의 크기나 항목 수를 확인해 주세요.')
                for item in entries:
                    if item.filename != 'bank.json' and not re.fullmatch(r'exam-assets/[pw]\d{4}-\d-\d{3}(?:-answer)?\.webp', item.filename):
                        raise ValueError('허용되지 않은 파일이 포함되어 있습니다.')
                    if item.file_size > (20 * 1024 * 1024 if item.filename == 'bank.json' else 2 * 1024 * 1024):
                        raise ValueError('개별 문항 파일의 크기가 너무 큽니다.')
                bank = ImportedBank.model_validate_json(archive.read('bank.json'))
                ids = [question.id for question in bank.questions]
                if len(set(ids)) != len(ids):
                    raise ValueError('중복된 문항 ID가 있습니다.')
                if not {question['id'] for question in imported['questions']} <= set(ids):
                    raise ValueError('기존 기출 문항도 포함한 전체 문제은행을 등록해 주세요.')
                required = {'bank.json'}
                for question in bank.questions:
                    if not re.fullmatch(r'[pw]\d{4}-\d-\d{3}', question.id) or question.l not in concept_ids:
                        raise ValueError('문항 ID와 과목 연결을 확인해 주세요.')
                    if question.type == 'choice' and (len(question.choices) != 4 or question.answer is None):
                        raise ValueError('선지와 정답을 확인해 주세요.')
                    if question.type == 'written' and (question.choices or question.answer is not None or not question.modelAnswer):
                        raise ValueError('필답형 모범답안을 확인해 주세요.')
                    for image in [question.image, question.answerImage]:
                        if not image:
                            continue
                        filename = image.removeprefix('/sikangi/')
                        if image != '/sikangi/exam-assets/' + question.id + ('-answer.webp' if image == question.answerImage else '.webp'):
                            raise ValueError('문항 이미지 경로를 확인해 주세요.')
                        required.add(filename)
                if set(item.filename for item in entries) != required:
                    raise ValueError('원문 이미지가 누락되었거나 불필요한 파일이 있습니다.')
                for item in entries:
                    if item.filename == 'bank.json':
                        continue
                    target = destination / item.filename
                    target.parent.mkdir(exist_ok=True)
                    with archive.open(item) as source, target.open('wb') as output:
                        shutil.copyfileobj(source, output)
                    with target.open('rb') as source:
                        header = source.read(12)
                    if not header.startswith(b'RIFF') or header[8:12] != b'WEBP':
                        raise ValueError('원문 이미지 형식을 확인해 주세요.')
                (destination / 'bank.json').write_text(json.dumps(bank.model_dump(mode='json'), ensure_ascii=False), encoding='utf-8')
            pointer = storage_root() / ('active-' + uuid4().hex + '.tmp')
            pointer.write_text(json.dumps({'version': destination.name}), encoding='utf-8')
            os.replace(pointer, storage_root() / 'active.json')
            return {'imported': len(ids), 'choice': sum(q.type == 'choice' for q in bank.questions), 'written': sum(q.type == 'written' for q in bank.questions)}
        except Exception:
            # 임시 등록본만 정리하며, 기존 활성 버전과 학습 기록은 보존합니다.
            shutil.rmtree(destination)
            raise

    def validate_exam(exam):
        if len(set(exam.ids)) != 80 or any(identifier not in catalog or catalog[identifier].get('type') == 'written' for identifier in exam.ids):
            raise HTTPException(422, '모의고사 문항 구성을 확인해 주세요.')
        if Counter(catalog[identifier]['s'] for identifier in exam.ids) != Counter({subject: 20 for subject in base_subjects}) or not set(exam.answers) <= set(exam.ids):
            raise HTTPException(422, '과목별 문항 수와 답안을 확인해 주세요.')

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

    @app.get('/api/sikangi/bank')
    def bank_data(request: Request):
        identity(request)
        refresh_bank()
        return {'questions': imported['questions'], 'registered': bool(imported['version'])}

    @app.put('/api/sikangi/admin/content')
    async def upload_content(request: Request):
        if profile(request)['role'] != 'admin':
            raise HTTPException(403, '관리자만 기출 문제은행을 등록할 수 있습니다.')
        refresh_bank()
        storage_root().mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=storage_root()) as directory:
            package = Path(directory) / 'upload.zip'
            total = 0
            with package.open('wb') as output:
                async for chunk in request.stream():
                    total += len(chunk)
                    if total > 80 * 1024 * 1024:
                        raise HTTPException(413, '등록 파일은 80MB 이하여야 합니다.')
                    output.write(chunk)
            try:
                result = await run_in_threadpool(install_package, package)
            except (ValueError, KeyError, zipfile.BadZipFile, RuntimeError) as error:
                raise HTTPException(422, '문제은행 파일을 확인해 주세요. 기존 자료는 유지됩니다.') from error
        refresh_bank()
        return result

    @app.get('/api/sikangi/state')
    def get_state(request: Request):
        return record(identity(request))

    @app.put('/api/sikangi/state')
    def put_state(request: Request, body: StudyState):
        account = identity(request)
        refresh_bank()
        if body.session and (body.session.index >= len(body.session.ids) or body.session.score > len(body.session.ids)):
            raise HTTPException(422, '풀이 진행 상태를 확인해 주세요.')
        if not set(body.read + body.saved + list(body.notes)) <= concept_ids:
            raise HTTPException(422, '등록된 개념인지 확인해 주세요.')
        question_ids = set(body.results) | set(body.saved_questions) | set(body.qnotes) | set(body.mastery) | set(body.repetitions) | set(body.responses) | set(body.grades) | {item.id for item in body.history}
        if body.session:
            question_ids.update(body.session.ids)
        if not question_ids <= catalog.keys():
            raise HTTPException(422, '등록된 문항인지 확인해 주세요.')
        if body.exam_session:
            validate_exam(body.exam_session)
            if not set(body.exam_session.flagged) <= set(body.exam_session.ids) or body.exam_session.deadline < body.exam_session.startedAt:
                raise HTTPException(422, '시험 진행 상태를 확인해 주세요.')
        for exam in body.exams:
            validate_exam(exam)
            exam.scores = {subject: sum(exam.answers.get(identifier) == catalog[identifier]['answer'] for identifier in exam.ids if catalog[identifier]['s'] == subject) * 5 for subject in base_subjects}
            exam.average = sum(exam.scores.values()) / 4
            exam.passed = exam.average >= 60 and min(exam.scores.values()) >= 40
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
        try:
            identity(request)
        except HTTPException as error:
            if error.status_code != 401:
                raise
            return RedirectResponse('/sikangi/login', status_code=303)
        return FileResponse(root / 'sikangi' / 'index.html')

    @app.get('/sikangi/login', include_in_schema=False)
    def login_page(request: Request):
        try:
            identity(request)
        except HTTPException as error:
            if error.status_code != 401:
                raise
            return FileResponse(root / 'sikangi' / 'login.html')
        return RedirectResponse('/sikangi', status_code=303)

    @app.get('/sikangi/exam-assets/{filename}', include_in_schema=False)
    def question_image(filename: str, request: Request):
        identity(request)
        refresh_bank()
        match = re.fullmatch(r'([pw]\d{4}-\d-\d{3})(?:-answer)?\.webp', filename)
        if not match or match[1] not in catalog or not imported['directory'] or not (imported['directory'] / 'exam-assets' / filename).is_file():
            raise HTTPException(404, '문항 이미지를 찾을 수 없습니다.')
        return FileResponse(imported['directory'] / 'exam-assets' / filename, media_type='image/webp')

    @app.get('/sikangi/{filename}', include_in_schema=False)
    def asset(filename: str, request: Request):
        if filename in {'login.css', 'login.js'}:
            return FileResponse(root / 'sikangi' / filename)
        identity(request)
        # 잡지식: 허용 목록을 쓰면 학습 자료 옆 서버 파일이 주소로 새는 일을 막을 수 있어요.
        if filename not in {'app.js', 'styles.css', 'content.js', 'exam.js'}:
            raise HTTPException(404, '학습실 파일을 찾을 수 없습니다.')
        if filename == 'content.js' and 'gzip' in request.headers.get('accept-encoding', ''):
            return FileResponse(root / 'sikangi' / 'content.js.gz', media_type='application/javascript', headers={'Content-Encoding': 'gzip', 'Vary': 'Accept-Encoding'})
        return FileResponse(root / 'sikangi' / filename)
