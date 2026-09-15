# Shisu 라이브 서비스 구축 작업

- 상태: 0.1.0 MVP 구현 및 검증 완료
- 기준일: 2026-09-15
- 원본: `C:/G_drive/.Game/DAMAGOCHI`
- 원칙: 원본은 수정하지 않고 검증된 규칙만 독립 도메인으로 이식

## 목표

Discord에 종속된 DAMAGOCHI를 브라우저에서 실행 가능한 Shisu 라이브 서비스로 분리한다.

## 계획과 검증 기준

1. 프로젝트 경계 분리 → 도메인/application/infrastructure/api/web 간 역방향 의존 없음
2. 신규 파밍 가이드 이식 → 각인·보석·드랍·Stage 단위 테스트 통과
3. 상태 변경 안정화 → 사용자별 Lock 및 저장 실패 시 메모리 상태 롤백
4. 웹 MVP 제공 → 상태 조회, 각인, 잠금, 보석 합성·장착 API와 모바일 UI 동작
5. 버전 관리 → 독립 Git, SemVer, CHANGELOG, save_version 명시

## 완료 기준

- [x] 원본 `task.md`, `implement.md`, 신규 파밍 가이드 확인
- [x] 기존 파밍 적용 항목 코드 대조
- [x] 독립 디렉터리 구조 및 실행 진입점 작성
- [x] 파밍 핵심 규칙 이식
- [x] PWA 웹 화면 작성
- [x] 전체 자동 테스트 통과 (`8 passed`)
- [x] 독립 Git 저장소와 `main` 브랜치 초기화
- [x] GitHub 사용자 `channiiiiiiii` 작성자 설정 및 0.1.0 초기 커밋
