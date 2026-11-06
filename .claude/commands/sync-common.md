---
description: 공통부 받기(psg05 이름 — Nova 는 /worktree-sync) — worktree 가 main 의 갱신을 단방향 merge 로 받는다. 절차는 /worktree-sync 를 따른다
argument-hint: (없음 — worktree 안에서 실행)
---

# /sync-common — /worktree-sync 의 다른 이름

`/sync-common`(psg05) 과 `/worktree-sync`(Nova) 는 **같은 일**이다 — worktree 가 main 을 merge 로 받는다(rebase 금지).

## 절차
1. [`/worktree-sync`](worktree-sync.md) 의 절차를 그대로 따른다 — 도구는 `python nova.py worktree-sync`(먼저 `--dry`)

## 하지 않는 것
- 여기에 절차를 따로 적기 — 정본은 `/worktree-sync` 하나다(두 곳에 적으면 갈라진다)
