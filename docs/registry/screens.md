# 화면 대장

> 생성 파일 — `uv run python scripts/ledgers.py` 가 코드에서 파생한다(ADR-004). 직접 고치지 않는다 — 원천(코드 · 선언)을 고친다.

화면 ↔ 라우트 ↔ API ↔ 표 ↔ 상태. 새 화면은 머리 주석 `/** @screen 이름 · @status 기획|설계|개발|완료 */` 를 쓰고, 부르는 API 는 코드에서 자동으로 잡힌다. 표는 그 API 를 가진 서비스의 표(서비스 단위).

| 화면ID | 앱 | 이름 | 라우트 | 사용 API | 사용 표 | 상태 |
|---|---|---|---|---|---|---|
| SCR-WAPP-0009 | app | 디자인 갤러리 — 대시보드 | /design/dashboard | — | — | 완료 |
| SCR-WAPP-0001 | app | 디자인 갤러리 | /design | — | — | 완료 |
| SCR-WAPP-0010 | app | 디자인 갤러리 — 설정 | /design/settings | — | — | 완료 |
| SCR-WAPP-0011 | app | 디자인 갤러리 — 스플릿 | /design/split | — | — | 완료 |
| SCR-WAPP-0002 | app | 도움말 | /help | — | — | 완료 |
| SCR-WAPP-0003 | app | 항목 상세 | /items/[id] | POST /sample/items/{item_id}/archive, POST /sample/items/{item_id}/restore, GET /sample/items/{item_id} | item, item_activity | 완료 |
| SCR-WAPP-0004 | app | 항목 만들기 | /items/new | POST /sample/items | item, item_activity | 완료 |
| SCR-WAPP-0005 | app | 항목 목록 | /items | POST /sample/items/{item_id}/archive, POST /sample/items/{item_id}/restore, DELETE /sample/items/{item_id}, GET /sample/items | item, item_activity | 완료 |
| SCR-WAPP-0006 | app | 로그인 | /login | — | — | 완료 |
| SCR-WAPP-0007 | app | 운영 모니터링 | /ops | GET /ops/monitoring/overview | — | 완료 |
| SCR-WAPP-0008 | app | 홈 | / | — | — | 완료 |
