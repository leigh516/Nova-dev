---
description: 메시지 버스로 보내기 — 다른 worktree(브랜치) 세션이나 main 에 질문 · 보고 · 인계 · 올림(escalation)을 보낸다
argument-hint: --to <받는 이(브랜치 · main · *)> --type question|report|handoff|escalation --subject "<요지>"
---

# /send — 메시지 보내기

인자: `$ARGUMENTS`
규칙: [docs/plans/README.md §6](../../docs/plans/README.md) — 버스는 본 작업 트리의 `.collab/` 하나(worktree 에서도 같은 곳, 커밋 안 함)

## 절차
1. 받는 이 이름은 브랜치 이름이다(본 작업 트리는 `main`, 모두에게는 `*`). 묶음 이름은 `python nova.py worktree-list` 로 본다
2. 종류를 고른다
   | 종류 | 언제 |
   |---|---|
   | question | 답이 있어야 진행된다(공통부 변경 요청 등) |
   | report | 끝냈다 · 알린다(무엇을 · 검증 숫자) |
   | handoff | 일을 넘긴다(main 이 묶음 worktree · 격리 작업 폴더를 만들 때 자동) |
   | escalation | 사람(main)이 판단할 일 — 한 주제로 3번 넘게 오갔거나 경계를 넘는 결정. **`--to` 에 무엇을 주든 main 으로 간다** · 3홉 상한에 걸리지 않는다 |

   도구가 스스로 보내는 메시지(손으로 보내지 않는다 — `scripts/parallel.py`):
   | 언제 | 보낸 이 → 받는 이 | 종류 | 요지 |
   |---|---|---|---|
   | `worktree-new <묶음>` 직후 | main → `wt-<묶음>` | handoff | `<묶음> 묶음 작업 시작`(담당 경로 · 요구 · 규칙) |
   | `worktree-new --scratch <이름>` 직후 | main → `scratch-<이름>` | handoff | `<이름> 격리 작업 시작` |
   | `/converge` 병합 뒤(다른 `wt-*` 가 남았을 때) | main → `*` | report | `main 갱신 — /worktree-sync` — `worktree-prune` 이 받은함 미처리로 세지 않는다 |
   | `/worktree-sync` 성공 뒤 | worktree → main | report | `<브랜치> — main 따라잡음(<N>커밋)` |
3. 본문은 한국어로 짧게, 다음을 적는다
   - 요지 한 줄(`--subject`)
   - 내용: 무엇이 · 왜 · 근거 `파일:줄`
   - 무엇을 해 주면 되나
4. `python nova.py send --to <이> --type <종류> --subject "<요지>" --body "<내용>"`. 긴 글은 `--body-file <파일>`, 회신은 `--reply-to <ID>`(같은 주제로 묶인다)
5. 보낸 메시지는 고치지 않는다. 바꿀 것이 있으면 새 메시지로 회신한다
