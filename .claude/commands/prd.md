---
description: 최종 PRD — 입고 분석과 인터뷰를 모아 docs/product/prd.json 정본을 만들고 빌더 점검 · 승인 관문 후 출고(prd.md · html · json)
argument-hint: (선택) 제품 이름 · 범위
---

# /prd — 최종 PRD 만들기

인자: `$ARGUMENTS`
규약: [docs/product/README.md](../../docs/product/README.md) · [superpowers.md §4](../../docs/conventions/superpowers.md)

## 입력 게이트
- `docs/product/intake.json` 이 있다(없으면 `/intake` 먼저). 입고 자료가 하나도 없으면 `/req-interview` 결과만으로 써도 된다
- `uv run python scripts/warehouse.py gaps` 에서 **열린 부족 항목**이 남았으면, 남은 채로 갈지 사용자에게 한 줄로 묻는다. 갈 때는 그 항목을 PRD `open_questions` 로 옮긴다. 근거 없는 영역이 있으면 `/req-interview` 로 먼저 채우기를 권한다

## 절차
1. **스킬 호출**: `superpowers:brainstorming` 의 서면 설계 · 빌더 점검 · 승인 관문을 따른다. 설계 문서 위치는 `docs/superpowers/specs/` 가 아니라 `docs/product/prd.json` 이다
2. 처음이면 `docs/product/_template_prd.json` 을 복사해 `docs/product/prd.json` 을 만든다. 이미 있으면 그 위에 고친다(승인된 것을 고치면 `version` 을 올린다)
3. 채운다. 근거는 `intake.json` 발견(E-*), 답한 부족 항목(G-*), 인터뷰 기록(`docs/requirement/interviews/INT-*`), 요구 문서(REQ-*)
   - 제품 · 배경 · 왜 지금 · 목표/비목표/반목표 · 성공 지표(숫자)
   - 사용자(U-01…) — 역할 · 숙련도 · 기기 · 장소
   - **기능(F-001…)**: 기능마다 `sources` 필수, `priority` 필수/중요/선택, **수용 기준(F-001-AC1…)은 확인 가능한 문장 + 확인 방법**
   - 비기능(N-01…): 성능 · 보안 · 접근성(WCAG 2.2 AA · [ux-heuristics](../../docs/conventions/ux-heuristics.md)) · 가용성 · 운영 · 법규
   - 제약, 가정(고객이 말하지 않은 것은 `"by": "Claude 판단"`), 미결 질문(Q-01…, 누구 몫 · 기한)
4. `uv run python scripts/warehouse.py check` 가 통과할 때까지 형식을 고친다
4-1. **자문**: 범위를 확정하기 전에 `practice-advisor` 에이전트로 의뢰 충실도 · 놓친 관점 · 기회를 본다(빠진 운영 · 권한 · 규제 관점은 PRD 영역으로, 기회는 `/req-new` 후보로)
5. **빌더 점검**: `req-analyst` 에이전트(빌더 점검 모드)에게 `docs/product/prd.json` 경로만 주고 Superpowers `brainstorming/builder-check-prompt.md` 형식으로 묻는다 — "이 PRD 만으로 SPEC · 계획을 세울 수 있나, 무엇을 물어야 하나". 답은 한국어로 받는다. 받은 질문은 셋으로 나눈다
   - 이미 답이 있음 → PRD 를 채운다
   - 사소함 → Claude 가 정하고 `assumptions` 에 `Claude 판단` 으로 남긴다
   - 고객 몫 → 중요한 순서로 **한 메시지에 모아** 묻는다. 직접 물을 수 없으면 `open_questions` 로 남기고 `outbound/checklist/gaps.md` 로 보낸다
6. `uv run python scripts/warehouse.py out` → `outbound/prd/prd.md` · `prd.html` · `prd.json`, `outbound/checklist/acceptance.md`(인수 점검표)
7. 사용자에게 건넨다: PRD 경로(`docs/warehouse/outbound/prd/prd.html` 은 파일 하나로 열린다), 기능 수 · 필수 기능, Claude 판단 목록, 미결 질문
8. **승인 관문**: 사용자가 승인하면 `status: "승인"`, `approved: {by, date}` 를 쓰고 다시 `warehouse.py out`. 관련 REQ 문서 "확인한 결정"에 `PRD v<버전> 승인` 한 줄을 남긴다. 승인 전에는 `/foundation` · `/spec` · 구현으로 가지 않는다
9. 다음: 새 프로젝트 · 큰 범위면 `/foundation`, 이미 기반이 정해진 저장소에 기능 하나를 더하는 것이면 `/spec`(foundation 은 기존 spec 의 것을 그대로 쓴다)
