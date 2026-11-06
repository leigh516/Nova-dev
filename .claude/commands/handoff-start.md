---
description: worktree 세션 이어받기 — 병렬 묶음 worktree 에서 새 세션을 열 때 받은함(인계 카드 · 지시) · HANDOFF.md · main 대비 뒤처짐을 확인하고 남은 일부터 잇는다. 본 작업 트리는 /session-start
argument-hint: (선택) 이번 세션 목표 한 줄
---

# /handoff-start — worktree 세션 이어받기

인자: `$ARGUMENTS`
규칙: [plans README §6](../../docs/plans/README.md) · [ADR-008](../../docs/adr/ADR-008-parallel-bus-release.md) · 짝 [/handoff-end](handoff-end.md)

`/session-start` 6-1 의 worktree 갈래를 한 명령으로 묶은 것이다. 받은함 · 동기화 · 종료 조건은 각 명령이 정본이다.

## 절차
1. **worktree 안인지 확인** — `uv run python scripts/handoff.py status`. 본 작업 트리면 도구가 거부한다 → `/session-start` 로 간다
2. 출력 네 가지를 읽는다: main 대비 뒤처짐(커밋 수) · 받은함 미처리 수 · `HANDOFF.md` 있음/없음 · 미커밋 수
3. **받은함부터**: `/inbox` — 인계 카드(handoff)의 담당 경로 · 요구 · 규칙, main 의 질문 · 지시를 읽고 처리한다(끝낼 때는 `python nova.py done <ID> --result …`). 내가 보내고 결과를 기다리는 것은 `python nova.py outbox`
4. **인계 메모**: 브랜치 루트 `HANDOFF.md` 가 있으면 읽는다 — '남은 것' 첫 항목이 이번 세션의 첫 일이다. 없으면 첫 세션이다(인계 카드가 그 자리를 대신한다)
5. **뒤처짐**: 1 이상이면 먼저 `/worktree-sync` — 낡은 공통부 · 계약 위에서 일하면 `/converge` 때 한꺼번에 터진다
6. **종료 조건**: 담당 REQ 마다 `python nova.py exit-check REQ-… --dry` — 무엇이 녹색이면 끝인지 확인한다
7. `python nova.py check` 로 지금 녹색인지 본 뒤, 사용자에게 한국어 3~5줄: 지난 세션 결과 · 받은함 처리 · 이번에 할 일(`$ARGUMENTS` 가 있으면 그것을 첫 줄에). 확인 받고 `/task-run` 으로 잇는다
8. 브리핑에 한 줄을 넣는다: "이 세션은 worktree — 담당 경로만 고치고, 번호가 붙는 기록은 쓰지 않는다. 마칠 때 `/handoff-end`"

## 하지 않는 것
- 번호가 붙는 기록(요구 · 계획 · 이력 · git 기록 · 세션 · 교훈) 쓰기 — main 이 `/converge` 뒤 남긴다(단일 기록자)
- 담당 경로 밖 · 공통부 고치기 — `python nova.py send --to main --type question …`
- psg05 의 `DIRECTIVE-*` 파일 · `HANDOFF-<branch>_NN` 순번 — Nova 는 지시를 메시지 버스로, 인계는 번호 없는 `HANDOFF.md` 하나로 한다(브랜치에 번호가 생기면 병합 때 다툰다)
