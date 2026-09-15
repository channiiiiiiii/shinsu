# 두 사람 운영 가이드

## 구성

브라우저 → FastAPI 한 프로세스 → SQLite 한 파일. 원본 게임 규칙은 `domain/legacy`, 웹 행동은 `application/game.py`, 트랜잭션은 `infrastructure/database.py`에 있다.

`domain/farming.py`, `domain/models.py`, `application/farming_service.py`, `infrastructure/json_repository.py`는 0.1 호환 코드다. 0.2 웹 API에서는 호출하지 않는다.

## 로컬 시작

프로젝트 폴더에서 `./start.ps1` 실행 후 `http://127.0.0.1:8000`에 접속한다. 첫 실행에서 `.local/accounts.json`에 서로 다른 무작위 접속 코드 두 개를 생성한다. 각 사람은 자기 계정과 코드를 사용한다. 접속 코드 파일은 Git에서 제외되며 화면이나 로그에 코드 자체를 출력하지 않는다.

의존성이 없을 때 학교 환경 설치:

```powershell
& 'C:/Users/AI-00/anaconda3/envs/torch-gpu-126/python.exe' -m pip install -e '.[dev]'
```

로컬 실행은 이 PC에서만 접근하도록 127.0.0.1에 바인딩한다. 인터넷용 실행에서는 `SHISU_COOKIE_SECURE=true`와 HTTPS를 사용한다.

## 인터넷 배포

1. Render에서 GitHub `channiiiiiiii/shinsu` 저장소를 Blueprint로 연결한다.
2. `render.yaml`의 `0.5c-512mb`(화면 표시: 0.5 CPU / 512 MB, 월 $7) 서비스와 1GB 영구 디스크 비용을 확인한다. `$7`은 Hobby 워크스페이스 선택 화면이 아니라 Web Service의 Compute 선택 단계에 표시된다.
3. `SHISU_ACCOUNTS`에 `.local/accounts.json`의 JSON 내용을 비밀 환경변수로 입력한다. 코드를 저장소에 커밋하지 않는다.
4. 배포 후 발급된 HTTPS 주소에서 두 계정으로 로그인한다.
5. 한 계정으로 던전 진행 → 로그아웃 → 다른 계정 저장 격리 확인 → 서버 재시작 후 보존 확인.

실제 유료 서비스 생성은 이 작업에서 수행하지 않았다. 호스팅 계정에서 위 설정을 적용해야 외부 접속 주소가 생긴다.

Render의 기본 파일시스템은 재배포·재시작 시 초기화되므로 DB 경로는 반드시 `/var/data/shinsu.sqlite3`로 두고 영구 디스크에 저장한다. 디스크를 사용하는 단일 인스턴스 배포에는 잠깐의 중단이 발생할 수 있다.

공식 근거: [영구 디스크](https://render.com/docs/disks), [배포 설정](https://render.com/docs/blueprint-spec).

## 백업과 복구

```powershell
$env:PYTHONPATH = 'src'
& 'C:/Users/AI-00/anaconda3/envs/torch-gpu-126/python.exe' -X utf8 -m shisu backup --output 'data/backup-20260915.sqlite3'
```

SQLite 백업 API로 일관된 복사본을 만든다. 백업에는 세션 정보도 포함되므로 비공개 보관한다. 외부 위치에도 정기 복사해야 서버 디스크 장애에서 복구할 수 있다. 복구는 서버를 중지하고 기존 DB를 별도 보관한 뒤, 백업 파일을 `SHISU_DB_PATH` 대상으로 지정해 재시작한다.

## 버전과 데이터

- 앱 0.2.2 / 신규 게임 저장 스키마 2. 미래 버전은 오류 처리하며 초기화하지 않는다.
- 0.1의 `data/players.json`과 DAMAGOCHI 운영 Supabase 세이브는 수정하지 않는다. 운영 세이브 이전은 계정 대응과 백업을 확인한 별도 작업이다.
- 두 계정의 ID는 고정한다. 닉네임만 변경해도 세이브는 유지된다.
- 접속 코드를 교체해도 기존 세션은 최대 7일 유지된다. 즉시 차단이 필요하면 운영 중지 후 `sessions` 테이블의 해당 계정 세션을 제거한다.
- `requests`는 재전송 중복 방지 이력이다. 임의 삭제하면 오래된 요청의 재실행이 가능해지므로 삭제하지 않는다.
- 실행 프로세스는 1개로 유지한다. 로그인 속도 제한은 프로세스 메모리에서 처리된다.

## 이번 버전 범위

돌봄·훈련·수면·치료·1회 던전·보석 합성/장착·장비 장착·각인·사탕 구매/사용을 제공한다. 공유 레이드, 웹 개인 레이드, 보물 강화, 환생 화면, Supabase 연결은 아직 없다. 따라서 레이드 해금 이후 성장과 보물 각인석 파밍은 아직 웹에서 완결되지 않는다.
