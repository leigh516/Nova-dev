---
description: 병렬 회차 분배 — 병렬 게이트를 통과하면 마스터플랜 '병렬 묶음' 표와 묶음 담당 REQ 상태로 파도(선행 묶음이 끝나야 시작) 분할안 초안을 내고, 사람이 고친 초안대로 파도 하나씩 /worktree-new 로 연다(본 작업 트리에서)
argument-hint: plan | next (비우면 plan — 화면 분할안만, 쓰기 없음)
---

# /dispatch — 병렬 회차 분배

인자: `$ARGUMENTS`
규칙: [plans README §6](../../docs/plans/README.md) · [ADR-008](../../docs/adr/ADR-008-parallel-bus-release.md) · 편제 [ADR-010](../../docs/adr/ADR-010-agent-folders.md) · 짝 [/converge](converge.md)

`/dispatch` 는 새 판정을 만들지 않고 **게이트 → 분할안 → 사람 확인 → 파도별 개설**을 잇는다. 게이트는 `parallel-gate`, 개설은 `/worktree-new` 가 정본이다.

## 절차
0. **본 작업 트리(main)에서** — 초안 쓰기는 도구가 worktree 에서 거부한다(단일 기록자)
1. **병렬이 이득인가 먼저 묻는다** — 묶음이 하나뿐이거나 일이 작으면 직렬이 빠르다. worktree 는 열 때마다 설치 · 동기화 · 병합 비용이 붙는다
2. **게이트**: `python nova.py parallel-gate` — 닫혀 있으면 이유를 사용자에게 알리고 **직렬로 간다**(여기서 끝). 표를 손으로 '완료'로 바꿔 열지 않는다
3. **묶음 설계가 애매하면**(경로 · 개념 · 표 · 토픽 겹침, 의존 순서) `orchestrator` 에이전트에 묶음안을 받는다 — 설계만 한다. 결과는 마스터플랜 '## 병렬 묶음' 표에 반영한다(마스터플랜 중요 변경은 `drafts/` → 사용자 결정 → `python nova.py masterplan adopt`)
   - 선행이 있으면 표에 `선행 묶음` 칸을 둔다(묶음 이름, 여럿이면 쉼표, 없으면 `-`). 칸이 없으면 모든 묶음이 파도 1이다
4. **분할안**: `uv run python scripts/dispatch.py plan` (화면) → 맞으면 `uv run python scripts/dispatch.py plan --write` → `docs/plans/drafts/dispatch_<날짜>.md`
   - 담당 REQ 가 모두 완료 · 적용됨인 묶음은 '끝난 묶음'으로 빠지고, 그 묶음을 기다리던 묶음도 기다리지 않는다
   - 표의 결함(없는 선행 묶음 · 선행 순환)은 종료 1 — 분할 문제가 아니라 **표를 고친다**
5. **승인 관문**: 사용자가 초안을 열어 '파도' 칸을 고치거나 행을 지운다(이번 회차에서 뺀다). '경로' 칸은 고치지 않는다(겹침은 마스터플랜에서). 사용자가 "이대로"라고 하기 전에는 worktree 를 만들지 않는다
6. 각 묶음의 담당 REQ 에 종료 조건이 있는지 확인한다 — `python nova.py exit-check REQ-… --dry`. 없으면 먼저 채운다(끝이 없는 묶음은 병합 시점이 없다)
7. **지금 열 파도**: `uv run python scripts/dispatch.py next` — 앞 파도가 모두 끝난 가장 이른 파도의 `python nova.py worktree-new <묶음>` 명령을 **안내만** 한다(이미 열린 worktree 는 뺀다). 안내된 묶음마다 `/worktree-new <묶음>` 를 차례로 실행한다
8. 사용자에게 묶음별 경로 · 담당 REQ · 파도를 표로 알리고, 각 폴더에서 새 세션 → `/handoff-start` 를 안내한다. 다음 파도는 앞 파도가 `/converge` 로 병합되고 담당 REQ 가 완료로 바뀐 뒤 다시 `dispatch.py next`
9. 진행 중 관측은 `/orchestrate`, 병합은 `/converge`

## 하지 않는 것
- 게이트 · 개설 로직을 여기서 따로 하기 — `parallel-gate` · `/worktree-new` 가 정본이다
- 초안을 정본으로 쓰기 — 정본은 마스터플랜 '## 병렬 묶음' 표다. 초안은 이번 회차의 순서 메모다
- psg05 의 `assignment.json` · `round_NN` 회차 원장 · task 선할당(`tasks.mjs add` · `fill`) · 보드 · 칸반 — Nova 는 표 하나 + REQ 상태 + 종료 조건으로 충분하다(원장이 늘면 맞춰야 할 곳이 는다)
- 파도 2를 앞당겨 열기 — 앞 묶음의 계약이 굳기 전에 갈라지면 병합이 터진다
