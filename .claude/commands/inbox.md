---
description: 받은함 — 내 앞으로 온 메시지(main 은 버스 전체)를 읽고 처리한 뒤 결과를 남겨 끝낸다
argument-hint: (선택) --as <이름>
---

# /inbox — 받은함 처리

규칙: [docs/plans/README.md §6](../../docs/plans/README.md)

## 절차
1. `python nova.py inbox` — 나(브랜치 이름, 본 작업 트리는 main) 앞으로 온 처리 전 메시지. main 은 버스 전체를 본다
2. 하나씩 `python nova.py show <ID>` 로 전문을 읽고 처리한다
   - question → 답을 `send --reply-to <ID>` 로
   - handoff → 담당 경로 · 요구를 내 작업으로 받는다(`/session-start` 이어서)
   - report → main 은 `/converge` 를 판단
   - 전체 공지(`*` · report — `/converge` 가 보내는 "main 갱신 — /worktree-sync") → worktree 는 `/worktree-sync` 로 따라잡고 끝낸다. 이미 병합된 worktree 는 처리하지 않아도 된다 — `worktree-prune` 이 받은함 미처리로 세지 않는다
   - escalation → main(사용자)에게 한국어로 요지 · 선택지 · 권고를 올린다
3. 끝낼 때는 반드시 결과와 함께: `python nova.py done <ID> --result "<무엇이 됐나>"` — 받는 이와 main 만 끝낼 수 있다
   - 받는 이가 끝내면: 한 명 앞이면 바로 보관(archive), 여러 명 앞이면 모두 끝내야 보관, 전체(`*`) 앞이면 각자 결과만 붙고 버스에 남는다
   - **main 이 끝내면 받는 이 구성과 관계없이 바로 보관한다**(거두기) — 아직 끝내지 않은 받는 이의 받은함에서도 사라지므로, 전체 · 여러 명 메시지는 모두의 결과가 붙은 뒤 거둔다
   - 목록의 ✔ 는 "누군가 결과를 붙였다"는 표시다. 내 받은함에 남았는지는 내가 끝냈는지로 따로 판정한다(여러 명 · 전체 메시지는 남이 끝내도 내 받은함에 남는다)
   - `--as <이름>` 은 다른 이름으로 대신 보고 끝내는 대리 처리용이다(사람이 손으로 정리할 때). 인증이 아니다 — 같은 PC 의 세션끼리 쓰는 버스라 막을 경계가 없고, 결과 절에 `--as` 로 준 이름이 남는다
4. 답을 기다리는 동안 자기 다른 일을 진행한다(서로 기다리다 멈추지 않게). 내가 보낸 것의 결과는 `python nova.py outbox`
