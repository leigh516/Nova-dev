---
description: 정적 · 계약 검증 — 구현을 마치고 task 를 끝났다고 표시하기 전에 lint 를 단계별로 돌려 위반을 가르고, 바뀐 축(보안 · 접근성 · 토큰 · 계약)만 판정 에이전트를 한 메시지에 함께 띄운다. 실행 테스트는 /test, 화면은 /e2e-test
argument-hint: [task ID | REQ-YYMMDD-NN] (선택)
---

# /verify — 정적 · 계약 검증

인자: `$ARGUMENTS`
규칙: 게이트 표 [/deep-audit §1](deep-audit.md) · [audit_scope.py](../../scripts/audit_scope.py) · 완료 주장 [superpowers.md §5](../../docs/conventions/superpowers.md)

## 절차
1. 바뀐 범위를 고정한다 — `git status -s` · `git diff --stat`(task 가 있으면 그 task 의 파일). 이 범위가 아래 축 선택의 근거다
2. **lint 축**: `verifier` 에이전트에 맡긴다 — `python nova.py lint` 를 돌리고, 멈춘 단계 뒤는 단계별 스크립트로 이어 돌려(예: `uv run python scripts/naming.py check`) 단계마다 통과 · 위반 · 분모를 받는다. 출력을 `| tail` 로 자르지 않는다
3. **바뀐 축만 함께 띄운다**(한 메시지에 — 모두 읽기 전용이라 서로 방해하지 않는다)

   | 바뀐 것 | 에이전트 |
   |---|---|
   | 항상 | `verifier`(위 2) |
   | 인증 · 입력 · 권한 · 의존성 · 비밀값 | `security-auditor` |
   | 화면 · `@nova/ui` · `kr.nova.uikit` | `accessibility-auditor` · `design-token-guardian` |
   | 기존 API · 이벤트 · 표 구조 · 명령 인자 | `contract-auditor` |
   - 위임 지시에 범위(1)와 "한국어 4절 보고(핵심 답 · 실측 · 근거 · 미해결)"를 싣는다
   - 셋 이상 띄웠고 보고가 겹치거나 부딪히면 `integrator` 로 합친다. **판정은 메인이 한다** — 보고는 가설이다
4. **문서 · 기록만 바뀌었으면**(코드 표면 0) 위 3 대신 `uv run python scripts/docs_index.py --check` · `uv run python scripts/claude_check.py --check` 를 돌리고, 왜 3을 건너뛰었는지 한 줄 남긴다("코드 · 계약 변경 0")
5. 결과를 판정한다

   | 결과 | 다음 |
   |---|---|
   | 모두 통과 | `/test`(실행 테스트 · 종료 조건) → 화면이면 `/e2e-test` |
   | 위반 — 되돌릴 수 있고 범위 안 | 고친 뒤 이 명령을 다시 |
   | 위반 — 계약 · DB 구조 · 권한 확대 | 고치지 않고 사용자에게(되돌리기 어려움) |
   | 같은 위반이 반복 | `/learn` 후보로 보고에 적는다 |
6. 보고: 통과 단계 수 / 전체 · 위반 `파일:줄` · 띄운 축과 뺀 축(뺀 이유)

## 하지 않는 것
- 게이트의 의미 · 단계 바꾸기 — 고치려면 REQ
- 생성물을 손으로 고쳐 lint 맞추기 — 원천을 고치고 `python nova.py gen`
- 통과 증거 없이 task 를 `- [x]` 로 — 체크는 `/test` 까지 녹색일 때
