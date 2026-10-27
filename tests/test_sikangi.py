"""학습 기록의 계정 격리와 관리자 읽기 권한을 검증한다."""
from fastapi.testclient import TestClient

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
