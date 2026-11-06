---
description: worktree 동기화 — 병렬 묶음 worktree 가 main 의 새 공통부 · 기록을 단방향으로 받는다(merge, rebase 금지). 미리보기(--dry)로 파괴적 변경을 판독한 뒤 병합 · 격리 재검증 · 상속 기준 보고까지. main 이 갱신됐다는 버스 알림을 받았을 때 쓴다(psg05 이름 /sync-common)
argument-hint: (없음 — worktree 안에서 실행)
---

# /worktree-sync — main 받기

규칙: [docs/plans/README.md §6](../../docs/plans/README.md) · [ADR-008](../../docs/adr/ADR-008-parallel-bus-release.md)

오래 가는 묶음이 낡은 공통부 · 계약 위에서 일하면 `/converge` 때 한꺼번에 터진다. main 이 갱신되면 받는다. 병합은 `main` **전체**를 받는다 — 경로를 골라 받으면 상속 기준(어느 main 위에 있는지)을 말할 수 없어진다.

## 절차
1. **worktree 안에서** 실행한다(main 에서는 도구가 거부한다 — main 이 할 일은 받는 것이 아니라 `/converge` 뒤 알림을 보내는 것). 커밋 안 된 변경이 있으면 도구가 거부한다 — 먼저 커밋한다(stash 후 병합 금지 — 되돌릴 때 2차 충돌)
2. **미리보기**: `python nova.py worktree-sync --dry` — 병합하지 않는다
   - 뒤처진 커밋 수와 상속 기준(지금 갈래점 `main@<sha>`)을 잰다. 0 이면 끝(빈 병합 커밋을 만들지 않는다)
   - 들어올 변경을 공통부 · 기록(`docs/`) · 내 묶음 · 다른 묶음 · 그 밖으로 나눠 보여 준다
   - "내 묶음 판정 불가"가 나오면 묶음 표에 내 행이 없다는 뜻이다 — **0개가 아니라 모르는 것**이므로 내 묶음 · 다른 묶음 수를 믿지 않고 main 에 묻는다
   - 20커밋을 넘게 뒤처졌으면 도구가 재분기 권고를 낸다 — 계속할지는 사용자가 정한다
   - 병합 전 이 브랜치가 녹색인지 한 번 확인해 두면(`python nova.py check`) 5단계 빨강의 원인(내 작업 · 들어온 것)을 가를 수 있다
3. **파괴적 변경 판독(관문)**: 공통부 부류만 diff 를 실제로 읽는다(`git diff HEAD...main -- <경로>`)

   | 판정 | 신호 | 다음 |
   |---|---|---|
   | 더하기만 | 새 토큰 · 새 부품 · 새 명령 · 새 절 · 새 함수(기존 서명 그대로) | 4단계 |
   | 파괴적 | 기존 함수 서명 · 토큰 이름 · 경로 · 표 구조 · 계약의 변경 · 삭제 | **멈춘다** — `파일:줄` · 무엇이 바뀌었나 · 이 브랜치의 영향 지점을 사용자에게 보이고 묻는다(`python nova.py send --to main --type question …`) |

   사용자가 그래도 진행하라고 하면 진행하되, 그 사실을 브랜치 루트 `HANDOFF.md` 의 주의에 남긴다(main 이 `/converge` 때 안다)
4. **병합**: `python nova.py worktree-sync` — 도구가 `git merge main --no-edit` 한다. 충돌이 나면 되돌리고 충돌 파일마다 처방을 보여 준다(경로 부류로 정한다 — 판단하지 않는다)

   | 충돌 경로 | 처방 |
   |---|---|
   | 공통부 | **항상 main 채택** — 브랜치 쪽 변경이 필요하면 main 에 question(상행 요청). 브랜치 쪽으로 맞추면 main 정본이 조용히 되돌려져 `/converge` 에 실린다 |
   | 기록(`docs/`) | **main 채택 + 보고** — worktree 는 기록을 쓰지 않으므로 충돌 자체가 단일 기록자 위반 신호다 |
   | 내 묶음 경로 | 브랜치 채택 |
   | 다른 묶음 · 그 밖(판정 불가) | **멈춘다** — 사용자 판정. 추측으로 맞추지 않는다 |

   맞춘 뒤 다시 `python nova.py worktree-sync`
5. **격리 재검증(관문)**: `python nova.py check` — 빨강이면 멈추고 원인부터(`/debug`). 돌리지 않았으면 보고에 "미실행"으로 적는다
6. **상속 기준 보고**: 도구가 main 에 보고(report)를 보낸다 — 상속 기준 `main@<옛>` → `main@<새>` · 부류별 파일 수. 인계 메모(`HANDOFF.md`)를 쓰고 있으면 상속 기준 한 줄을 갱신한다. 받은 알림 메시지는 `python nova.py done <ID> --result "동기화 · check 통과"`

## 하지 않는 것
- rebase · reset --hard · cherry-pick · 강제 푸시 — 버스 · 검토 · 인계에 적힌 커밋 해시가 거짓이 된다
- 경로를 골라 받기(공통부만 checkout) — 상속 기준이 사라진다
- 역방향(브랜치 → main) 병합 · 푸시 — 그것은 `/converge`(main 에서)
- 번호가 붙는 기록 쓰기(단일 기록자 — main 이 `/converge` 때 남긴다)
