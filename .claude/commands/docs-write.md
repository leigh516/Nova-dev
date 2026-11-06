---
description: 기록 분량 정하기 — 바뀐 파일로 등급(작은 일 · 보통 일 · 큰 일)을 제안받아 기록 하한을 정하고, 요구 · 이력 · tasks 3갈래 대조 · 판본 노트 · check · git 기록까지 끝낸다(본 작업 트리에서)
argument-hint: [커밋 범위] | tasks [tasks_REQ_NN]
---

# /docs-write — 얼마나 기록할지 정하고 기록한다

`/docs-write` 는 **얼마나 기록할지**를 정하고 그 절차(`/history-new` · `/req-new` · `git_record.py`)를 부른다. 작업 단위의 검증 · 병합 선택은 `/finish`, 회차를 닫는 묶음은 `/round-close` 가 이 명령을 부른다.

인자: `$ARGUMENTS` — 비우면 git 기록 기준..HEAD + 작업 트리, 커밋 범위(`A..B`)를 주면 그 범위, `tasks <tasks_REQ_NN>` 이면 4단계만

규칙: [CLAUDE.md](../../CLAUDE.md) '문서 규칙' · 계획 · task: [plans README](../../docs/plans/README.md) · 판본 노트: [releases README](../../docs/releases/README.md) · 단일 기록자: [ADR-008](../../docs/adr/ADR-008-parallel-bus-release.md)

## 절차
0. **본 작업 트리(main)에서** 한다 — worktree 안이면 번호 기록을 쓰지 않고 `/send` 로 main 에 보고한다(단일 기록자)
1. **등급**: `python nova.py docs-write grade $ARGUMENTS` 를 돌려 등급 · 신호 · 기록 하한을 본다. 등급은 제안이다 — 계약을 바꾸는지 · 결정을 남기는지는 사람이 안다. **애매하면 한 등급 위로**, 판정과 근거를 git 기록 요약에 한 줄

   | 등급 | 기록 하한 |
   |---|---|
   | 작은 일 | 커밋 + `git_record.py` |
   | 보통 일 | + `/history-new` |
   | 큰 일(또는 ADR · DB 모델 · 계약 신호) | + 요구(REQ) 갱신 · 되돌리기 어려운 결정이면 ADR(`docs_new.py adr`) |
2. **요구 문서**(큰 일 · 새 요구가 있을 때 — `/req-new` 로 만들거나 기존 문서를 고친다): 요구마다 **수용 기준을 Given-When-Then 으로 먼저** 쓴다 — `**Given** <사전 조건> **When** <행동> **Then** <관측 가능한 결과>`. 못 쓰겠으면 비우지 말고 `미정 — 무엇이 갖춰지면 정해지는가` 를 적는다. 상태 칸(진행 중 · 완료 · 적용됨)과 종료 조건 판정(`python nova.py exit-check REQ-…` 출력) 칸을 채운다
3. **이력**(보통 일 이상): `/history-new <작업 제목>` — 긴 본문은 `doc-writer` 에이전트에게 파일 경로와 main 이 실행한 검증 출력을 주고 맡긴다(번호 · 인덱스는 main)
4. **tasks 3갈래 대조**: `python nova.py docs-write tasks <tasks_REQ_NN>` 로 남은 `- [ ]` 를 보고 한 줄씩 판정한다

   | 남은 칸 | 처방 |
   |---|---|
   | 했음 | 코드 · 테스트(명령 출력)로 확인한 뒤 `- [x]` |
   | 넘김 | 체크하지 않는다 — 🆕 표시 + 판정(`지금 — <깨는 종료 조건>` / `다음 판본`) · 다음 요구 · 이유(plans README §5) |
   | 기각 | 체크하지 않는다 — `~~취소선~~ — 이유`(지우지 않는다) |
5. **판본 노트**: 소비자가 느낄 변화(새 명령 · 화면 · API · 토큰)가 있으면 열린 판본(`python nova.py release status` 의 draft) 노트 `docs/releases/v<버전>.md` 의 '새로운 것 · 바뀐 것'에 한 줄 누적한다. draft 판본이 없으면 쓰지 않고 '다음 판본 후보'로 보고한다. 순수 기록 커밋은 올리지 않는다
6. **검사 · 기록**: `python nova.py check` 통과 출력을 확인 → 커밋 · 푸시 → `uv run python scripts/git_record.py "<요약 · 등급>" <범위>`

## 하지 않는 것
- worktree 에서 번호 붙는 기록(요구 · 이력 · git 기록 · 인덱스)을 쓰기 — 단일 기록자, 병합(`/converge`) 뒤 main 이 쓴다
- tasks 일괄 체크 — 넘김 · 기각까지 `[x]` 가 되면 하지 않은 일을 했다고 기록하게 된다
- 검증 숫자 지어내기 — 이력 · 요구에 적는 수는 이번에 실행한 명령 출력에서만
- 등급을 낮추려고 파일을 나눠 커밋하기 · 신호를 무시하기
