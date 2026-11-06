---
description: worktree 세션 마감 — 받은함 미처리가 없고 HANDOFF.md 를 쓴 뒤에만 커밋 · 푸시하고 main 에 보고를 보낸다(close-check 가 막으면 마감하지 않는다). 본 작업 트리는 /session-end
argument-hint: (선택) 한 줄 마감 메모
---

# /handoff-end — worktree 세션 마감

인자: `$ARGUMENTS`
규칙: [plans README §6](../../docs/plans/README.md) · [ADR-008](../../docs/adr/ADR-008-parallel-bus-release.md) · 짝 [/handoff-start](handoff-start.md)

`/session-end` 1-2 의 worktree 갈래다. 다음 세션(같은 worktree)과 main 의 `/converge` 가 이어받을 수 있게 남긴다.

## 절차
1. **worktree 안인지 확인** — `uv run python scripts/handoff.py status`(본 작업 트리면 거부 → `/session-end`)
2. 이번 세션에서 겪은 함정 · 교정이 있으면 `HANDOFF.md` '교훈 후보'에 적는다(교훈 원장 `/learn` 은 main 이 병합 뒤 쓴다)
3. **받은함 정리**: `/inbox` — 처리한 것은 `python nova.py done <ID> --result …`. 이번에 못 하는 지시는 결과에 "받음 · 다음 세션으로"를 붙여 끝내고 `HANDOFF.md` '남은 것'에 메시지 ID 와 요지를 옮긴다. 버스(`.collab/`)는 커밋되지 않으므로 옮겨 적지 않으면 다음 세션에 전달되지 않는다
4. **`HANDOFF.md`**(브랜치 루트 · 번호 없음 — 덮어 쓴다) 를 쓴다. 절:
   - `## 한 일` — REQ · task 단위, 검증 숫자(`python nova.py check` 의 통과 · 실패 수)
   - `## 남은 것` — 다음 세션이 첫 번째로 할 일부터(받은함에서 옮긴 메시지 ID 포함)
   - `## 주의` — 함정 · 결정 대기 · 계약 관련
   - `## 보낸 것` — 결과를 기다리는 내 메시지(`python nova.py outbox`)
   - `## 교훈 후보` · `## 공통부 변경 요청` — 없으면 "없음"
5. **마감 관문**: `uv run python scripts/handoff.py close-check` — 종료 1 이면 **마감하지 않는다**(출력의 이유를 고친 뒤 다시). 받은함 미처리가 남은 채 마감하면 다음 세션이 받을 상태가 거짓이 된다
6. `python nova.py check` — 빨강이면 `HANDOFF.md` '주의'에 실패 축을 적는다(숨기지 않는다)
7. **커밋 · 푸시**: 바꾼 파일과 `HANDOFF.md` 를 경로를 지정해 담고 한국어 커밋(협업 꼬리말) → `git push`(실패하면 사유를 `HANDOFF.md` '주의'에). `git_record.py` 는 돌리지 않는다(번호 기록 — main 몫)
8. **보고**: `python nova.py send --to main --type report --subject "<묶음> 세션 마감" --body "<한 일 · 검증 숫자 · 남은 것>"`. 종료 조건이 모두 녹색이면 본문에 "`/converge` 요청"을 넣는다
9. 사용자에게 커밋 해시 · 보고 메시지 ID · 릴레이(다음 세션이 잇는다)인지 최종(병합 대기)인지를 알린다

## 하지 않는 것
- 번호가 붙는 기록 · 인덱스 쓰기(요구 · 이력 · git 기록 · 세션 · 교훈) — main 이 `/converge` 때 `HANDOFF.md` 를 이력 부록으로 옮긴다
- close-check 를 건너뛴 마감 · `.collab/` 커밋
- psg05 의 frontmatter 계약 · `HANDOFF-<branch>_NN` 순번 · DIRECTIVE 수령 절 — Nova 는 번호 없는 `HANDOFF.md` 와 버스의 `done --result` 가 그 일을 한다
