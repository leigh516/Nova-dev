---
description: 교훈 기록 — 교정 · 테스트 실패 · 검증 위반 · 사후기록의 재발방지를 "트리거 → 규칙" 한 줄로 docs/memo/lessons.md 에 남긴다(근거 식별자 필수 · 승급은 /soul-review)
argument-hint: [교훈 한 줄](선택)
---

# /learn — 교훈 기록

인자: `$ARGUMENTS`
원장: [docs/memo/lessons.md](../../docs/memo/lessons.md)

## 언제
사용자가 교정했을 때 · 테스트가 실패했을 때 · 검증 규칙을 어겼을 때 · [/postmortem](postmortem.md) 의 재발방지 — **생긴 즉시**.

## 절차
0. **본 작업 트리(main)에서** — worktree 에서는 스크립트가 거부한다(단일 기록자). worktree 의 교훈은 `python nova.py send --to main …` 으로 보내고, main 이 병합 뒤 남긴다
1. 증상이 아니라 **원인이 된 상황(트리거)** 을 찾는다
2. 출력이 아니라 **다음에 바꿀 행동(규칙)** 을 한 문장으로
3. 먼저 같은 것이 있는지 찾는다: `python nova.py learn find <낱말>`
4. 남긴다
   ```bash
   python nova.py learn add "<트리거>" "<규칙>" --ref <근거 ID>
   ```
   - 근거는 강한 식별자 하나 이상: `REQ-YYMMDD-NN` · `ISS-YYMMDD-NN` · `history_YYMMDD_NN` · `review_YYMMDD_NN` · `ADR-NNN`. 날짜 · 산문만은 거부된다
   - 같은 트리거가 이미 있으면 `(승급 후보)` 가 자동으로 붙는다
5. `python nova.py learn check` 로 형식을 확인하고, 추가한 한 줄을 보고한 뒤 하던 일로 돌아간다

## 하지 않는 것
- SOUL · STYLE · CLAUDE.md · 명령 · 게이트를 이 명령에서 고치지 않는다 — 승급 후보는 [/soul-review](soul-review.md) 가 제안하고 사람이 승인한다
- 기계(검사 · 훅)로 막을 수 있는 것을 교훈으로만 끝내지 않는다 — 그런 것은 새 요구(`/req-new`)로 남긴다
