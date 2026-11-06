# Superpowers 활용 규약 — 고객 인터뷰부터 마무리까지

[Superpowers](https://github.com/obra/superpowers)는 Claude Code 플러그인(스킬 15종)으로, **일하는 방법**을 담고 있다. 고객 인터뷰, 설계 검토, 계획 작성, TDD, 서브에이전트 실행, 코드 검토, 디버깅, 완료 전 검증이 들어 있다. Nova는 **무엇을 어디에 기록할지**를 정한다(요구 → 3층 계획 → task · 이력 · git · 세션). 둘을 겹쳐 쓴다: **방법은 Superpowers, 기록은 Nova**. 결정: [ADR-005](../adr/ADR-005-superpowers-workflow.md) · 요구: [REQ-261104-01](../requirement/requirement_261104_01.md)

## 0. 설치 · 확인
| 범위 | 방법 |
|---|---|
| 이 저장소(팀 공통) | `.claude/settings.json` 의 `enabledPlugins` 에 `superpowers@claude-plugins-official` 를 켜 두었다. 저장소를 연 사람에게 Claude Code가 설치를 안내한다. `new-project` 로 만든 프로젝트도 이 설정을 물려받는다 |
| 내 PC(직접 설치) | Claude Code에서 `/plugin install superpowers@claude-plugins-official` |
| 확인 | `python nova.py doctor` 에 `superpowers` 줄. 세션을 시작하면 "You have superpowers" 안내가 붙고 스킬 목록에 `superpowers:*` 가 보인다 |
| 작업 폴더 | `.superpowers/`(시각 도우미 화면 · 실행 원장)와 `.worktrees/` 는 커밋하지 않는다(`.gitignore`) |

## 1. 우선순위 — 겹칠 때는 Nova 규칙이 이긴다
Superpowers 스킬은 "사용자 지시(CLAUDE.md)가 스킬보다 우선"이라고 스스로 정해 두었다. Nova가 다르게 정한 것은 아래와 같다.

| Superpowers 기본값 | Nova 에서는 |
|---|---|
| 설계 문서 `docs/superpowers/specs/YYYY-MM-DD-<주제>-design.md` | 제품 전체는 `docs/product/prd.json` · `spec.json`(입고 → `/intake` · `/prd` · `/foundation` · `/spec`), 요청 하나는 인터뷰 기록 `docs/requirement/interviews/interview_YYMMDD_NN.md` + 요구 `docs/requirement/requirement_YYMMDD_NN.md` (목적 · 목표/비목표/반목표 · 수용 기준) + 설계는 `plan_REQ_NN.md` §0~§12 |
| 구현 계획 `docs/superpowers/plans/YYYY-MM-DD-<기능>.md` | `docs/plans/plan_REQ_NN.md`(설계 · 전역 제약 · 검토 초점) + `docs/plans/tasks/tasks_REQ_NN.md`(task ID `T<NN>-<단계>.<순번>`, 단계별 하위 체크) |
| 영어 안내("I'm using the … skill") · 영어 문서 | **대화 · 기록 모두 한국어**([CLAUDE.md](../../CLAUDE.md) 규칙 0). 안내는 "superpowers:brainstorming 으로 요구를 정리합니다"처럼 쓴다 |
| 커밋 메시지 `feat: add …` | [git.md](git.md) — `feat(범위): 한국어 요약` + 푸시 묶음마다 `scripts/git_record.py` |
| 실행 원장 `.superpowers/sdd/<계획>/progress.md` | 실행 중 메모로만 쓴다(커밋 안 함). 정식 진척은 tasks 의 `- [x]` · history · git 기록 |
| 시각 도우미 화면 `.superpowers/brainstorm/` | 탐색용(커밋 안 함). 확정한 화면은 `docs/plans/mockups/REQ_NN/*.html` 로 옮겨 `python nova.py mockups` → 계획 §4 |
| 코드 검토 결과는 대화로 | 검토 결과는 `docs/reviews/review_YYMMDD_NN.md`(심각도 · 처리) |
| 작업 완료 = 테스트 통과 | task 는 그 테스트 · `python nova.py quick`, 단계 관문 · 마무리는 `python nova.py test` + `lint`(화면이면 `ui-smoke`) 출력 확인 → task `- [x]` (실환경이면 `docs/verification/`) |

## 2. 단계별 스킬 지도 — 15종 전부
```
고객 ─▶ ① 인터뷰 ─▶ ② 요구 분석 ─▶ ③ 계획 ─▶ ④ 실행 ─▶ ⑤ 검토 ─▶ ⑥ 마무리
        /req-interview  /req-analyze   /plan-new   /task-run   /review-request /finish
        brainstorming   brainstorming  writing-    subagent-driven-  requesting-/  verification-before-
        (visual         (builder check) plans      development ·     receiving-    completion ·
         companion)                                executing-plans · code-review   finishing-a-
                                                   test-driven-dev                 development-branch
   상시: using-superpowers(스킬 찾기) · systematic-debugging(/debug) · dispatching-parallel-agents ·
         using-git-worktrees · writing-skills(Nova 명령 만들기) · diagnosing-superpowers(과정 진단)
```

| 단계 | Superpowers 스킬 | Nova 명령 | 산출물 (Nova 위치) |
|---|---|---|---|
| 상시 | `using-superpowers` — 작업마다 맞는 스킬을 먼저 찾아 쓴다 | (세션 시작 시 자동) | - |
| 묶음 | 아래 단계의 스킬을 차례로(§4 크기 판정 · 승인 관문 그대로) | `/sdd [full\|light\|fast] <이름>` | 각 단계의 산출물(이어서 시작 — 있는 산출물로 단계 판정) |
| ⓪ 체크리스트 | `brainstorming`(고객 말로 · 하나씩 · 추측 표시) | `/checklist` · `python nova.py checklist` | `inbound/checklist/checklist.html`(자료에서 채움) → 고객 답 `checklist_YYYYMMDD_NN.json` + `.md` |
| ⓪ 입고 분석 | `dispatching-parallel-agents`(파일마다 분석) | `/intake` | `docs/product/intake.json`(발견 E-* · 부족 G-*) → `docs/warehouse/outbound/<분류>/` |
| ① 고객 인터뷰 | `brainstorming` — 한 번에 질문 하나, 실제 장면을 묻기, 되읽기(play back), 추측 표시, 시각 도우미 | `/req-interview <주제>` | `docs/requirement/interviews/interview_YYMMDD_NN.md` |
| ② 요구 분석 | `brainstorming` 의 크기 판정 · 서면 설계 · **빌더 점검**(새 서브에이전트가 읽고 질문) · 승인 관문(HARD-GATE) | `/req-analyze <인터뷰 또는 REQ>` · `/req-new` | `requirement_YYMMDD_NN.md`(분해 · 수용 기준 · 비목표/반목표 · 미결 질문) |
| ②′ PRD · 기반 · SPEC | `brainstorming`(빌더 점검 · 승인 관문) · 시각 도우미 | `/prd` → `/foundation`(4단계 질의) → `/spec` | `docs/product/prd.json` · `spec.json` + ADR → 출고 md · html · json · DDL ([product README](../product/README.md)) |
| ③ 계획 | `writing-plans` — 파일 구조, 인터페이스, 전역 제약, 검토 초점, 자체 점검 5가지, 실행 방식 선택 | `/plan-new <제목> <REQ>` | `plan_REQ_NN.md` + `tasks/tasks_REQ_NN.md` |
| ③ 격리 | `using-git-worktrees` — 큰 작업은 별도 작업 폴더에서 | (`/task-run` 안에서) | 브랜치 `feat/<계획>-<요약>`([git.md](git.md)) |
| ④ 실행 | `subagent-driven-development`(task 마다 새 구현자 + 새 검토자) 또는 `executing-plans`(이 세션에서 직접) | `/task-run <tasks_REQ_NN>` | 코드 · 테스트 · task `- [x]` · 커밋마다 git 기록 |
| ④ 테스트 | `test-driven-development` — 실패 테스트 → 실패 확인 → 최소 구현 → 통과 확인 → 커밋 | (`/task-run` 안에서) | `tests/` · 서비스 `tests/` · `web` 스모크 |
| ④ 병렬 | `dispatching-parallel-agents` — 서로 무관한 조사 · 수정 2건 이상 | (필요할 때) | - |
| 문제 | `systematic-debugging` — 원인을 찾기 전에는 고치지 않는다(재현 → 가설 → 확인) | `/debug <증상>` | 원인 · 고침은 history "발견 · 주의", 반복될 결함은 회귀 테스트 |
| ⑤ 검토 요청 | `requesting-code-review` — 새 검토자에게 요구 · 계획 · 커밋 범위를 준다 | `/review-request <범위>` | `docs/reviews/review_YYMMDD_NN.md` |
| ⑤ 심층 감사 | `dispatching-parallel-agents`(읽기 전용 축 15개 동시) · `verification-before-completion`(확정은 직접 확인) · `test-driven-development`(고칠 때 회귀 테스트 먼저) | `/deep-audit [범위]` | `docs/reviews/review_YYMMDD_NN.md`(분모 · 축별 결과 · 처분 5갈래) |
| ⑤ 검토 받기 | `receiving-code-review` — 맞장구 금지, 지적마다 확인하고 근거로 수용/반박 | (`/review-request` 안에서) | 검토 문서의 "처리" 칸 |
| ⑥ 검증 | `verification-before-completion` — 증거(명령 출력) 없이 "됐다"고 말하지 않는다 | (모든 완료 주장 전) | task `- [x]` · `docs/verification/` |
| ⑥ 마무리 | `finishing-a-development-branch` — 테스트 → 병합/PR/유지 선택 → 정리 | `/finish` · `/docs-write`(기록 분량) · `/round-close`(회차 마감) | history · git 기록 · (PR) · 세션 인수인계 |
| 개선 | `writing-skills` — Nova 명령 · 스킬 · 에이전트를 새로 만들거나 고칠 때(압박 시나리오로 시험) | 스킬 nova-subagent-creator · nova-skill-creator · nova-command-creator(+ 에이전트 `agent-creator` 판정) | `.claude/commands/*.md` · `.claude/skills/*/SKILL.md` · `.claude/agents/*.md`(설명 · 본문 한국어, `scripts/claude_check.py` 통과) |
| 진단 | `diagnosing-superpowers` — "왜 같은 일을 반복했나", "왜 계획을 안 따랐나", "왜 비쌌나" | (요청 시) | 보고서는 `~/.superpowers/…`, 요지는 `docs/reviews/` 에 한 건 |

## 2.1 Nova 스킬 · 에이전트 · 운영 명령 ([ADR-009](../adr/ADR-009-commands-skills-agents.md) · ADR-010 폴더형 편제)
Superpowers 가 **방법**이면, 아래는 Nova 가 그 방법을 실제로 돌리는 **이름**이다. 명령 · 스킬이 정한 자리에서 부른다. 에이전트는 성격별 폴더(`.claude/agents/<폴더>/`)에 있고, 빠른 찾기는 에이전트 README(`.claude/agents/README.md`) '상황 → 에이전트'.

| 단계 | Nova 스킬 | Nova 에이전트 | Nova 명령 · 도구 |
|---|---|---|---|
| ⓪ 입고 · 첫 세션 | - | `inbound-analyst` · `mockup-analyst`(파일마다) · `project-starter` | `/intake` · `/checklist` · `/session-start` |
| ② 분석 · 빌더 점검 | - | `req-analyst` | `/req-analyze` · `/prd` · `/spec` |
| ②′ 기반 · SPEC | - | `architect` · `api-designer` · `database-architect` · `screen-architect` · `registry-keeper`(이름) | `/foundation` · `/spec` |
| ③ 계획 · 마스터플랜 | `nova-masterplan` · `nova-screen`(§4 목업) | `practice-advisor` · `task-planner` · `masterplanner` · `orchestrator` · `contract-auditor`(§0 영향) | `/plan-new` · `python nova.py impact` · `masterplan adopt` |
| ④ 실행 | `nova-screen`(화면 조립) | `backend-developer` · `frontend-developer` · `devops-engineer` · `refactorer` · `ux-writer` · `tester` | `/task-run` · `python nova.py check` |
| 문제 | - | `debugger` | `/debug` · `/learn` |
| ⑤ 검토 · 감사 | - | `code-reviewer` · `security-auditor` · `contract-auditor` · `accessibility-auditor` · `design-token-guardian` · `docs-auditor` · `ops-auditor` · `performance-engineer` · `integrator`(통합) | `/review-request` · `/deep-audit` |
| ⑥ 검증 · 마무리 | `nova-ui-verify`(화면을 띄워 확인) | `tester` · `verifier` · `e2e-tester` · `doc-writer` | `/finish` · `/history-new` · `/converge` |
| 개선(정의 만들기) | nova-subagent-creator · nova-skill-creator · nova-command-creator | `agent-creator`(만들지 · 기존으로 충분한지) | `uv run python scripts/claude_check.py --check` |
| 화면(nicomms 운영 콘솔) | `nicomms-screen`(AppShell side · ListPage 등으로 조립, 갭은 토큰 · 부품 제안) | `screen-architect` · `ux-writer` · `design-asset-keeper` | `python nova.py mockups` · `ui-smoke` |
| 디자인 축 | `nova-screen` | `design-director` · `design-rule-architect` · `design-asset-keeper` · `design-researcher` | `/spec` 4-0 · `/plan-new` 4 · `/change` |
| 업종 규칙(도메인 팩) | - | `<팩>-specialist`(팩 이름의 `_` 는 `-`, `domain/` · 팩과 짝 · 읽기 전용) | `/req-analyze` · `/plan-new` · `/task-run` · `/review-request` · `python nova.py new-pack` |
| 운영 결함 | - | `incident-responder`(P0) · `doc-writer`(사후기록) | `/issue` → `/hotfix` → `/postmortem` → `/learn` |
| 승인된 범위의 변경 | - | `change-manager` · `contract-auditor` | `/change` → `/plan-new` |
| 병렬 · 상류 | - | `orchestrator`(설계만 — 착수 전 묶음) | `/dispatch` · `/worktree-new` · `/handoff-start` · `/handoff-end` · `/orchestrate` · `/worktree-sync` · `/converge` · `/sync-upstream` — 모두 공통 영역 7항목이 끝난 뒤(병렬 게이트) |
| 릴리스 · 세션 | - | `release-manager` · `project-manager` · `verifier` | `/release` · `/session-start` · `/session-end` · `python nova.py progress` |
| 에이전트 배치 | - | `agent-creator` | (새 정의를 둘지 판단할 때) |

- 에이전트는 **재료**를 내고 판정은 main 이 한다. 번호가 붙는 기록 · 커밋 · 푸시는 main 만 한다(단일 기록자)
- 비싼 병렬(에이전트 여럿)은 명령이 정한 자리(`/deep-audit` 축 · `/intake` 파일 · `/review-request` 범위 · `/spec` 골격 · `/finish` 검증)에서만 — 그 밖은 확인 후

## 3. 고객 인터뷰 규칙 (① — `/req-interview`)
고객은 기획 · 설계 용어를 모른다는 전제로 진행한다. Superpowers `brainstorming` 의 대화 원칙을 고객 인터뷰에 맞게 정했다.

**진행 방식 세 가지 — 시작할 때 고른다**
| 방식 | 언제 | Claude 가 하는 일 |
|---|---|---|
| (공통) 입고 자료가 있을 때 | `docs/warehouse/inbound/` 에 자료가 있으면 | `/intake` 가 찾은 **부족 항목(G-*) · 근거 없는 영역만** 묻는다 — 자료에 이미 답이 있는 것은 다시 묻지 않는다 |
| A. 실시간 인터뷰 | 고객(또는 고객 대신 사용자)이 이 대화에 직접 답할 때 | 한 번에 질문 하나로 진행 · 되읽기 · 기록 |
| B. 질문지 준비 | 사용자가 고객을 직접 만나 인터뷰할 때 | 고객 · 업종에 맞춘 질문지(§3.3) + 기록 양식을 만든다 → 인터뷰 후 C 로 |
| C. 회의록 · 녹취 분석 | 회의록 · 녹취 · 메일 · 메모를 받았을 때 | 원문을 붙여 넣고 → 발언 정리 · 빠진 영역 · 모순 · 추가 질문 목록 |

**대화 원칙**
1. **첫 메시지는 두 가지뿐**: "질문 없이 바로 시작해도 된다"는 한 줄 + 실제 장면을 묻는 열린 질문 하나("이게 있었으면 좋겠다고 느낀 마지막 순간을 말씀해 주세요")
2. **메시지마다 질문 하나**. 보기 목록을 달지 않는다. 고객이 막힐 때만 짧은 보기를 준다
3. **고객 말로 묻는다**: "엔터티 · 권한 모델 · 워크플로" 같은 말 대신 "누가 · 언제 · 무엇을 보고 · 무엇을 누르나"로 묻는다
4. **장면을 묻는다**: "지난번에 그 일을 어떻게 처리하셨는지 처음부터 따라가 볼까요?", "하나만 잘 된다면 무엇이었으면 하세요?", "제가 무엇을 잘못 만들면 가장 곤란하실까요?"
5. **되읽기**: 한 부분(누구를 위한 것인지, 한 화면의 동작 등)을 이해하면 200~300자로 되읽고 "틀리거나 빠진 것이 있나요?"로 끝낸다. 고객이 말한 것과 Claude 의 **[추측]** 을 구분한다
6. **보여 주기**: 화면 · 배치 · 흐름 · 모양이 다른 선택지는 말보다 보여 준다. 처음 필요할 때 따로 "보여 드리면 더 쉬울 것 같습니다. 화면 예시를 브라우저로 띄워 드릴까요?"라고 묻는다(시각 도우미, §1)
7. **자료 조사 제안**: 근거가 조금 생기면 "기존 시스템 · 엑셀 · 비슷한 서비스를 살펴볼까요?"처럼 무엇을 볼지 말하고 허락을 받는다
8. **원문 보존**: 고객 발언은 다듬지 않고 그대로 인터뷰 기록 §2 에 남긴다(개인정보 · 비밀번호는 지운다)

**3.1 다룰 영역 — 질문 목록이 아니라 지도다(그대로 읽지 않는다)**
| 영역 | 확인할 것 |
|---|---|
| 무엇 · 특별한 점 | 이것이 어떤 종류의 일이고, 다른 것과 무엇이 다른가 |
| 왜 지금 · 성공 | 지금 해야 하는 이유, 고객이 말하는 성공의 모습(숫자 · 장면) |
| 목표 · 비목표 · 반목표 | 할 것, 하지 않을 것, **기술적으로 돌아가도 실패인 것** |
| 사람 | 누가 쓰는가(역할 · 숙련도 · 기기 · 장소), 누가 결정하고 승인하는가 |
| 지금 상태 | 지금은 어떻게 하는가(종이 · 엑셀 · 기존 시스템), 무엇을 시도해 봤나 |
| 선례 | 다른 곳에서 본 것 중 좋았던 것 · 싫었던 것 |
| 만드는 방법 | 고객이 정하고 싶은 것과 맡기는 것(플랫폼 · 기기 · 연동 · 일정 · 예산) |
| 세부 | 고객이 특히 신경 쓰는 부분(문구 · 숫자 형식 · 보고서 모양 · 예외 상황) |
| Nova 표준 | 조직(테넌트)이 여러 개인가, 업종별로 규칙이 다른가(도메인 팩), AI 가 대신 처리해도 되는 일인가(AX 등급) — [docs/std](../std/README.md) |

**3.2 끝내는 기준**: §3.1 의 영역마다 되읽기에 고객이 "맞다"고 답했고, 남은 미결 질문이 "고객만 답할 수 있는 것"뿐일 때 인터뷰를 닫고 ② 로 간다.

**3.3 질문지(방식 B) 형식**: 인터뷰 기록 문서 §2 에 질문을 영역별로 3~5개씩, "열린 질문 → 장면 질문 → 확인 질문" 순서로 두고 답 칸을 비워 둔다. 질문은 고객 업종의 말로 쓴다.

- 질문 전에 체크리스트 최신 완료본 · `intake.json` 부족 항목을 읽고, 맴도는 쟁점은 요구 충돌로 고객 몫에, 드러난 가정은 인터뷰 기록 §4.1 에 남긴다. 수치 모호성 관문은 쓰지 않는다(§4 빌더 점검 + 승인 관문)

## 4. 요구 분석 규칙 (② — `/req-analyze`)
1. **크기 판정**을 고객 말로 알린다: 빠른 일(바로 한다) · 작은 변경(대화로 합의 → 요구 문서 → task 추가) · 프로젝트(요구 문서 → 세부 계획). 여러 개의 독립 프로젝트면 나누고 순서를 정한다
2. **요구 문서를 쓴다**(`docs_new.py req`): 목적과 이유, 목표 · 비목표 · 반목표, 사용자, 하위 요구 `REQ-YYMMDD-NN-n` 과 **확인 가능한 수용 기준**, 고객이 정한 방법과 맡긴 방법, 근거(인터뷰 기록 링크). Claude 가 정한 것은 "Claude 판단"으로 표시한다
3. **빌더 점검**: 새 서브에이전트에게 요구 문서만 주고(Superpowers `brainstorming/builder-check-prompt.md`) "이 문서만으로 만들 수 있나?"를 묻는다. 나온 질문을 셋으로 나눈다
   - **이미 답이 있음** → 문서에 답을 채운다
   - **사소함** → Claude 가 정하고 "Claude 판단"으로 표시한다
   - **고객 몫** → 답에 따라 만들 것이 달라지는 질문. 중요한 순서로 **한 번에 모아** 묻는다(질문은 이 한 번뿐)
4. **승인 관문**: 고객(사용자)이 요구 문서를 승인하기 전에는 코드 · 골격 · 설치 · 프로젝트 생성을 하지 않는다. 읽기 · 조사는 된다. 승인은 요구 문서 "확인한 결정" 표에 남긴다
5. 승인 후 다음은 **계획**이다 → `/plan-new`(Superpowers `writing-plans`)

### 4.1 속도 — 일의 크기 · 되돌림에 맞춘 절차 ([REQ-261104-17](../requirement/requirement_261104_17.md))
표준화의 목적은 신속 · 효율 · 정확이다. 절차의 무게를 **일의 크기와 되돌림 가능성**에 맞춘다.

| 표시 | 언제 | 검사 | 기록 | 관문 |
|---|---|---|---|---|
| `[FAST]` · `/sdd fast` | 되돌릴 수 있는 작은 일(문구 · 작은 화면 · 스크립트 버그) | task 마다 `python nova.py quick` | 커밋 + 푸시 묶음 git 기록 | 요구 승인만 |
| (표시 없음) | 보통 일 | task 마다 `quick` · 단계 끝 `check` | `/docs-write` 등급 | 명령이 정한 관문 |
| `[DEEP]` | **되돌리기 어려운 일** — 아래 목록 | task 마다 전체 `check` + 해당 판정 에이전트 + `/review-request` | 보통 일 이상 + 필요하면 ADR | 사용자 확인 뒤 실행 |

- **[DEEP] 필수(어느 프로젝트 규모든)**: 회계 마감 · 정산 · 금액 계산, DB 구조 · 마이그레이션, 인증 · 권한(`rbac.json` · 역할 확대 · 무인 허용 목록 적용도 권한 확대 — [agents.md §5.1](agents.md)), 데이터 삭제 · 보존 정책, 외부 공개(공개 API 계약 · 태그 원격 푸시 · 저장소 설정), 의존성 추가, 개인정보 칸, AX 등급 올림. `/docs-write grade` 가 경로 신호(ADR · 모델 · 마이그레이션 · 계약 파일)로 알린다 — 회계 · 개인정보는 사람이 표시한다
- **자동 진행(`/task-run --auto`)**: 위 크기 판정과 관문은 그대로이고, 상한(고치기 회차 · 호출 수 · 연속 실패 · 동시 구현자)은 `.claude/commands/task-run.md` 의 안전장치 표가 유일한 정본이다 — 여기에 값을 옮겨 적지 않는다. `[DEEP]` 항목은 자동으로 진행하지 않고 질문 모음에 올린다
- **빠른 검사만으로 푸시 · 출시하지 않는다** — 푸시 묶음 · 단계 끝 · `/finish` · `/release` 는 언제나 전체 `check`
- **규모 프로파일**(`nova.project.json` `profile` — `lite` 소형 · `product` 제품 · `platform` 플랫폼 · 명령 `python nova.py profile get|set|check|suggest` · lint 가 선언 · 이유를 판정 · 복제본은 `product` 로 시작 · `lite` 면 병렬 게이트가 닫힌다)이 위 기본값을 프로젝트 단위로 정한다: `lite` 는 착수 절차(체크리스트 · PRD · SPEC · 마스터플랜)를 건너뛰고 `/req-new` → `/plan-new` 짧은 판 · `/sdd light` 기본 · 병렬 없음, `product` 는 전체 착수 · 공통 영역 뒤 병렬, `platform` 은 전체 + 마스터플랜 봉인 · 이력 하한 '보통 일'. **승인 관문 · 안전 검사 · 기록 하한(커밋 + git 기록)은 어느 프로파일에서도 빼지 않는다**

## 5. 계획 · 실행 · 검토 규칙 (③~⑥)
- **계획(`/plan-new`)**: Nova 템플릿 §0~§13 에 `writing-plans` 의 요소를 넣는다. **전역 제약**(버전 · 이름 · 문구 · 플랫폼 규칙, 원문 값 그대로)과 **검토 초점**(어느 task 의 테스트도 건드리지 않지만 사람이 쓰다 부딪힐 입력 · 상황 5가지 → 각각 담당 task 에 테스트 추가)은 §11.1 · §11.2 에, task 의 파일 · 인터페이스 · 단계는 tasks 문서에 쓴다. 다 쓴 뒤 자체 점검 5가지(요구 반영 · 단계 명확성 · 타입 일관성 · 검토 초점 · 분량)를 하고, 사용자에게 **실행 방식**을 묻는다
- **실행(`/task-run`)**: 서브에이전트 방식(독립 검토, 비싸다)과 직접 방식(빠르다, 마지막에 한 번 검토) 중 고른 것으로 한다. task 마다 TDD 다섯 단계를 지키고, 끝나면 `- [x]` 와 커밋 · git 기록을 같은 흐름에서 남긴다(나중에 몰아서 하지 않는다). `--auto` 를 붙이면 main 이 겹치지 않는 task 를 한 층 병렬로 배치해 이어 가고 상한 · 멈춤 조건은 task-run 의 안전장치 표를 따른다(값은 거기에만)
- **검토(`/review-request`)**: 검토자에게 요구 · 계획 · 커밋 범위(BASE..HEAD)를 주고 결과를 리뷰 문서로 남긴다. 받은 지적은 하나씩 코드로 확인하고 수용/반박을 근거와 함께 "처리" 칸에 쓴다
- **디버깅(`/debug`)**: 재현 → 증거 수집 → 가설 하나 → 확인 → 고침 → 회귀 테스트. 세 번 고쳐도 안 되면 멈추고 구조를 의심한다(사용자에게 보고)
- **마무리(`/finish`)**: 전체 테스트 · lint 통과 확인 → 병합/PR/유지 중 사용자 선택 → history · git 기록 · 필요하면 `/session-end`

## 6. 하지 않는 것
- `docs/superpowers/` 폴더를 만들지 않는다(Nova 위치로 쓴다 — §1)
- 영어로 기록하지 않는다. 스킬 본문이 영어여도 산출물은 한국어
- 고객이 승인하지 않은 요구로 구현을 시작하지 않는다(§4.4)
- 증거 없이 완료를 주장하지 않는다(§5)
- 스파이크(버리는 시험 제작)를 그대로 제품 코드로 쓰지 않는다. 남기려면 새 요구로 다시 승인 관문을 거친다
