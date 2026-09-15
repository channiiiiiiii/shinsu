# 신수 · Shinsu 0.3.0

두 사람이 각자의 신수를 키우는 웹게임. HTML/CSS/JS 화면과 FastAPI 게임 서버를 함께 실행하고 SQLite에 저장합니다.

## 바로 실행

```powershell
Set-Location 'C:/G_drive/.Game/Shisu'
./start.ps1
```

`http://127.0.0.1:8000`에서 접속합니다. 첫 실행 시 생성되는 `.local/accounts.json`에서 본인 계정의 접속 코드를 확인하세요. 코드와 DB는 Git에서 제외됩니다. 패키지가 없으면 지정된 Python으로 `-m pip install -e '.[dev]'`를 먼저 실행합니다.

## 사용 가능한 기능

- 두 계정 로그인·로그아웃, 자기 데이터만 접근
- 랜덤 신수 부화·먹이·목욕·훈련·쓰다듬기·수면·치료
- 종족별 성장 Stage 1~4 이미지와 로그인 대표 이미지
- 원본 던전 1회 탐험과 보석·재료·장비 획득
- 보석 합성·장착, 장비 장착, 각인·잠금, 사탕 구매·사용
- 서버 저장, 같은 요청 중복 지급 방지, SQLite 백업
- 개인·2인 협동 레이드, 5대 보스·5개 난이도, 토벌 기록·혼·보물 각인석 보상
- 성장 스킬·조건부 각인 효과, 잠재 성장, 신화·고대 던전
- 보물·방어구 강화, 방어구 별 각성, 제작·분해, 환생, 전체 상점
- 기존 DAMAGOCHI 세이브 이전 명령, Supabase 선택적 자동 백업·복원

## 파일 구성

```text
web/                           로그인·신수·모험·가방·각인 화면
src/shisu/api/main.py           인증 및 HTTP API
src/shisu/application/game.py   게임 행동과 저장 모델 연결
src/shisu/domain/legacy/        원본 신수·전투·파밍·장비 규칙 스냅샷
src/shisu/infrastructure/       저장소·세션·트랜잭션
tests/                         도메인·API·동시성·브라우저 검증
docs/                          가이드 대조와 운영 안내
render.yaml                    유료 영구 저장 배포 설정
.github/workflows/test.yml      Push·PR 자동 검사
```

`domain/legacy`는 DAMAGOCHI 독립 복사본에 웹 연결을 위한 각인·성장 수정과 상위 던전 확장을 더한 코드입니다. 웹 레이드 계산은 `domain/combat.py`를 사용합니다. 실제 운영 데이터·비밀키·Discord 봇은 포함하지 않습니다. 0.1 파밍 전용 모듈들은 호환 기록으로 남아 있으며 현재 API에서는 사용하지 않습니다.

## 검증

```powershell
& 'C:/Users/AI-00/anaconda3/envs/torch-gpu-126/python.exe' -X utf8 -m pytest -q
```

브라우저 검사는 별도 Playwright와 Edge가 있는 환경에서 `tests/browser_smoke.py`로 실행합니다.

## 운영 및 버전

[운영 가이드](docs/OPERATIONS.md)에 인터넷 배포·접속 코드·백업 방법이 있습니다. Render 설정은 유료 서비스와 영구 디스크를 사용합니다. 아직 외부 서비스에 배포한 상태는 아닙니다.

앱 버전은 0.3.0, 신규 저장 스키마는 2입니다. 변경은 [CHANGELOG.md](CHANGELOG.md)에 누적합니다. 원격 저장소는 `channiiiiiiii/shinsu`입니다.

0.3.0은 기능 추가 버전이며 수동 플레이·밸런스 검증은 사용자 수행 범위입니다. 클라우드 백업은 비밀 환경변수와 테이블 설정 후 활성화됩니다. 세이브 이전은 원본과 대상 계정을 명시하는 명령으로 수행합니다. [기능 안내](docs/EXPANSION.md)와 [대조표](docs/FARMING_GUIDE_AUDIT.md)를 참고하세요.
