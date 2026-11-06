---
description: 병렬 수렴 — main 에서 묶음 브랜치를 병합하고 test · lint 를 돌린 뒤, 단일 기록자로서 이력 · git 기록을 남긴다
argument-hint: <묶음 이름>
---

# /converge — 묶음 병합 · 검증 · 기록

인자: `$ARGUMENTS`
규칙: [docs/plans/README.md §6](../../docs/plans/README.md)

## 절차
1. 본 작업 트리(main)에서 `python nova.py inbox` — 그 묶음의 보고(report)와 남은 질문을 먼저 처리한다
2. 그 묶음의 요구 종료 조건을 판정한다(`tester` 에이전트에 맡겨도 된다): worktree 경로에서 `python nova.py exit-check REQ-…`. 녹색이 아니면 병합하지 않고, 남은 ✗ 만 그 worktree 에 요청한다(범위를 넓히지 않는다)
2-1. 병합 직전에 `python nova.py release checkpoint "<묶음> 병합 직전"` 을 권고한다 — 병합이 잘못되면 `release rollback <태그>` 로 돌아갈 지점([판본 규약 §9](../../docs/conventions/versioning.md) · REQ-261106-02)
3. `python nova.py converge <묶음> --verify`(병합 뒤 lint 가 길면 `verifier` 에이전트)
   - **병합 전에 경로 검사**: 묶음 브랜치가 그 묶음 '경로' 밖 파일을 바꿨으면 도구가 병합을 거부하고 파일을 보여 준다(브랜치 루트의 `HANDOFF.md` 만 예외). 밖을 바꿔야 했다면 main 이 먼저 받아 공통부로 넣고, 묶음은 `/worktree-sync`
   - `--no-ff` 로 병합한 뒤 test · lint 를 돌린다
   - 충돌이 나면 도구가 되돌리고 알린다. 충돌 파일이 묶음 경로 밖이면 병렬 묶음 표의 경로를 다시 본다
4. **main 에서 기록한다**(단일 기록자)
   - `/history-new`(한 일 · 검증 숫자) — 묶음이 남긴 `HANDOFF.md` 원문은 history 부록으로 옮긴 뒤 지운다
   - 요구 상태를 완료로 바꾼다(종료 조건 녹색일 때만)
   - task `- [x]`
   - 커밋 · 푸시 · `git_record.py`
5. 버스 메시지를 끝낸다: `python nova.py done <ID> --result "병합 · 기록 완료(커밋 …)"`
6. worktree 는 바로 지우지 않는다(되돌아볼 수 있게). 지우려면 사용자 확인 뒤 `git worktree remove .worktrees/wt-<묶음>` · `git branch -d wt-<묶음>`
6-1. 병합 뒤 도구가 남은 worktree 에 'main 갱신 — /worktree-sync' 를 버스로 알린다. 오래 가는 묶음은 낡은 공통부 위에서 일하지 않게 `/worktree-sync` 한다
7. 모든 묶음이 수렴되면 릴리스를 확인한다: `python nova.py release status` → `/release`
