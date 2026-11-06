# 결함 · 변경요청 원장

운영 중에 들어오는 **결함(defect)** 과 이미 만든 것을 바꿔 달라는 **변경요청(change)** 을 한 그릇에 받는다. 새 기능은 여기가 아니라 요구(`/req-new`)로 간다.

- 원천: [`issues.json`](issues.json) — 상태 JSON(ADR-004). 손으로 고치지 않고 `python nova.py issue …` 로 쓴다
- 보기: 이 문서 아래의 표 절은 생성물이다(`python nova.py issue render` — `add` · `set` 이 자동으로 다시 만든다). `python nova.py issue check` 가 lint 에서 형식 · 게이트 · 표 일치를 검사한다
- 사후기록: [`postmortem/`](postmortem/_template.md) — P0 종결 조건

## 흐름
| 등급 | 정의 | 다음 |
|---|---|---|
| P0 | 서비스 중단 · 보안사고 · 데이터 손실 | `/hotfix`(`.claude/commands/hotfix.md`) — 재현 테스트(RED) 먼저 → 최소 수정 → `/release`(patch) → `/postmortem`(`.claude/commands/postmortem.md`) → 종결 |
| P1 | 핵심 기능 결함(우회로 없음) | `/req-new` → `/plan-new`, 24시간 안 착수 |
| P2 | 일반 결함(우회로 있음) | `/req-new` → `/plan-new`, 다음 릴리스 |
| P3 | 개선 · 사소 | 백로그 — 분기 정리 |

변경요청은 등급과 별개로 영향도 L1~L3 를 매긴다(`/change`(`.claude/commands/change.md`) — `python nova.py impact …` → 5줄 보고 → 사용자 승인).

## 기계가 거부하는 것
- 재현 · 기대 · 실제 · 환경 4요소 중 하나라도 비거나 공백뿐인 접수
- P0 결함을 재현 테스트(`경로::이름`, 파일 실재) · 사후기록(파일 실재) 없이 closed 로
- P0 결함을 보류를 정한 사람(`--approved-by`) 없이 deferred 로
- 변경요청을 영향(impact) · 등급(level) · 승인자(approved-by) 없이 in_progress 이상으로, L3 인데 실재하는 ADR 없이
- worktree 에서의 쓰기(단일 기록자 — ADR-008)

상태: `open`(접수) → `triaged`(분류) → `in_progress`(진행) → `verifying`(확인 중) → `closed`(종결), 재현 불가 · 중복은 `deferred`(보류).

<!-- 생성 시작: scripts/issues.py render — 이 아래부터 '생성 끝' 까지는 손으로 고치지 않는다 -->

> 생성물 — scripts/issues.py render · 원천 `docs/issues/issues.json`. 고치려면 `python nova.py issue set …`

열린 항목 2개 · 전체 2개

| ID | 종류 | 등급 | 상태 | 제목 | 근거 · 영향 | 접수 |
|---|---|---|---|---|---|---|
| ISS-261105-02 | 결함 | P2 | 접수 | 운영 게이트웨이가 메모리 DB(sqlite://)로 뜬다 — DATABASE_URL_GATEWAY 기본값 · k3s 배포 원천에 값 없음 · 운영 안전장치가 게이트웨이 DB 를 검사하지 않음 | — | 2026-11-05 |
| ISS-261105-01 | 결함 | P2 | 분류 | 메모리 DB(sqlite:// StaticPool)에서 배경 스레드의 연결 반납 ROLLBACK 이 다른 스레드의 커밋 전 쓰기를 지운다 — 삭제 204 뒤 항목이 다시 보임 | — | 2026-11-05 |

<!-- 생성 끝 -->
