# 에이전트 운영 가이드 — 총괄(main) · 역할 · 지시와 피드백 · 병렬

> 결정: [ADR-009](../adr/ADR-009-commands-skills-agents.md)(명령 · 스킬 · 에이전트 3층) · [ADR-010](../adr/ADR-010-agent-folders.md)(폴더형 편제) · [ADR-008](../adr/ADR-008-parallel-bus-release.md)(단일 기록자 · 메시지 버스) · 이 가이드 [REQ-261105-08](../requirement/requirement_261105_08.md).
> 정본: 명단 · 부르는 곳은 `.claude/agents/README.md` 의 편제표(생성물 — `claude_check.py --write`). 이 문서는 **어떻게 굴리나**를 설명하고, 명단 · 숫자는 그 표를 따른다.

## 1. 한 줄 요약
Nova 는 **main 하나가 총괄하는 허브형**이다. 에이전트끼리 직접 말하지 않고, 지시 · 전달 · 피드백은 모두 main 을 거친다. 일부러 그렇게 했다(플랫폼이 못 하게 하는 것이 아니다 — 공식 문서상 하위 에이전트도 기본으로는 아래 층을 부를 수 있고, Nova 는 정의 `tools` 에 `Agent` 를 넣지 않아 막는다) — 기록자가 여럿이면 번호 · 원장이 엉키고, 서로 부르기 시작하면 비용과 책임이 흐려진다. 대가는 main 의 문맥이 병목이 된다는 것이고, 이 가이드의 규칙 대부분이 그 병목을 줄이는 장치다.

## 2. main 과 에이전트
| | main | 에이전트 |
|---|---|---|
| 정체 | 사용자와 대화하는 **이 세션**(Claude Code 본 대화) — `.claude/agents/` 명단에 없다 | `.claude/agents/<폴더>/<이름>.md` 로 정의된 하위 역할 — main 이 부를 때만 산다 |
| 하는 일 | 일 나누기 · 지시서 · 판정 · 명령 재실행 확인 · 커밋 · 원장 · 번호 기록 · 사용자와 대화 | 맡은 한 가지(조사 · 설계 초안 · 구현 · 검증 · 기록 본문) |
| 문맥 | 대화 전체 | 새 문맥 — main 이 지시서에 준 것만 안다 |
| 다른 에이전트 부르기 | 한다 | **안 한다** — 정의 `tools` 에 `Agent` 를 넣지 않아 Nova 가 일부러 막는다(플랫폼 제한 아님 · 부르는 규칙 1) |
| 사용자에게 묻기 | 한다 | **안 한다** — `AskUserQuestion` 은 하위 에이전트에서 늘 빠지고, 권한 확인 창은 main 으로 넘어온다 |
| 결과의 지위 | 판정 | **가설** — main 이 코드 · 명령 출력으로 확인한 뒤 채택 |

## 3. 지시 · 전달 · 피드백 — 한 task 의 고리
```
사용자 ─ main(총괄 · 판정 · 기록 · 커밋)
            │ ① 지시서(파일)            ▲ ② 보고서(파일) + 짧은 요약
            ▼                           │
     구현 에이전트 ──── main 경유 ────> 검토 에이전트
            ▲   ④ 고치기 지시(같은 구현자 재개)    │ ③ 지적(치명 · 중요 · 경미)
            └────────────── main ◀────────────────┘
                 ⑤ 범위를 좁힌 재검토 → 처리됨이면 닫음 · main 이 명령을 직접 다시 돌려 확인 → 커밋 · task 체크
```
1. **지시서** — main 이 task 원문 · 정해 둔 판정 · 앞 task 에서 생긴 인터페이스를 파일로 쓴다. 지시서가 요구의 단일 원천이다(대화 이력을 붙여 넣지 않는다)
2. **보고서** — 구현자는 전문을 파일로, main 에게는 상태(끝남 · 걱정 있음 · 맥락 필요 · 막힘) · 커밋 · 테스트 한 줄만
3. **검토** — 새 검토자가 지시서 · 보고서 · 차이 파일 셋을 읽고 '요구 충족'과 '품질' 두 판정을 낸다. 경미는 원장에 미뤄 최종 검토에서 분류한다
4. **고치기** — 앞 회차는 같은 구현자를 이어 부르고(문맥 유지), 뒤 회차는 한 등급 위 모델의 새 구현자(경계는 README '모델 등급'). 회차 상한은 `.claude/commands/task-run.md` 의 안전장치 표가 정본이다 — 상한에 닿고도 남으면 main 이 판정해 원장에 남긴다
5. **확인** — 담당이 낸 '통과'는 main 이 그 명령을 직접 다시 돌린 뒤 체크한다(CLAUDE.md '이 PC 환경')

실행 원장 · 지시서 · 보고서는 `.superpowers/sdd/<계획>/`(git 무시) — 문맥이 압축돼도 이 원장과 `git log` 로 이어 간다.

**병렬 worktree 세션끼리**는 메시지 버스를 쓴다 — `/send` · `/inbox`(본 트리 `.collab/` 하나, 커밋 안 함). 보낸 것은 고치지 않고, 3번 넘게 오가면 main 에 넘긴다(escalation).

## 4. 역할 — 8묶음
명단 · 부르는 명령은 편제표(`.claude/agents/README.md`)가 정본이다. 아래는 묶음의 성격이다.

| 묶음(폴더) | 하는 일 | 쓰기 | 대표 |
|---|---|---|---|
| 조사 `research/` | 자료 · 코드 · 밖의 사례를 읽고 요약 | 읽기 전용 | researcher · inbound-analyst · mockup-analyst |
| 설계 `planning/` | 선택지 · 초안(파일 · 번호는 main) | 읽기 전용 | architect · req-analyst · task-planner · orchestrator(병렬 묶음 설계만) · integrator(보고 합치기) |
| 구현 `development/` | 코드 · 테스트 | 쓰기 | backend-developer · frontend-developer · devops-engineer · database-architect · debugger |
| 검증 · 판정 `quality/` | 재고 판정 — 재지 않은 것은 발견이 아니다 | 읽기 전용 | code-reviewer · security-auditor · contract-auditor · tester · verifier · e2e-tester |
| 기록 `docs/` | main 이 만든 문서의 본문 | 쓰기 | doc-writer · ux-writer |
| 운영 `ops/` | 원장 조회 · 변경 · 릴리스 · 사고 | 기본 읽기 전용 | project-manager · registry-keeper · release-manager · incident-responder |
| 메타 `meta/` | 새 에이전트를 둘지 판정 | 정의 파일만 | agent-creator |
| 도메인 `domain/` | 업종 규칙 | 읽기 전용 | `<팩>-specialist` |

## 5. 병렬 호출 — 언제 동시에, 언제 순서대로
main 은 한 번에 여러 에이전트를 함께 띄울 수 있다(독립 작업은 한 메시지에 함께 — 끝나는 대로 알림). 일의 성격으로 가른다.

| 일 | 병렬 | 이유 · 자리 |
|---|---|---|
| 읽기 · 조사 · 검토 · 감사 | **동시에** | 파일을 쓰지 않아 부딪히지 않는다 — `/deep-audit` 축 · `/intake` 자료 · `/review-request` 범위 · `/spec` 골격 · `/finish` 검증. 셋 이상이면 `integrator` 로 합친다 |
| 서로 다른 파일을 고치는 구현 | 조건부 | 같은 작업 트리에서 파일이 겹치지 않을 때만 — 겹침 판정은 `.claude/commands/task-run.md` 의 병렬 배치(`task_batch.py` 가 묶음을 낸다)를 따르고 여기서 다시 판정하지 않는다. 안전하게는 에이전트마다 작업 폴더(worktree 격리) |
| 같은 파일 · 같은 계약을 고치는 구현 | **순서대로** | 뒤 task 가 앞 결과에 기댄다(예: 2026-11-05 쿠키 전환 — 서버 → SDK → 스모크) |
| 큰 묶음 병렬 개발 | worktree + 버스 | 공통 영역 완료 선언 뒤 `/worktree-new` · `/dispatch` → main 이 `/converge`. 게이트가 닫혀 있으면 직렬([plans README §6](../plans/README.md)) |

대가: 에이전트마다 새 문맥이라 토큰이 개수만큼 는다 · 무거운 테스트를 동시에 돌리면 이 PC 에서 시간 초과 → 구현 에이전트에게 전체 `test` · `check` 를 시키지 않고 main 이 관문에서 한 번 돌린다 · **비싼 병렬(여러 개 · 5분 넘는 일)은 크기를 먼저 말하고 시작**([IDENTITY](../../IDENTITY.md) '지연이 생길 때').

### 5.1 무인 허용 목록 제안 (`/task-run --auto` — 제안만, 적용은 따로)
`--auto` 가 권한 확인 창에서 멈추지 않게 `.claude/settings.json` 의 `permissions.allow` 를 채우자는 제안이다. **이 절은 기준만 정하고 settings.json 은 바꾸지 않는다.**
- **허용 후보**: 읽기 · 검사 명령만(상태 · 로그 조회, `python nova.py lint` · `quick` 같은 검사)
- **ask 로 남긴다(되돌리기 어려운 것)**: `git push` · `git tag` · `release ship` · `release publish` · 의존성 추가 · 데이터 삭제 · 외부 설정 변경
- **모양**: 명령 + 하위명령을 정확히 일치시킨다(`Bash(python nova.py lint)`). 하위명령 없는 접두 일괄 허용(`Bash(python nova.py:*)` · `Bash(python nova.py *)`)은 금지 — 같은 접두 밑에 `release ship` 이 함께 열린다
- **적용**: 허용 목록을 넣는 것도 권한 확대이므로 `[DEEP]` 로 따로 사용자 승인을 받는다([superpowers.md §4.1](superpowers.md))
- **지키는 장치**: `tests/test_task_batch.py::test_settings_has_no_blanket_allow` 가 접두 일괄 · push · tag · 릴리스 허용을 막는다

## 6. 비용을 줄이는 장치 (REQ-261105-08)
- **모델 등급** — 일의 위험으로 고른다: 옮겨 쓰기는 가벼운 등급, 보통 구현 · 재검토는 중간, [DEEP] 검토 · 설계 · 최종 검토는 상위. 표는 `.claude/agents/README.md` '모델 등급'
- **긴 보고는 파일로** — main 이 `.claude/state/reports/<이름>.md` 경로를 주면 읽기 전용 에이전트도 그 파일에만 전문을 쓰고 짧게 돌려준다(부르는 규칙 9). main 의 문맥이 덜 분다
- **호출 기록 원장** — `/round-close` 가 `python nova.py usage --record` 로 회차마다 집계를 `docs/memo/agent_usage.jsonl` 에 쌓는다. `python nova.py usage --unused` 가 한 번도 안 불린 에이전트를 낸다 → '두 판본 동안 안 부른 얇은 정의는 합친다'(ADR-010)를 판본을 낼 때 판정한다

## 7. 2026-11-05 점검 결과 (사용자 질문에 대한 분석)
> 질문: "전체를 총괄하고 에이전트 간 커뮤니케이션으로 지시 · 전달 · 피드백을 하며 효율을 높이는 구조인가 · 역할 설명 · 더 필요한 에이전트나 보완할 것"

**잘 되는 것** — 같은 날 plan_REQ_04 8단계(웹 인증 쿠키)를 이 고리로 돌렸다: 서버 구현자 → 검토자가 중요 지적 1건(로그아웃 우회 경로의 CORS 헤더 누락) → 같은 구현자가 실패 테스트를 먼저 세우고 고침 → 재검토 '처리됨' → main 이 테스트를 다시 돌려 확인. 에이전트끼리 직접 말하지 않아도 지시 · 피드백 고리는 닫혔다.

**보완한 것**(REQ-261105-08)
| 보인 것 | 근거 | 보완 |
|---|---|---|
| 읽기 전용 검토자가 검토 전문을 main 에 돌려보낸다 — 허브 병목이 커진다 | 같은 날 검토 2회 모두 "쓰기 도구 없음" | 보고서 경로 규칙(부르는 규칙 9) — 읽기 전용 원칙(A5)은 그대로 |
| 어느 역할에 어느 모델을 쓸지 규칙이 없다 | 정의 파일은 모두 상속 · 그날 main 이 일마다 고름 | 모델 등급 표 |
| '부른 기록'이 이 PC 의 git 무시 폴더에만 있다 | `usage` 출력이 `.claude/state` 7일치 · ADR-010 재검토 원천 미정 | 커밋되는 원장 + `--record` · `--unused` + 회차 마감 단계 |

**새 에이전트 판단 — 지금은 만들지 않는다.** 후보로 떠오른 '규제 · 개인정보 감사'(ISMS-P · 개인정보보호법)는 `req-analyst` · `practice-advisor`(계획 단계 놓친 관점)와 `security-auditor`(표준 축)가 이미 다룬다. 만들기 전 세 가지 확인(`.claude/agents/README.md` '새 에이전트를 만들 때') 중 '두 명령 이상에서 반복'을 넘지 못한다 — 기존 정의의 설명을 넓히는 쪽이 싸다. 얇은 정의의 합치기는 원장이 두 판본 쌓인 뒤 `usage --unused` 로 판정한다.

**정정(2026-11-05, 공식 문서 확인)** — 이 점검 때까지 '에이전트는 다른 에이전트를 못 부른다'로 적었으나 플랫폼 제한이 아니다. 하위 에이전트도 기본으로는 아래 층을 부를 수 있고, Nova 가 정의 `tools` 에 `Agent` 를 넣지 않아 일부러 막는다(§1). 허브형 결론은 그대로다.

**놓친 관점** — 같은 날 영어 문장이 새어 나간 것은 에이전트가 아니라 main 이었다(응답 검사 훅이 잡음). 장치는 작동했고 고칠 쪽은 main 이다.

## 8. 빠른 안내
| 하고 싶은 것 | 이렇게 |
|---|---|
| 어떤 에이전트를 부를지 | 편제 README '상황 → 에이전트' 표 |
| 구현을 에이전트에게 맡기기 | `/task-run`(실행 방식 subagent — 구현자 + 검토자 고리) |
| 저장소 전체를 여러 시각으로 | `/deep-audit`(읽기 전용 병렬) |
| 큰 묶음을 동시에 개발 | `/dispatch` → `/worktree-new` → `/converge` |
| 이번 회차에 누가 불렸나 | `python nova.py usage --days 7` |
| 한 번도 안 불린 에이전트 | `python nova.py usage --unused` |
| 새 에이전트를 만들까 | nova-subagent-creator 스킬 · `agent-creator` |
