---
description: 행동 테스트(psg05 이름 /test) — 전체 테스트 · 요구의 종료 조건을 실제로 돌려 판정한다. 통과 전에는 task 를 끝났다고 표시하지 않는다
argument-hint: [REQ-YYMMDD-NN]
---

# /test — 행동 테스트

인자: `$ARGUMENTS`

psg05 의 `/test` 이름으로 부르는 입구다. 정적 · 계약 검증은 `/verify`, 화면을 띄워 보는 것은 `/e2e-test` 다.

## 절차
1. `python nova.py test` — 전체(common · 서비스별 · 저장소). 출력이 길면 `tester` 에이전트에게 맡겨 통과 · 실패 요약을 받는다
2. 요구가 주어졌으면 그 종료 조건을 판정한다: `python nova.py exit-check $ARGUMENTS`
3. 모바일을 바꿨으면 `python nova.py kmp-test`(JAVA_HOME — CLAUDE.md '이 PC 환경')
4. 🔒 **하나라도 빨강이면 task 를 `- [x]` 로 표시하지 않는다.** 다시 돌려 초록을 만들지 않고 원인부터 — `/debug`
5. 통과 숫자(몇 건 통과)를 그대로 기록에 옮긴다 — `/docs-write`

## 하지 않는 것
- 출력 없이 "통과"라고 쓰기 · 실패 테스트를 건너뛰거나 끄기 · 숫자 지어내기
