# 0.3.0 확장 기능

## 화면

- 레이드: 난이도·보스 선택 → 혼자 도전 또는 협동 방 만들기 → 참가자별 매 턴 스킬 선택. 협동은 살아 있는 두 신수가 모두 선택해야 공유 보스 HP가 갱신된다. 진행 중인 턴·체력·쿨타임은 저장되며, 대기방은 15분 만료, 화면은 5초 간격 갱신된다.
- 성장과 스킬: 현재 성장 관문·강화된 4종 스킬·혼 소모 잠재 성장 표시.
- 강화 공방: 장착 보물 강화, 방어구 강화, +15 신화 방어구 별 각성, 종족 보물 제작·분해.
- 환생: Lv.99에서 초기화 항목을 확인하고 ‘환생’을 입력. 기존 도메인 환생 규칙 사용.
- 상점: 기존 상품 전체 구매 및 사용. 재료는 공방에서 소모하고 생명의 보석은 패배 시 자동 사용.
- 던전: 신화 Lv.70, 고대 Lv.99 추가. 이전 난이도 4대 레이드 보스 토벌 필요.

## 전투 규칙과 검증 범위

기존 종족·보스 기본 스탯, EXP 공식, 강화·잠재 비용을 재사용한다. 웹 전투는 별도 순수 계산 모듈에서 개인/협동을 함께 처리한다. 최대 100턴에 처치하지 못하면 패배다. 패배 기력·건강도 저장한다. 전체 밸런스와 Discord 전투 결과의 일치 검증은 수행하지 않았다.

각인 피해 증가는 조건을 확인한 뒤 합산하여 한 번 적용한다. 피해 감소 합계는 85%까지이며, 치명 피격 감소·확률 반감·보호막은 이어 적용한다. 회복 증가와 흡혈량 증가를 분리한다. 단계별 스킬은 원본의 복사본에서 계산하고 내부 스킬 ID를 유지한다. 3·4단계 표시 이름에는 각성·초월 접두어를 붙인다. 신화·고대 던전의 신규 보상 배율은 밸런스 검증 대상이다.

## Supabase 백업 연결

현재 게임의 원본 저장소는 SQLite다. 클라우드는 서버 전용 복구용 백업이며 두 계정 저장을 한 스냅샷으로 보관한다. SQLite 세션과 중복 요청 이력은 클라우드에 올리지 않는다. 로컬 DB 전체 백업도 유지한다.

1. Supabase SQL 편집기에서 `docs/supabase.sql`을 실행한다.
2. 서버에 `SUPABASE_URL`, `SUPABASE_SECRET_KEY` 또는 `SUPABASE_SERVICE_ROLE_KEY`를 비밀 환경변수로 설정한다.
3. `SHISU_CLOUD_SLOT`으로 환경별 백업 이름을 지정한다. 기본값은 `default`다.
4. `SHISU_CLOUD_BACKUP=true`를 설정하고 재시작하면 60초마다 백업한다. 실패 시 로컬 저장은 유지하며 이후 주기에 재시도한다.

공식 방식: [Supabase REST API](https://supabase.com/docs/guides/api), [행 수준 보안과 서버 역할](https://supabase.com/docs/guides/database/postgres/row-level-security). 키를 웹 화면이나 Git에 넣지 않는다.

## 세이브 이전·복원

지원 형식은 Shisu 저장 스키마 2, DAMAGOCHI 17/18의 pet/inventory JSON이다. 현재 운영 데이터를 자동으로 덮어쓰지 않는다. 이전 명령은 DB 전체 `.bak`를 만든 뒤 계정을 원자적으로 교체하고 해당 계정의 세션을 만료시킨다. 원본 메타데이터는 `legacy_metadata`에 보존한다. 이전과 클라우드 복원은 서버를 중지한 상태에서 실행한다.

```powershell
$env:PYTHONPATH = 'src'
& 'C:/Users/AI-00/anaconda3/envs/torch-gpu-126/python.exe' -X utf8 -m shisu export-save --account player1 --output '.local/player1-export.json'
& 'C:/Users/AI-00/anaconda3/envs/torch-gpu-126/python.exe' -X utf8 -m shisu import-save --account player1 --input '.local/legacy-save.json'
& 'C:/Users/AI-00/anaconda3/envs/torch-gpu-126/python.exe' -X utf8 -m shisu cloud-backup
& 'C:/Users/AI-00/anaconda3/envs/torch-gpu-126/python.exe' -X utf8 -m shisu cloud-import --account player1
```

기존 계정을 교체하려면 `--replace`를 추가한다. DAMAGOCHI Supabase `user_saves`에서 이전하려면 `cloud-import --account player1 --legacy-id 원본사용자ID`로 원본 ID와 대상 계정을 명시한다. 두 계정 클라우드 복원은 같은 백업에서 각각 수행하고 서버를 다시 시작한다. 원본 `user_saves`는 읽기만 한다. 0.1 파밍 시제품 JSON은 실제 신수 정보가 없으므로 이 명령으로 이전하지 않는다.

## 사용자 플레이 점검 순서

1. 레이드 한 번 도전 후 기력·건강·전투 기록 확인.
2. 한 계정으로 협동 방을 만들고 다른 계정으로 참가하여 양쪽 결과 확인.
3. 보상 장비 장착 → 강화·각인 → 잠재 성장, 성장 관문 해제 확인.
4. 신화·고대 던전과 99레벨 환생 확인. 환생은 저장을 백업한 뒤 진행.

이 버전에서 실제 클라우드 연결과 운영 세이브 이전은 실행하지 않았다. 외부 서버 배포도 별도 설정이 필요하다.
