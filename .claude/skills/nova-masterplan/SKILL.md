---
name: nova-masterplan
description: 마스터플랜 새 판본 초안을 쓴다 — "마스터플랜 만들어줘", "전체 로드맵 · 모듈 나누기", "병렬 묶음 정하기", "새 판본 열기", "공통 영역 완료 선언" 때 쓴다. prd.json · spec.json · foundation ADR 를 읽어 docs/plans/drafts/master_plan_vX.Y-draft.md 를 쓰고, 종료 조건 · 하지 않는 것 · 공통 영역 완료 선언 · 병렬 묶음 표를 parallel-gate 가 읽는 형식으로 채운 뒤, 사람이 정하면 masterplan adopt 로 채택한다. 요구 하나짜리 계획은 /plan-new 로 간다.
---

# nova-masterplan — 표는 설명이 아니라 분배 계약

형식 정본: `docs/plans/README.md` §1(판본 · 채택 · 봉인) · §5(목표 · 종료 조건 · 하지 않는 것) · §6(병렬 · 공통 영역). 도구: `scripts/masterplan.py` · `scripts/parallel.py`.

## 1. 입력을 읽는다
- `docs/product/prd.json` · `spec.json`(있으면) · `docs/adr/` 의 foundation 결정 · 지금 정본 `docs/plans/master_plan.md` · 이력 `master_plan_changelog.md`
- 열린 요구 `docs/requirement/requirement_index.md` · 열린 판본 `python nova.py release status` · 진척 `python nova.py progress`
- 대장 `docs/registry/*.md` — 서비스 · 표 · 이벤트의 실제 소유

## 2. 자문 — 그리기 전에 묻는다
`practice-advisor` 에이전트에게 맡길 수 있다(원문 · 선행사례 · 밖 근거를 모아 아래 세 갈래로 돌려준다).
1. **충실도** — 고객이 말한 것과 다른 것을 넣고 있지 않은가(원문 대조)
2. **놓친 관점** — 운영 · 권한 · 감사 로그 · 마이그레이션 · 삭제/보존 · 장애 · 한국 규제(ISMS-P · 개인정보보호법 · AI 기본법). 안 넣는 것은 '하지 않는 것'에 이유와 함께
3. **기회** — 다른 프로젝트와 같은 것은 Nova 공통으로 올릴 후보(새 요구로)

## 3. 초안을 쓴다(본문 초안은 `masterplanner`, 병렬 묶음 표는 `orchestrator` 에이전트에 맡길 수 있다) — `docs/plans/drafts/master_plan_vX.Y-draft.md`
- 머리 표: 버전 `**vX.Y**` · 상태 `초안` (초안은 '정식'일 수 없다 — lint 가 잡는다)
- **목표** 한 문장 · **종료 조건** 표(1~7개, 한 번 돌리거나 한 번 보고 답이 나오는 것 — `goals.py` 형식) · **하지 않는 것**
- **공통 영역 완료 선언** 표 `| 항목 | 상태 | 증거 |` — 전부 완료(+증거)여야 병렬이 열린다
- **병렬 묶음** 표 `| 묶음 | 경로 | 담당 REQ | 선행 묶음 |`(선행 묶음은 선택 — 비우면 첫 파도, `/dispatch` 가 파도 순서로 쓴다) — 경로 글롭이 서로 겹치면 병렬 게이트가 막는다. 묶음마다 **소유 서비스 · 표**를 경로로 표현한다(서비스는 자기 DB 만)
- 계획 목록은 요구마다 한 줄(`plan_REQ_NN` 은 `/plan-new` 가 만든다)
- 그 밖의 블록(모듈 지도 · 요구 로드맵 · 의존 그래프 · 횡단 관심사 · 큰 그림 ERD · **M0 = 걷는 골격** · 위험 · 되돌리기 · 도메인 채택 표)과 진입 분기 · 입력 관문 · 자문 처분 규칙은 `/masterplan` 명령 0~3단계가 정본이다 — 명령으로 들어왔으면 그 순서를 따른다

## 4. 점검 → 채택
1. `python nova.py masterplan check` · `python nova.py parallel-gate`(묶음 표를 넣었으면)
2. 사용자에게 바뀐 것 · 대가를 보여 주고 **결정을 받는다**(되돌리기 어려운 결정 — SOUL 되돌림 원칙)
3. `python nova.py masterplan adopt docs/plans/drafts/<초안> --why "<근거 REQ>" --what "<바뀐 것>"` — 지난 판본 봉인 · 이력 · 초안 삭제
4. `/history-new` → 커밋 · `git_record.py`

## 하지 않는 것
- 정본(`master_plan.md`)이나 보관본(`archive/`)을 직접 고치기 — 봉인 해시가 잡는다
- 끝이 없는 종료 조건("전부 찾는다 · 빠짐없이") — 한 번 보고 답이 나오는 형태로
