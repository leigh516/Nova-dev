---
description: 병렬 개발 시작 — 병렬 게이트(공통 영역 완료 · 묶음 2개 이상 · 경로 겹침 없음)를 통과하면 묶음마다 worktree 를 만들고 버스로 인계 카드를 보낸다
argument-hint: <묶음 이름>
---

# /worktree-new — 묶음별 worktree 만들기

인자: `$ARGUMENTS` (마스터플랜 '## 병렬 묶음' 표의 묶음 이름)
규칙: [docs/plans/README.md §6](../../docs/plans/README.md) · [ADR-008](../../docs/adr/ADR-008-parallel-bus-release.md)

## 절차
1. **본 작업 트리(main)에서** 실행한다. worktree 안에서는 도구가 거부한다
1-1. 묶음 경로 · 개념 겹침이 애매하면 `orchestrator` 에이전트로 묶음안을 먼저 받는다(설계만 — 생성은 이 명령)
2. `python nova.py parallel-gate`
   - 닫혀 있으면 이유를 사용자에게 한국어로 알리고 **직렬로 간다**
   - 공통 영역을 끝내는 것이 먼저다. 표를 손으로 '완료'로 바꿔 게이트를 여는 일은 하지 않는다 — 완료에는 증거가 있어야 한다
3. 묶음에 묶인 요구(REQ)에 종료 조건(exit)이 있는지 확인한다(`python nova.py exit-check REQ-… --dry`). 없으면 먼저 채운다
4. 커밋 안 된 변경이 있으면 먼저 커밋한다(worktree 는 마지막 커밋에서 갈라진다)
5. `python nova.py worktree-new <묶음>`
   - `.worktrees/wt-<묶음>` 이 생기고, 브랜치는 `wt-<묶음>` 이다
   - 인계 카드(담당 경로 · 요구 · 규칙)가 버스로 간다
   - 그 worktree 에서 `uv sync` 를 시도한다(웹이 있으면 `npm install` 안내). 설치를 빼면 열자마자 빨갛다
   - 원격이 있으면 `git push -u origin wt-<묶음>` 을 시도한다(실패해도 계속 — 경고만)
6. 사용자에게 알린다: "새 터미널에서 `cd .worktrees/wt-<묶음>` → `claude` → `/session-start`(받은함부터 확인)"
7. worktree 세션이 지키는 것
   - 자기 경로만 고친다. 공통부를 바꿔야 하면 `python nova.py send --to main --type question …`
   - 번호가 붙는 기록은 쓰지 않는다(단일 기록자)
   - main 이 갱신됐다는 버스 알림을 받으면 `/worktree-sync`
   - 마감은 `/handoff-end` — 브랜치 루트에 `HANDOFF.md`(번호 없음 — 한 일 · 검증 숫자 · 남은 것)를 커밋한다. 버스(`.collab/`)는 커밋되지 않으므로 저장소 이력에는 이것이 남는다
   - 종료 조건이 녹색이면 끝: `python nova.py check` → 커밋 → `send --to main --type report`(무엇을 · 검증 숫자) → `/converge` 를 main 에 요청
