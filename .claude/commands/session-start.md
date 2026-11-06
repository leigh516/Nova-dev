---
description: 세션 시작 — 이전 세션의 LATEST 인수인계와 계획·task·이력을 읽고 이어서 작업한다
---

# /session-start — 인수인계 불러오기

## 절차
1. `docs/session/LATEST.md` 를 읽는다 (없으면 `docs/session/session_index.md` 의 마지막 항목, 그것도 없으면 첫 세션 — 3단계로)
1-1. 인수인계가 없는 첫 세션(new-project · 템플릿 초기화 직후)이면 `project-starter` 에이전트로 저장소 요약부터 받는다
2. 다음을 순서대로 읽고 현재 상태를 파악한다
   - `CLAUDE.md` (저장소 규칙)
   - `docs/plans/master_plan.md` (전체 계획 · 순서)
   - 인수인계 §4 "다음에 할 일"이 가리키는 `docs/plans/plan_REQ_NN.md` 와 `docs/plans/tasks/tasks_REQ_NN.md`
   - `docs/requirement/requirement_index.md`, 최근 `docs/history/` 2개, `docs/git/git_index.md`
   - 교훈 `docs/memo/lessons.md`(최근 항목 · 승급 후보)
3. `git fetch && git status && git log --oneline -10` — 인수인계의 최신 커밋과 실제 저장소가 일치하는지 확인
4. 인수인계 §6 검증 명령으로 현재 상태가 녹색인지 확인 (기본: `python nova.py check` — test · lint 동시)
4-1. 상태 브리핑 재료: `python nova.py progress` · `python nova.py release status` · `python nova.py issue list --open` · `python nova.py inbox`(넓으면 `project-manager` 에이전트 — 원장 종합)
4-2. **열린 자동 진행 알림**: `.superpowers/sdd/<계획>/` 원장이 있거나 `docs/plans/tasks/tasks_REQ_NN.md` 에 `- [ ]` 가 남은 계획마다(계획이 여럿이면 계획마다 한 줄) `uv run python scripts/task_batch.py <tasks 파일> < /dev/null` 의 출력과 종료 코드를 읽는다(종료 코드 뜻 · 상한은 [task-run.md](task-run.md) · 스크립트 docstring 이 정한다 — 여기 다시 적지 않는다). 원장이 없어도 tasks 체크만으로 안내한다. 이어 갈 묶음이 있으면 "이어 가려면 같은 명령: `/task-run <tasks_REQ_NN> subagent --auto`" 한 줄, 막힘 · 형식 이상이면 "막힘 · 형식 이상 — 이어 가기 전에 확인" 으로 안내한다. 알리기만 하고 시작하지 않는다(`--auto` 는 사용자가 부른다)
5. 사용자에게 한국어로 3~5줄 요약: 지난 세션 결과 · 지금 상태(열린 판본 · 열린 결함 수) · 열린 자동 진행(4-2 가 낸 한 줄 — 없으면 생략) · 이번 세션에서 할 일 제안(미완료 task ID)
6. 새 요구가 있으면 `/req-new` 로 기록하고 계획에 반영한 뒤 작업 시작. 고객 요구면 `/req-interview` → `/req-analyze`
6-1. **worktree 안이면**(`git rev-parse --git-dir` 과 `--git-common-dir` 이 다르다): 받은함부터 — `python nova.py inbox`. 인계 카드(handoff)의 담당 경로 · 요구 · 규칙을 읽고, 그 요구의 종료 조건(`python nova.py exit-check REQ-… --dry`)을 확인한다. 번호가 붙는 기록은 쓰지 않는다(단일 기록자 — main 이 `/converge` 뒤 남긴다). main 보다 뒤처졌으면 `/worktree-sync`(한 번에: `/handoff-start`)
7. Superpowers 확인: `python nova.py doctor` 의 superpowers 줄이 ✓ 인지. 작업마다 맞는 스킬을 먼저 찾아 쓴다(`superpowers:using-superpowers`, 지도: `docs/conventions/superpowers.md` §2)
