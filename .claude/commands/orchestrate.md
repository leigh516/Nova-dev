---
description: 병렬 관제 — 본 작업 트리에서 열린 worktree 를 읽기 전용으로 관측(뒤처짐 · 묶음 경로 밖 변경 · 미커밋 · HANDOFF.md · 받은함)하고 문제 지점을 짚은 뒤, 사용자 확인을 거쳐 지시를 메시지 버스로 보낸다. 고치기 · 대신 커밋 · 병합은 하지 않는다
argument-hint: (선택) <브랜치 wt-…> — 비우면 전부
---

# /orchestrate — 병렬 관제(관측 → 짚기 → 지시)

인자: `$ARGUMENTS`
규칙: [plans README §6](../../docs/plans/README.md) · [ADR-008](../../docs/adr/ADR-008-parallel-bus-release.md) · 오케스트레이션은 main 하나 [ADR-009](../../docs/adr/ADR-009-commands-skills-agents.md) · [ADR-010](../../docs/adr/ADR-010-agent-folders.md)

`/orchestrate` 는 **진행 중** 관측 · 지시이고, `orchestrator` 에이전트는 **착수 전** 묶음 설계만 한다 — 둘을 섞지 않는다. 관제는 비행기를 조종하지 않는다.

## 절차
0. **본 작업 트리(main)에서** — worktree 안이면 도구가 거부한다. worktree 세션은 받은 지시를 `/handoff-start` · `/inbox` 로 처리한다
1. **관측(읽기 전용)**: `uv run python scripts/handoff.py observe`(기계용은 `--json`). worktree 마다 앞섬 · 뒤처짐(main 대비 커밋 수) · 미커밋 수 · `HANDOFF.md` 유무 · 받은함 미처리 수 · 묶음 경로 밖 변경(커밋분 + 미커밋분)이 나온다. "관측 대상 없음"이면 평시 직렬이다 — 여기서 끝
2. **버스 판독**: `python nova.py inbox`(main 은 버스 전체) · `python nova.py outbox` — 오래 처리 안 된 것 · 홉 3에 닿은 스레드(다음 회신은 escalation 이어야 한다)
3. **문제를 짚는다** — 심각을 위로, 위치는 `파일:줄`(허용 경로는 관측이 낸 `docs/plans/master_plan.md:<줄>`, 오염은 그 파일 경로)

   | 등급 | 무엇 | 다룸 |
   |---|---|---|
   | 심각 | 묶음 경로 밖 변경 · 표에 없는 묶음 | 되돌리라는 지시(공통부 변경이 필요하면 main 에 question 으로 올리게) — `/converge` 는 이 상태에서 병합을 거부한다 |
   | 주의 | main 보다 뒤처짐 | `/worktree-sync` 안내 |
   | 주의 | 받은함 미처리 · 오래된 질문 | 확인 요청만 — 처리 중일 수 있다 |
   | 확인 | 커밋 · 메시지 없이 오래 멈춤 | 확인 요청만 — 대기 · 휴가일 수 있다 |
   - 문제가 0이면 그렇게 보고하고 끝낸다. 문제를 만들어 내지 않는다
4. **지시 초안 → 승인 관문**: 브랜치마다 지시 초안(요지 한 줄 · 무엇을 · 왜 · 근거 `파일:줄` · 끝낼 때 `done --result` 로 알릴 것)을 사용자에게 보여 준다. **사용자가 승인하기 전에는 보내지 않는다**(문구 수정 · 일부만 승인 가능)
5. **보내기(승인분만)**: `python nova.py send --to <브랜치> --type question --subject "<요지>" --body "<내용>"`(답이 필요한 지시) 또는 `--type report`(알림). 전부에게면 `--to "*"`. 이어지는 회신은 `--reply-to <ID>`, 한 주제로 3번 넘게 오가면 도구가 막는다 → 사용자 판단(escalation)
6. 보고(화면만 — 번호 기록을 만들지 않는다): 관측 worktree 수 · 등급별 문제 수 · 보낸 메시지 ID. 심각이 남았으면 `/converge` 를 보류할지 사용자에게 묻는다

## 하지 않는 것
- worktree 안 파일 고치기 · 대신 커밋 · 푸시 · reset · 강제 동기화 — 필요하면 지시로 요청한다
- 강제 병합 — 병합은 `/converge` 하나다
- psg05 의 미커밋 `DIRECTIVE-*` 파일 투하 · `orchestration.json` 관측 원장 · 칸반 — Nova 는 버스로 지시하고 관측은 화면 보고로 끝낸다
- 승인 없이 보내기 · `/session-start` 등에 자동으로 끼워 넣기
