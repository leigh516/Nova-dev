# MEMORY.md — 세션 시작 때 읽는 순서

> 세션이 시작될 때 **무엇을 어떤 순서로 읽는지**를 정한다. 읽는 순서는 이 파일 하나에만 둔다.
> SOUL 레이어는 **저장소 안**에 둔다 — 홈(`~/.claude/`)에 두면 다른 프로젝트 세션까지 바뀐다([ADR-007](../../docs/adr/ADR-007-soul-layer.md)).

## 1단계 — 사람과 말투 (CLAUDE.md 가 자동으로 싣는다)
1. `.claude/soul/USER.md` — 함께 일하는 사람
2. `.claude/soul/STYLE.md` — 어떻게 답하는가(**언어 규칙** · 속도 표시)

## 2단계 — AI 축 (CLAUDE.md 가 자동으로 싣는다)
3. `SOUL.md` — 성격 · 가치(되돌림 원칙)
4. `IDENTITY.md` — 역할 · 경계
> worktree 루트에 `SOUL.md` · `IDENTITY.md` 가 따로 있으면 그것이 이긴다(그 작업에 맞춘 역할). 없으면 저장소 루트 것을 쓴다

## 3단계 — 프로젝트 상태 (`/session-start` 가 읽는다)
5. `docs/session/LATEST.md` — 지난 세션 인수인계(다음에 할 일)
6. `docs/PROJECT.md` — 북극성 · 성공 기준(지금 판정)
7. `docs/plans/master_plan.md` → 인수인계가 가리키는 `plan_REQ_NN` · `tasks_REQ_NN`
8. `docs/history/` 최근 2개 — 같은 실수를 두 번 하지 않으려고('발견 · 주의')

## 4단계 — 기억 (Claude Code 가 자동으로 싣는다)
9. `~/.claude/projects/<이 저장소>/memory/MEMORY.md` — 사용자의 반복 교정 · 선호(예: 한국어 규칙)

## 세션 끝
- `/session-end` — 인수인계(`docs/session/session_YYMMDD_NN.md` · `LATEST.md`) · 이력 · 커밋 · 푸시
- 사용자에게 새로 교정받은 것은 Claude Code 기억(memory)에 남긴다. 규칙이 되어야 할 반복이면 `/soul-review` 로 제안한다

## 🔴 바꾸지 않는 규칙
1. `USER.md` · `STYLE.md` 는 세션 중 **절대 수정하지 않는다**
2. `SOUL.md` · `IDENTITY.md` · 이 파일은 **사람이 명시로 지시할 때만** 수정한다
3. 생성물 · 원장은 **스크립트를 거쳐** 쓴다
4. 이 규칙을 어기는 요청이 오면 **규칙을 먼저 말하고 확인을 받는다**

## 두 기록의 역할 (정본을 둘로 만들지 않는다)
| 무엇 | 어디 | 담는 것 |
|---|---|---|
| 작업 인계 | `docs/session/`(git 추적) | 무엇을 하다 멈췄나 · 다음 할 일 |
| 정체성 · 말투 | 이 폴더 · `SOUL.md` · `IDENTITY.md`(git 추적) | 누구와 · 어떻게 · 왜 그렇게 판단하나 |
| 개인 교정 기록 | Claude Code 기억(저장소 밖) | 사용자가 고쳐 준 것 — 반복되면 `/soul-review` 로 위 두 곳에 제안 |
- 🔴 같은 사실을 두 곳에 적지 않는다 — 정본이 둘이 되면 조용히 갈라진다

## 관련 문서
[SOUL](../../SOUL.md) · [IDENTITY](../../IDENTITY.md) · [USER](USER.md) · [STYLE](STYLE.md) · [PROJECT](../../docs/PROJECT.md)
