---
description: 코드 검토 — 새 검토자에게 요구 · 계획 · 커밋 범위를 주고 결과를 리뷰 문서로 남긴다(superpowers:requesting-code-review · receiving-code-review)
argument-hint: <범위: BASE..HEAD 또는 task ID> [plan_REQ_NN]
---

# /review-request — 코드 검토 요청 · 반영

인자: `$ARGUMENTS`
규칙: [docs/conventions/superpowers.md §5](../../docs/conventions/superpowers.md)

## 절차
1. **스킬 호출**: `superpowers:requesting-code-review`. 검토 자료: 요구(REQ) · 계획(plan_REQ_NN, §11 전역 제약 · 검토 초점) · BASE/HEAD 커밋. Nova 규약도 기준에 넣는다: [ui.md](../../docs/conventions/ui.md) · [ux-heuristics.md](../../docs/conventions/ux-heuristics.md) · [backend.md](../../docs/conventions/backend.md) · CLAUDE.md 규칙 0(한국어)
2. `code-reviewer` 에이전트에게 Superpowers `requesting-code-review/code-reviewer.md` 양식을 함께 주고 맡긴다(읽기 전용). 범위에 인증 · 권한 · 외부 경계가 있으면 `security-auditor`, 화면이 있으면 `accessibility-auditor` · `design-token-guardian`, 계약 · 스키마면 `contract-auditor`, 도메인 팩(`packs/<팩>/`)이면 `<팩>-specialist`(팩 이름의 `_` 는 `-`) 를 **같은 메시지에** 함께 띄운다. 결과는 한국어로 받고, 판정은 main 이 한다
2-1. 셋 이상 띄웠으면 `integrator` 에이전트에게 보고를 넘겨 중복 · 상충 · 덮지 못한 곳을 갈라 받는다(판정은 main)
3. `uv run python scripts/docs_new.py review "<제목>"` → `docs/reviews/review_YYMMDD_NN.md` 에 지적을 심각도(치명 · 중요 · 경미) 순으로 남긴다(본문이 길면 `doc-writer` 에이전트에게 그 파일 경로와 검토 결과를 주고 채우게 한다 — 번호 · 인덱스는 main)
4. **반영**(구조 지적 — 동작을 바꾸지 않는 정리 — 은 `refactorer` 에이전트에 맡길 수 있다): `superpowers:receiving-code-review` — 지적마다 코드로 사실을 확인하고, 맞으면 고치고 틀리면 근거를 들어 반박한다. 맞장구 · 무조건 수용 금지. 처리 결과(수용 · 반박 · 보류 + 근거)를 리뷰 문서 "처리" 칸에 쓴다. **수용한 것을 고치기 전에** 리뷰 문서에 반영 묶음의 **목표 · 완료 조건 · 하지 않는 것**을 적는다 — 지금 고치는 것은 검토 대상 일의 종료 조건을 깨거나 치명적인 것만, 그 밖은 🆕 '다음 판본'. 반영하다 새로 보인 것은 같은 회차에 다시 고치지 않는다(한 세대 규칙 — [plans README §5](../../docs/plans/README.md))
5. 고친 뒤 `python nova.py test` · `lint` 출력 확인 → 커밋 · git 기록, 리뷰 인덱스의 마지막 칸에 처리 상태
