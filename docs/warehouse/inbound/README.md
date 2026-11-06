# docs/warehouse/inbound — 입고 (원본 자료를 넣는 곳)

> 한 줄 요약: 프로그램 개발에 필요한 **원본 입력 자료**를 종류별 폴더에 넣는다. `/intake` 가 이 폴더를 심층 분석해 고객 요구와 필요한 것을 파악한다. 출고 쪽: [outbound](../outbound/README.md)

| 읽는 순서 | 폴더 | 무엇을 넣나 |
|---|---|---|
| 1 | [`checklist/`](checklist/README.md) | 프로젝트 기본정보 체크리스트 · 고객이 채워 준 질문지 · 요구 점검표(고객이 **채워서 준** 것) |
| 2 | [`prd/`](prd/README.md) | 받은 PRD · 기획서 · 기능 목록 · 제안요청서(RFP) · 요구를 정한 회의록 · 메일 (`.md` `.pdf` `.txt` · `.docx` 는 PDF 로 바꿔 넣는다) |
| 3 | [`spec/`](spec/README.md) | 받은 기술 명세 · API 계약(OpenAPI · Swagger) · 데이터 사전(설명형) · 인터페이스 정의서 · 연동 규격서 |
| 4 | [`db-sql/`](db-sql/README.md) | **이미 돌고 있는 DB 의 실물** — DDL · 마이그레이션 · 쿼리 · 테이블 정의서 |
| 5 | [`html-mockup/`](html-mockup/README.md) | 화면 · 상태 · 상호작용을 담은 HTML 목업(`mockup_<화면>.html`, 자산은 같은 폴더 아래) |
| 6 | [`screenshot/`](screenshot/README.md) | 현행 시스템 화면 캡처 · 손그림 와이어프레임 · 화이트보드 사진 · 구조도 |
| 7 | [`claude-code-handoff/`](claude-code-handoff/README.md) | 다른 저장소 · 다른 세션 · 외부 협업자가 건넨 인계서 · 요약 · 상태 스냅샷 |
| 8 | [`etc/`](etc/README.md) | 위 어디에도 안 맞는 것 — 용어집 · 데이터 샘플 · 경쟁 제품 조사 · 참고 링크 모음 |

- 분석은 `/intake`. 파일마다 지문(sha256)을 `docs/product/intake.json` 에 남기므로, 새로 넣거나 바꾼 파일만 다시 분석한다
- 각 폴더의 `README.md` 는 지우지 않는다(빈 폴더도 git 에 남도록)
