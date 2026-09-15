# Shisu

기존 DAMAGOCHI의 검증된 육성·파밍 규칙을 독립 웹 라이브 서비스로 재구성한 프로젝트입니다.

## 구조

```text
src/shisu/domain          순수 게임 규칙과 상태 모델
src/shisu/application     유스케이스, 사용자별 동시성·저장 경계
src/shisu/infrastructure  JSON/Supabase 등 외부 저장 구현
src/shisu/api             FastAPI HTTP 계층
web                       모바일 우선 웹/PWA
tests                     도메인·API 회귀 테스트
docs                      설계와 원본 가이드 대조 문서
```

## 실행

학교 환경:

```powershell
& 'C:/Users/AI-00/anaconda3/envs/torch-gpu-126/python.exe' -m pip install -e '.[dev]'
& 'C:/Users/AI-00/anaconda3/envs/torch-gpu-126/python.exe' -m uvicorn shisu.api.main:app --app-dir src --reload
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다. 기본 저장 위치는 `data/players.json`입니다.

## 버전 정책

- 앱 버전은 `pyproject.toml`의 Semantic Versioning을 사용합니다.
- 저장 데이터는 앱 버전과 별개인 `save_version`으로 마이그레이션합니다.
- 사용자에게 보이는 변경은 `CHANGELOG.md`에 누적합니다.
- `main`은 배포 가능 상태만 유지하고 기능 작업은 `feature/*` 브랜치를 권장합니다.

