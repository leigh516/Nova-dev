---
description: 세션 종료 — 다음 세션이 이어받을 수 있게 인수인계를 쓰고 기록·커밋·푸시한다
---

# /session-end — 세션 인수인계 작성

컨텍스트가 많이 소모되었거나 작업을 끊어야 할 때 실행한다. 다음 세션이 `/session-start` 한 번으로 이어받을 수 있어야 한다.

## 절차
1. 현재 상태 수집(볼 원장이 많으면 `project-manager` 에이전트로 한 장 요약을 받는다)
   - `git status`, `git log --oneline -15`, 현재 브랜치 · 열린 PR
   - 미완료 task: `grep -rn -- "- \[ \]" docs/plans/tasks/` (진행 중 계획의 것)
   - `docs/plans/master_plan.md` 품질 게이트 · `plan_REQ_*.md` §12 체크리스트
   - 최근 `docs/history/`, `docs/git/` 파일
1-1. 이번 세션에서 겪은 함정 · 교정이 있으면 먼저 `/learn`(교훈 한 줄)
1-2. **worktree 안이면**(한 번에: `/handoff-end` — `handoff close-check` 가 막으면 마감하지 않는다) 번호 기록 대신 브랜치 루트 `HANDOFF.md` 를 쓰고 커밋한 뒤 `python nova.py send --to main --type report …` — 아래 2~6 은 main 이 `/converge` 때 한다
2. 이번 세션 작업 이력이 아직 없으면 `uv run python scripts/docs_new.py history "<제목>" --plan plan_REQ_NN` 으로 만들고 채운다
3. 끝낸 task 를 `- [x]` 로 체크(코드 · 테스트로 확인한 것만), 작업 중 생긴 일은 `🆕` 로 추가(같은 줄에 판정(`지금 — <깨는 종료 조건>` / `다음 판본`)을 적는다(plans README §5)), plan 진척 줄 갱신
3-1. 열린 릴리스 판본(`python nova.py release status`)과의 관계를 인수인계에 한 줄: 이 세션이 어떤 종료 조건을 채웠나 · 남은 것
4. `uv run python scripts/docs_new.py session "<한 줄 요약>"` → `session_YYMMDD_NN.md` + `LATEST.md` + 인덱스. 템플릿 §1~§7 을 모두 채우고 LATEST.md 에도 같은 내용(긴 본문은 `doc-writer` 에이전트 — 파일 경로를 주고)
5. `uv run python scripts/docs_index.py --check` 통과 확인
6. 커밋 · 푸시 → `uv run python scripts/git_record.py "<요약>" <범위>` → 기록 커밋 · 푸시
7. 사용자에게 인수인계 파일 경로와 "다음 세션에서 `/session-start` 실행" 안내
