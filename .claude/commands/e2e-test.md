---
description: 실연동 E2E — 실제로 띄운 스택 · 화면 · 모바일에서 흐름을 돌려 종료 코드 · 콘솔 오류 · PNG 로 판정한다(ui-smoke · checklist-smoke · kmp-smoke · e2e-kafka). 못 돌리는 표면은 판정 불가로 남긴다
argument-hint: [web | form | mobile | api | all] (비우면 바뀐 것으로 고른다)
---

# /e2e-test — 실연동 E2E

인자: `$ARGUMENTS`
규칙: 화면 확인 스킬 `nova-ui-verify`([SKILL](../skills/nova-ui-verify/SKILL.md)) · 이 PC 환경 [CLAUDE.md](../../CLAUDE.md) '이 PC 환경'

`/test` 가 단위 · 통합 테스트라면 이 명령은 **실제로 띄워서** 본다. 테스트가 녹색이어도 화면이 비어 있거나 이벤트가 안 흐를 수 있다.

## 절차
1. `python nova.py doctor` — node · npm · Playwright · JDK(JAVA_HOME) · Docker · bash 가 있는지. 없는 도구가 필요한 표면은 4의 '판정 불가'로 간다
2. **표면을 고른다**(인자가 없으면 `git diff --stat` 으로)

   | 표면 | 바뀐 것 | 명령 |
   |---|---|---|
   | `web` | 웹 화면 · `@nova/ui` · 게이트웨이 · 서비스 API | `python nova.py stack up` → `ui-smoke` → `stack down`(빈 포트 · CORS · 데모 로그인 빌드는 stack 이 맞춘다 — 스킬 2절) |
   | `form` | 체크리스트 폼 | `python nova.py checklist-smoke` |
   | `mobile` | `apps/kmp` · `kr.nova.uikit` | `python nova.py kmp-smoke`(게이트웨이 — `stack up --no-web` 주소를 자동으로) · 화면은 `kmp-snapshots` |
   | `api` | 서비스 · 이벤트 · 아웃박스 | `python nova.py e2e-kafka`(bash · Linux/WSL · 실제 Kafka) — 흐름 정본 `scripts/e2e_check.py`(로그인 → 생성 → 이벤트 소비 → 보관 → 권한 403) |
   - 새 서비스를 만들었으면 그 서비스의 핵심 흐름이 `scripts/e2e_check.py` 에 있는지 먼저 본다 — 없으면 추가가 이번 task 다
3. **실행을 맡긴다**: 표면마다 `e2e-tester` 에이전트(스킬 `nova-ui-verify` 절차 — 종료 코드 · 콘솔 오류 · 단계 수 · PNG 를 직접 연 판정)를 띄운다. 표면이 둘 이상이면 한 메시지에 함께. 포트 · DB 를 함께 쓰는 표면(`web` 과 `mobile` 의 게이트웨이)은 같은 서버를 공유하므로 서버는 메인이 한 번 띄운다
4. **판정** — 표면마다 하나

   | 판정 | 조건 |
   |---|---|
   | 통과 | 종료 코드 0 + 콘솔 오류 0 + 본 PNG(라이트 · 다크 × 넓은 · 좁은 폭 중 본 조합을 적는다) |
   | 실패 | 실패 단계 · 재현 명령 · 화면 경로 → `/debug` |
   | 판정 불가 | 도구 · 환경 없음 — **무엇이 있으면 되는지**(예: "Linux + Kafka 에서 e2e-kafka") |
5. 보고: 표면별 판정 · 숫자 · PNG 경로. 실환경 검증으로 남길 것이면 `docs/verification/` 에(main 에서)

## 하지 않는 것
- 판정 불가를 통과로 세기 — 못 돌린 것은 "안 봤다"다
- 테스트 데이터를 지우지 않고 남기기 — 스모크는 고유 이름(시각 포함)으로 만들고 정리한다
- 엔드포인트 목록을 이 문서에 베끼기 — 흐름 정본은 `scripts/e2e_check.py` · `scripts/ui_smoke.py` 다
