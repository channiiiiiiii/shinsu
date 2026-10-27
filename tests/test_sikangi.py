"""학습 기록의 계정 격리와 관리자 읽기 권한을 검증한다."""
from fastapi.testclient import TestClient
import io
import json
import zipfile

from shisu.api.main import create_app


ACCOUNTS = {
    'player1': {'name': '여니', 'code': '1' * 32},
    'player2': {'name': '차니', 'code': '2' * 32},
}
HEADERS = {'X-Shinsu-Client': 'web'}


def login(client, account):
    result = client.post('/api/login', json={
        'account': account, 'code': ('1' if account == 'player1' else '2') * 32,
    }, headers=HEADERS)
    assert result.status_code == 200


def test_roles_isolation_and_admin_read_only(tmp_path):
    app = create_app(tmp_path / 'game.db', ACCOUNTS, False)
    record = {
        'read': ['l1'], 'notes': {'l1': '위해요소 세 가지 복습'},
        'results': {'q1': False},
        'history': [{'id': 'q1', 'correct': False, 'time': 1793000000000}],
        'daily': {'2026-10-27': 1}, 'goal': 5, 'target': None,
    }
    with TestClient(app) as client:
        for path in ['/sikangi/app.js',
                     '/api/sikangi/me', '/api/sikangi/state', '/api/sikangi/admin/learner']:
            assert client.get(path).status_code == 401
        login(client, 'player1')
        assert client.get('/api/sikangi/me').json()['role'] == 'learner'
        assert client.get('/api/sikangi/state').json()['state'] is None
        assert client.put('/api/sikangi/state', json=record).status_code == 403
        assert client.put('/api/sikangi/state', json=record, headers=HEADERS).status_code == 200
        before = client.get('/api/sikangi/state').json()
        assert before['state']['read'] == ['l1']
        assert client.get('/api/sikangi/admin/learner').status_code == 403
        login(client, 'player2')
        assert client.get('/api/sikangi/me').json()['role'] == 'admin'
        assert client.get('/api/sikangi/state').json()['state'] is None
        assert client.get('/api/sikangi/admin/learner').json()['state'] == before['state']
        assert client.put('/api/sikangi/admin/learner', json=record, headers=HEADERS).status_code == 405
        assert client.put('/api/sikangi/state', json={'read': ['l2']}, headers=HEADERS).status_code == 200
        assert client.get('/api/sikangi/admin/learner').json()['state'] == before['state']
        login(client, 'player1')
        assert client.get('/api/sikangi/state').json()['state'] == before['state']
        assert client.get('/diet').status_code == 403
    with TestClient(create_app(tmp_path / 'game.db', ACCOUNTS, False)) as client:
        login(client, 'player2')
        assert client.get('/api/sikangi/admin/learner').json()['state'] == before['state']
        assert client.get('/diet').status_code == 200


def test_assets_validation_and_security_policy(tmp_path):
    with TestClient(create_app(tmp_path / 'game.db', ACCOUNTS, False)) as client:
        login(client, 'player1')
        for path in ['/sikangi', '/sikangi/']:
            response = client.get(path)
            assert response.status_code == 200
            assert '/sikangi/styles.css' in response.text
            assert '/sikangi/app.js' in response.text
            assert "style-src 'self'" in response.headers['Content-Security-Policy']
            assert "'unsafe-inline'" not in response.headers['Content-Security-Policy']
        assert client.get('/sikangi/styles.css').status_code == 200
        script = client.get('/sikangi/app.js')
        assert script.status_code == 200 and 'javascript' in script.headers['content-type']
        assert 'style="' not in script.text
        assert '@import' not in client.get('/sikangi/styles.css').text
        assert client.get('/sikangi/task.md').status_code == 404
        assert client.get('/api/health').status_code == 200
        for invalid in [
            {'read': ['l99']}, {'goal': 0}, {'notes': {'l1': '가' * 4001}},
            {'account': 'player2'}, {'results': {'q1': '아니오'}},
            {'session': {'ids': ['q1'], 'index': 2, 'score': 0}},
        ]:
            assert client.put('/api/sikangi/state', json=invalid, headers=HEADERS).status_code == 422


def test_login_screen_and_return_to_study(tmp_path):
    with TestClient(create_app(tmp_path / 'game.db', ACCOUNTS, False)) as client:
        for path in ['/sikangi', '/sikangi/']:
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 303
            assert response.headers['location'] == '/sikangi/login'
            screen = client.get(path)
            assert screen.status_code == 200
            assert 'id="login-form"' in screen.text
            assert '/sikangi/login.css' in screen.text
            assert '/sikangi/login.js' in screen.text
            assert '<select' not in screen.text
            assert 'name="account" type="text"' in screen.text
            assert '여니 · 학습 사용자' not in screen.text
            assert '차니 · 관리자' not in screen.text
        assert client.get('/sikangi/login.css').status_code == 200
        assert client.get('/sikangi/login.js').status_code == 200
        assert client.get('/api/sikangi/state').status_code == 401
        assert client.post('/api/login', json={'account': 'player1', 'code': '틀린 비밀번호'}, headers=HEADERS).status_code == 401
        assert client.get('/sikangi/login').status_code == 200
        login(client, 'player1')
        response = client.get('/sikangi/login', follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'] == '/sikangi'
        assert 'id="main"' in client.get('/sikangi').text
        assert client.get('/api/sikangi/me').json()['role'] == 'learner'
        client.post('/api/logout', headers=HEADERS)
        assert client.get('/sikangi', follow_redirects=False).status_code == 303


def test_direct_id_and_nickname_login(tmp_path):
    with TestClient(create_app(tmp_path / 'game.db', ACCOUNTS, False)) as client:
        for identifier, code, account, role in [
            ('player1', '1' * 32, 'player1', 'learner'),
            (' 여니 ', '1' * 32, 'player1', 'learner'),
            ('차니', '2' * 32, 'player2', 'admin'),
        ]:
            response = client.post('/api/login', json={'account': identifier, 'code': code}, headers=HEADERS)
            assert response.status_code == 200
            assert client.get('/api/sikangi/me').json()['account'] == account
            assert client.get('/api/sikangi/me').json()['role'] == role
        for identifier in ['알 수 없는 아이디', '   ', 'admin']:
            assert client.post('/api/login', json={'account': identifier, 'code': '2' * 32}, headers=HEADERS).status_code == 401
        app = client.app
        app.state.db.register('player2', '새 닉네임', '등록한비밀번호123')
        assert client.post('/api/login', json={'account': '새 닉네임', 'code': '등록한비밀번호123'}, headers=HEADERS).status_code == 200
        assert client.get('/api/sikangi/me').json()['role'] == 'admin'
        assert client.post('/api/login', json={'account': '새 닉네임', 'code': '2' * 32}, headers=HEADERS).status_code == 401
        assert client.post('/api/login', json={'account': '차니', 'code': '등록한비밀번호123'}, headers=HEADERS).status_code == 401
        assert client.post('/api/login', json={'account': 'player2', 'code': '등록한비밀번호123'}, headers=HEADERS).status_code == 200


def test_ambiguous_nickname_and_unknown_id_rate_limit(tmp_path):
    accounts = {key: {**value, 'name': '같은 이름'} for key, value in ACCOUNTS.items()}
    with TestClient(create_app(tmp_path / 'game.db', accounts, False)) as client:
        assert client.post('/api/login', json={'account': '같은 이름', 'code': '2' * 32}, headers=HEADERS).status_code == 401
        login(client, 'player1')
        for _ in range(18):
            assert client.post('/api/login', json={'account': '없는 아이디', 'code': '잘못된 암호'}, headers=HEADERS).status_code == 401
        assert client.post('/api/login', json={'account': '없는 아이디', 'code': '잘못된 암호'}, headers=HEADERS).status_code == 429


def test_private_bank_upload_exam_storage_and_restart(tmp_path):
    subjects = ['safety', 'chemistry', 'process', 'micro']
    questions = [{
        'id': f'p2025-3-{number:03d}', 's': subjects[(number-1)//20], 'l': 'l1',
        'title': f'업로드 검증용 독립 작성 문항 {number}', 'choices': ['가', '나', '다', '라'],
        'answer': number % 4, 'explain': '검증용 해설', 'origin': 'past',
        'year': 2025, 'round': 3, 'number': number, 'pdfPage': 4,
        'source': '테스트 전용 합성 자료', 'current': True,
        'image': f'/sikangi/exam-assets/p2025-3-{number:03d}.webp',
    } for number in range(1, 81)]
    written = {**questions[0], 'id': 'w2025-3-001', 'type': 'written', 'choices': [], 'answer': None,
               'modelAnswer': '검증용 모범답안', 'image': '/sikangi/exam-assets/w2025-3-001.webp'}
    package = io.BytesIO()
    with zipfile.ZipFile(package, 'w') as archive:
        archive.writestr('bank.json', json.dumps({'questions': questions + [written]}))
        for question in questions + [written]:
            archive.writestr(question['image'].removeprefix('/sikangi/'), b'RIFF\x04\x00\x00\x00WEBP')
    app = create_app(tmp_path / 'game.db', ACCOUNTS, False)
    with TestClient(app) as client:
        assert client.get('/api/sikangi/bank').status_code == 401
        login(client, 'player1')
        assert client.get('/api/sikangi/bank').json()['registered'] is False
        assert client.put('/api/sikangi/admin/content', content=package.getvalue(), headers=HEADERS).status_code == 403
        login(client, 'player2')
        assert client.put('/api/sikangi/admin/content', content=package.getvalue()).status_code == 403
        response = client.put('/api/sikangi/admin/content', content=package.getvalue(), headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.json() == {'imported': 81, 'choice': 80, 'written': 1}
        assert len(client.get('/api/sikangi/bank').json()['questions']) == 81
        ids = [question['id'] for question in questions]
        answers = {question['id']: question['answer'] for question in questions if question['s'] != 'safety'}
        result = {'id': 'e123', 'ids': ids, 'answers': answers, 'scores': {}, 'average': 100,
                  'passed': True, 'time': 1793000000000, 'origin': 'past', 'elapsed': 100}
        state = {'read': ['l1'], 'saved_questions': [ids[0]], 'qnotes': {ids[0]: '계산 과정 메모'},
                 'responses': {'w2025-3-001': '직접 작성 답안'}, 'grades': {'w2025-3-001': 'partial'},
                 'session': {'ids': ids[:20], 'index': 2, 'score': 0, 'hideChoices': True}, 'exams': [result],
                 'exam_session': {'ids': ids, 'answers': answers, 'index': 3, 'flagged': [ids[0]],
                                  'startedAt': 1793000000000, 'deadline': 1793007200000, 'origin': 'past', 'round': '2025-3'}}
        login(client, 'player1')
        assert client.put('/api/sikangi/state', json=state, headers=HEADERS).status_code == 200
        saved = client.get('/api/sikangi/state').json()['state']
        assert saved['exams'][0]['average'] == 75
        assert saved['exams'][0]['passed'] is False
        assert saved['exams'][0]['scores']['safety'] == 0
        assert saved['exam_session']['index'] == 3
        assert saved['qnotes'][ids[0]] == '계산 과정 메모'
        assert client.get('/sikangi/exam-assets/' + ids[0] + '.webp').status_code == 200
        assert client.get('/sikangi/exam-assets/p2025-3-999.webp').status_code == 404
        invalid = {**state, 'exam_session': {**state['exam_session'], 'ids': [ids[0]] * 80}}
        assert client.put('/api/sikangi/state', json=invalid, headers=HEADERS).status_code == 422
        login(client, 'player2')
        malicious = io.BytesIO()
        with zipfile.ZipFile(malicious, 'w') as archive:
            archive.writestr('../outside.txt', '불허 파일')
        assert client.put('/api/sikangi/admin/content', content=malicious.getvalue(), headers=HEADERS).status_code == 422
        assert len(client.get('/api/sikangi/bank').json()['questions']) == 81
        assert client.get('/api/sikangi/admin/learner').json()['state']['exams'][0]['average'] == 75
    with TestClient(create_app(tmp_path / 'game.db', ACCOUNTS, False)) as client:
        login(client, 'player1')
        assert client.get('/api/sikangi/bank').json()['registered'] is True
        assert client.get('/api/sikangi/state').json()['state']['responses']['w2025-3-001'] == '직접 작성 답안'


def test_daily_statistics_survive_history_limit_and_admin_read(tmp_path):
    """일별 정답률은 최근 풀이 목록 제한으로 잘리지 않아야 한다."""
    app = create_app(tmp_path / 'game.db', ACCOUNTS, False)
    record = {
        'history': [{'id': 'q1', 'correct': True, 'time': 1793000000000}],
        'daily': {'2026-10-27': 1200},
        'daily_stats': {'2026-10-27': {'total': 1200, 'correct': 900}},
        'session': None, 'exam_session': None,
    }
    with TestClient(app) as client:
        login(client, 'player1')
        assert client.put('/api/sikangi/state', json=record, headers=HEADERS).status_code == 200
        invalid = {**record, 'daily_stats': {'2026-10-27': {'total': 1, 'correct': 2}}}
        assert client.put('/api/sikangi/state', json=invalid, headers=HEADERS).status_code == 422
        assert client.get('/api/sikangi/admin/learner').status_code == 403
        login(client, 'player2')
        saved = client.get('/api/sikangi/admin/learner').json()['state']
        assert saved['daily_stats']['2026-10-27'] == {'total': 1200, 'correct': 900}
        assert len(saved['history']) == 1
        assert saved['session'] is None and saved['exam_session'] is None
    with TestClient(create_app(tmp_path / 'game.db', ACCOUNTS, False)) as client:
        login(client, 'player2')
        assert client.get('/api/sikangi/admin/learner').json()['state']['daily_stats'] == record['daily_stats']
