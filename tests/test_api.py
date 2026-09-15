from fastapi.testclient import TestClient

from shisu.api.main import app


def test_헬스체크():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_신규_사용자_파밍_상태_조회():
    response = TestClient(app).get("/api/players/test-user")
    assert response.status_code == 200
    body = response.json()
    assert len(body["relic_engravings"]) == 3
    assert set(body["gems"]) == {"hp", "atk", "def", "spd", "crit"}
