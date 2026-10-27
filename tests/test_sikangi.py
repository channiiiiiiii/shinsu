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
        for path in ['/sikangi', '/sikangi/', '/sikangi/app.js',
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
