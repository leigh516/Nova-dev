---
description: 구현(psg05 이름 /build) — 승인된 계획의 task 를 하나씩 TDD 로 구현한다. Nova 의 /task-run 과 같은 일이다
argument-hint: <tasks_REQ_NN> [subagent|native] [T<NN>-<단계>.<순번>부터]
---

# /build — task 구현 (Nova 이름 `/task-run`)

인자: `$ARGUMENTS`

psg05 의 `/build` 이름으로 부르는 입구다. **절차는 [/task-run](task-run.md) 을 그대로 따른다** — 실패 테스트 먼저 · 경로 → 구현자 표 · 멈춤 조건 · 명령 출력으로 확인한 뒤에만 `- [x]`.

- 구현 뒤 확인은 `/verify`(정적 · 계약) · `/test`(행동)
