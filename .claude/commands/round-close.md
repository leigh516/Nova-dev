---
description: 회차 마감 — 사실을 한 번 모으고(docs-write facts · progress · release · issue · exit-check) 기록(/docs-write) → 교훈(/learn) → check · 커밋 · git 기록 · 푸시 → 인수인계(/session-end)를 한 흐름으로 잇는다(본 작업 트리에서)
argument-hint: [REQ-YYMMDD-NN] (이 회차의 주 요구 · 선택)
---

# /round-close — 회차 마감

`/round-close` 는 **회차(세션 안의 큰 묶음)를 닫는 것**이고, `/finish` 는 **브랜치 · 작업 단위를 끝내는 것**(검증 · 병합/PR/유지 선택)이다. 회차 안에 작업 단위가 끝났으면 `/finish` 를 먼저 하고 이 명령으로 닫는다.

인자: `$ARGUMENTS` — 이 회차의 주 요구(비우면 사실 수집에서 바뀐 요구를 본다)

규칙: [CLAUDE.md](../../CLAUDE.md) '문서 규칙' · '끝이 있는 일' · 단일 기록자: [ADR-008](../../docs/adr/ADR-008-parallel-bus-release.md)

## 절차
0. **본 작업 트리(main)에서** 한다 — worktree 안이면 `/session-end` 1-2(브랜치 `HANDOFF.md` + `/send`)로 간다
1. **사실을 한 번 모은다** — 아래 출력을 그대로 쓴다. 이 뒤로 같은 조회를 다시 돌리지 않고, **숫자를 지어내지 않는다**. 원장이 많으면 `project-manager` 에이전트에 한 장 요약을 맡겨도 된다(한국어로 4절 보고)
   - `python nova.py docs-write facts` — 기록 기준 이후 커밋 · 등급 · 미판정 task 수
   - `python nova.py progress` — 계획 · task / 요구 상태 ↔ task 모순 / 릴리스 초안
   - `python nova.py release status` · `python nova.py issue list --open`
   - 주 요구가 있으면 `python nova.py exit-check $ARGUMENTS`
2. **기록** — `/docs-write`(등급 → 기록 하한 · 요구 Given-When-Then · 이력 · tasks 3갈래 · 판본 노트). **멈추는 자리**: "왜 그렇게 판단했나 · 무엇이 반증됐나" 문장은 위임하지 않고 main 이 쓴다
3. **교훈** — 이번 회차의 교정 · 실패 · 함정이 있으면 `/learn`(없으면 건너뛴다 — 억지로 만들지 않는다). 같은 함정이 **두 번째**면 교훈 한 줄보다 **게이트로 막을 수 있는지 먼저 따진다**(예: docs → `.claude` 링크를 `docs_index.py --check` 가 기계로 막게 한 것). 게이트 신설은 명령 · 게이트 의미 변경이라 요구(REQ)로 남긴다
4. **검사 · 저장** — (본 작업 트리만) `python nova.py usage --record` 로 이번 회차 호출 집계를 원장 `docs/memo/agent_usage.jsonl` 에 한 줄 남긴다(에이전트 재검토 조건의 원천 — REQ-261105-08). 그다음 `python nova.py check` 통과 출력 확인 → 경로를 밝혀 add(`git add -A` 금지) → 커밋 · 푸시 → `uv run python scripts/git_record.py "<요약>" <범위>` → 기록 커밋 · 푸시. 태그 원격 푸시는 **사용자 확인 뒤**(`/release`)
5. **인계** — 컨텍스트를 많이 썼으면 `/session-end`. **멈추는 자리**: "다음 회차가 무엇부터 하나"는 사용자가 정한다 — 후보만 낸다

## 하지 않는 것
- worktree 에서 번호 붙는 기록 · 인덱스 · git 기록 쓰기 — 단일 기록자, main 이 `/converge` 뒤에 쓴다
- 1단계 밖의 숫자(테스트 수 · 남은 task · 종료 조건)를 기억으로 적기 — 출력이 없으면 "확인 안 함"
- tasks 일괄 체크 · 교훈 지어내기 · 이번 회차를 넓히기(새로 보인 것은 새 요구 · 다음 판본으로)
- 병합 · PR 선택 — 그것은 `/finish` 의 일이다
