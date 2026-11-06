# 에이전트 편제

Nova 의 전문 서브에이전트 명단과 부르는 규칙입니다. 어떻게 굴리나(main 의 역할 · 지시와 피드백 고리 · 병렬)는 [운영 가이드](../../docs/conventions/agents.md). 결정: [ADR-009](../../docs/adr/ADR-009-commands-skills-agents.md)(명령 · 스킬 · 에이전트 3층) · ADR-010(폴더형 편제 — psg05 역할을 폴더로 묶어 대부분 살림). 형식 검사: `uv run python scripts/claude_check.py --check`(lint 단계).

## 상황 → 에이전트
명령이 부르는 자리가 정해져 있으면 그것을 따른다. 아래는 빠른 찾기다(이름은 lint A19 가 실재를 검사).

| 상황 | 에이전트 |
|---|---|
| 넓게 조사 · 대안 비교 | `researcher` |
| 입고 자료 판독(글 · 목업) | `inbound-analyst` · `mockup-analyst` |
| 첫 세션 · 새 합류 요약 | `project-starter` |
| 요구 · PRD · SPEC 빌더 점검 | `req-analyst` |
| 계획 직전 놓친 관점 · 기회 | `practice-advisor` |
| 기반 4단계 · ADR 초안 | `architect` |
| API · 이벤트 / 표 · 마이그레이션 / 화면 골격 | `api-designer` · `database-architect` · `screen-architect` |
| 계획서 · task / 마스터플랜 / 병렬 묶음 | `task-planner` · `masterplanner` · `orchestrator` |
| 구현(서버 / 화면 / 게이트 · 인프라 / 정리) | `backend-developer` · `frontend-developer` · `devops-engineer` · `refactorer` |
| 결함 원인 / P0 긴급 | `debugger` · `incident-responder` |
| 테스트 / lint / 화면 구동 | `tester` · `verifier` · `e2e-tester` |
| 코드 검토 · 보안 · 계약 영향 | `code-reviewer` · `security-auditor` · `contract-auditor` |
| 접근성 · 토큰 · 성능 · 운영 · 문서 정합 | `accessibility-auditor` · `design-token-guardian` · `performance-engineer` · `ops-auditor` · `docs-auditor` |
| 새 이름 만들기 전 · 변경 요청 정리 | `registry-keeper` · `change-manager` |
| 원장 종합 / 병렬 보고 통합 | `project-manager` · `integrator` |
| 디자인 축 종합 · 규칙 변경안 · 부품 관문 · 밖의 사례 | `design-director` · `design-rule-architect` · `design-asset-keeper` · `design-researcher` |
| 화면 문구 / 긴 기록 본문 / 릴리스 노트 | `ux-writer` · `doc-writer` · `release-manager` |
| 업종 규칙(켜진 도메인 팩) | `<팩>-specialist`(팩 이름의 `_` 는 `-`) |
| 새 에이전트를 둘지 판단 | `agent-creator` |

## 체계 — 세 층
| 층 | 맡는 것 | 위치 |
|---|---|---|
| 명령 | **절차** — 사용자가 부르는 일의 순서와 관문 | [`.claude/commands/`](../commands/) |
| 스킬 | **판단 묶음** — 요청 문장으로 자동 발동되는 방법 | [`.claude/skills/`](../skills/) |
| 에이전트 | **역할** — 명령 · 스킬이 정한 자리에서 부르는 전문가 | 이 폴더(성격별 하위 폴더) |

## 폴더 — 성격과 도구 원칙
Claude Code 는 하위 폴더를 재귀로 읽고 에이전트를 `name` 으로만 식별합니다(폴더가 달라도 이름이 같으면 하나만 실린다 — lint A2 가 막는다). **묶음 · 읽기 전용 여부는 폴더에서 파생**합니다(정의에 `> 묶음:` 줄을 쓰지 않는다).

| 폴더 | 묶음 | 원칙 |
|---|---|---|
| `research/` | 조사 | 넓게 읽고 요약 — **읽기 전용 · Bash 필수**(실측) |
| `planning/` | 설계 | 선택지 · 초안을 돌려준다 — **읽기 전용**. 파일 · 번호는 main 이 만든다 |
| `development/` | 구현 | 코드 · 테스트를 쓴다 — 쓰기. 커밋 · 기록은 main |
| `quality/` | 검증 · 판정 | **읽기 전용 · Bash 필수**. 재지 않은 것은 발견이 아니다 |
| `docs/` | 기록 | main 이 만든 파일의 본문만 채운다 — 번호 · 인덱스는 건드리지 않는다 |
| `ops/` | 운영 | 기본 **읽기 전용**, 쓰기는 `release-manager` · `incident-responder` 둘 |
| `meta/` | 메타 | 정의 파일만 쓴다 |
| `domain/` | 도메인 | `<팩>-specialist` 만 — 팩과 짝(`python nova.py new-pack` 이 만든다) · 읽기 전용 · 프로젝트 소유(상류 받기 대상 아님) |

## 부르는 규칙
1. **오케스트레이션은 main 하나가 한다.** Nova 는 에이전트가 다른 에이전트를 부르지 않게 **일부러 막는다** — 플랫폼 제한이 아니다(공식 문서: 하위 에이전트도 기본으로는 아래 층을 부를 수 있다). 정의의 `tools` 에 `Agent` 를 넣지 않아 막는 것이고, 이유는 단일 기록자 · 사용자 판단 요청은 main 만 하기 위해서다(`AskUserQuestion` 은 하위 에이전트에서 늘 빠진다 — 권한 확인 창은 main 으로 넘어온다). 무엇을 몇 개 띄울지는 명령 절차가 정한다(`orchestrator` 는 병렬 묶음을 **설계만** 한다)
2. **병렬은 명령이 정한 자리에서만** 띄운다 — `/deep-audit` 축 · `/intake` 파일 · `/review-request` 범위 · `/spec` 골격 · `/finish` 검증 · `/task-run --auto` 의 겹치지 않는 구현(`task_batch.py` 가 낸 묶음만). 독립 작업은 한 메시지에 함께 띄우고, 셋 이상이면 `integrator` 로 합친다
3. **비싼 병렬은 확인한 뒤에** 띄운다 — 서브에이전트 여러 개 · 5분 넘는 검증은 사용자에게 크기를 먼저 말한다([IDENTITY.md](../../IDENTITY.md) '지연이 생길 때')
4. **반환은 가설이다 — 판정은 main 이 한다.** main 이 코드 · 명령 출력으로 확인한 뒤에 고치거나 기록한다
5. **반환은 4절**이다 — 핵심 답 · 실측 · 근거(`파일:줄`) · 미해결(없으면 '없음')
6. **단일 기록자** — 번호가 붙는 기록 · 원장 · 커밋 · 푸시는 main 만 한다([ADR-008](../../docs/adr/ADR-008-parallel-bus-release.md)). 정의의 '하지 않는 것' 절 밖에 그 명령 이름이 나오면 lint 가 실패시킨다
7. 모든 위임 · 보고는 **한국어**([CLAUDE.md](../../CLAUDE.md) 규칙 0). 함께 일하는 사람은 "사용자"라고 부른다(Nova 는 플랫폼 이름)
8. 폐지된 이름(`synthesizer` · `planner` · `implementer` · `ui-auditor`)을 명령 · 스킬이 부르면 lint 가 새 이름을 안내한다
9. **긴 보고는 파일로**(REQ-261105-08-1) — main 이 보고서 경로 `.claude/state/reports/<이름>.md`(git 무시 · 셸 쓰기 허용 경로)를 주면, 읽기 전용 에이전트도 Bash 따옴표 heredoc(`cat > 경로 <<'EOF'` — 따옴표가 있어야 `$` · 역슬래시가 그대로 들어간다)으로 **그 파일에만** 전문을 쓰고(길면 나눠 `>>` 로 이어 붙이고 끝 절까지 들어갔는지 다시 읽어 확인한다 — 긴 heredoc 이 중간에서 잘린 일이 있다) main 에게는 핵심 답 · 판정 · 치명/중요 한 줄씩만 돌려준다. 저장소의 다른 파일은 여전히 쓰지 않는다(A5 의미 그대로). 경로를 주지 않으면 지금처럼 전문을 돌려준다
10. **병렬 위임** — 분석 · 조사 · 검토 요청은 배경 읽기 전용 에이전트에 맡기고, main 은 진행 중인 task 를 계속하며, 계획이 이미 정한 다음 task 는 사용자에게 묻지 않고 바로 간다.

## 모델 등급 — 역할 · 위험 → 모델 (REQ-261105-08-2)
정의 파일의 `model` 은 비워 두고(상속), **main 이 부를 때 일의 위험으로 고른다**. 값은 claude_check A15 가 허용하는 이름(`opus` · `sonnet` · `haiku` · `inherit`).

| 일 | 등급 | 예 |
|---|---|---|
| 지시서에 코드 · 값이 다 있는 옮겨 쓰기 · 한 파일 기계적 수정 | `haiku` | 문구 한 줄 · 상수 바꾸기 |
| 보통 구현 · 범위를 좁힌 재검토 · 조사 · 요약 | `sonnet` | task 구현(서버 · 화면 · 스크립트) · 고치기 뒤 재검토 |
| [DEEP] 영역 검토(인증 · 권한 · 계약 · DB 구조 · 금액) · 설계 판단 · 최종 전체 검토 · 고치기 뒤쪽 회차(상한은 `.claude/commands/task-run.md` 안전장치 표) | `opus` | 인증 경계 task 검토 · `/review-request` 최종 · `architect` |

- 턴 수가 토큰 단가보다 비싸다 — 여러 단계 일을 가장 싼 등급에 맡기면 턴이 늘어 오히려 비싸진다. 검토자의 바닥은 `sonnet`
- 정의 파일에 `model` 을 박는 것은 그 역할이 늘 같은 위험일 때만(예: 늘 [DEEP] 인 판정자)

부르는 법(예):

```text
Agent(subagent_type: "security-auditor", description: "인증 경계 감사", prompt: "범위 BASE..HEAD — 한국어로 4절 보고")
```

새로 만든 정의는 세션이 타입 목록을 다시 읽은 뒤에 부를 수 있습니다.

## 재검토 조건
쓰이는 자리가 얇은 정의(`project-starter` · `design-director` · `design-asset-keeper` · `design-rule-architect` · `agent-creator`)는 **두 판본 동안 부른 기록이 없으면 가까운 정의로 합친다**(재검토 조건 ADR-010). '부른 기록'의 원천은 호출 기록 원장 `docs/memo/agent_usage.jsonl` 이다 — `/round-close` 가 회차마다 `python nova.py usage --record` 로 한 줄 쌓고(본 작업 트리만), `python nova.py usage --unused` 가 원장 전체에서 한 번도 안 불린 이름을 낸다(REQ-261105-08). 판정 시점은 판본을 낼 때(`/release`) 사람이 본다. 합치면 명령 · 스킬의 호출도 함께 고친다.

## 편제표 (생성물 — 손으로 고치지 않는다)
`uv run python scripts/claude_check.py --write` 가 정의 파일(폴더 · 이름 · tools)과 명령 · 스킬 문서의 호출에서 만듭니다. 어긋나면 lint(A12)가 실패합니다.

<!-- 편제표: scripts/claude_check.py --write 가 만든다 — 손으로 고치지 않는다 -->
| 폴더 | 이름 | 묶음 | 쓰기 | 부르는 곳 |
|---|---|---|---|---|
| research | `design-researcher` | 조사 | 읽기 전용 | /plan-new · /spec |
| research | `inbound-analyst` | 조사 | 읽기 전용 | /checklist · /intake · /kickoff · /masterplan |
| research | `mockup-analyst` | 조사 | 읽기 전용 | /checklist · /intake · /kickoff · /masterplan · /spec |
| research | `project-starter` | 조사 | 읽기 전용 | /kickoff · /session-start |
| research | `researcher` | 조사 | 읽기 전용 | /analyze · /plan-new |
| planning | `architect` | 설계 | 읽기 전용 | /foundation |
| planning | `design-director` | 설계 | 읽기 전용 | /plan-new |
| planning | `design-rule-architect` | 설계 | 읽기 전용 | /change · /spec · 스킬 nicomms-screen |
| planning | `integrator` | 설계 | 읽기 전용 | /deep-audit · /review-request · /verify |
| planning | `masterplanner` | 설계 | 읽기 전용 | /masterplan · /plan-new · 스킬 nova-masterplan |
| planning | `orchestrator` | 설계 | 읽기 전용 | /dispatch · /masterplan · /orchestrate · /worktree-new · 스킬 nova-masterplan |
| planning | `practice-advisor` | 설계 | 읽기 전용 | /masterplan · /plan-new · /prd · 스킬 nova-masterplan |
| planning | `req-analyst` | 설계 | 읽기 전용 | /prd · /req-analyze · /spec |
| planning | `screen-architect` | 설계 | 읽기 전용 | /plan-new · /spec · 스킬 nicomms-screen · 스킬 nova-screen |
| planning | `task-planner` | 설계 | 읽기 전용 | /plan-new |
| development | `api-designer` | 구현 | 쓰기 | /spec · /task-run |
| development | `backend-developer` | 구현 | 쓰기 | /deep-audit · /task-run |
| development | `database-architect` | 구현 | 쓰기 | /plan-new · /spec · /task-run |
| development | `debugger` | 구현 | 쓰기 | /debug · /deep-audit · /task-run · 스킬 nova-command-creator |
| development | `devops-engineer` | 구현 | 쓰기 | /deep-audit · /task-run |
| development | `frontend-developer` | 구현 | 쓰기 | /deep-audit · /task-run |
| development | `refactorer` | 구현 | 쓰기 | /deep-audit · /review-request · /task-run |
| quality | `accessibility-auditor` | 검증 · 판정 | 읽기 전용 | /deep-audit · /review-request · /verify · 스킬 nicomms-screen |
| quality | `code-reviewer` | 검증 · 판정 | 읽기 전용 | /deep-audit · /review-request · /task-run |
| quality | `contract-auditor` | 검증 · 판정 | 읽기 전용 | /change · /deep-audit · /plan-new · /review-request · /task-run · /verify |
| quality | `design-token-guardian` | 검증 · 판정 | 읽기 전용 | /deep-audit · /review-request · /verify · 스킬 nicomms-screen |
| quality | `docs-auditor` | 검증 · 판정 | 읽기 전용 | /deep-audit |
| quality | `e2e-tester` | 검증 · 판정 | 읽기 전용 | /e2e-test · /finish · /task-run · 스킬 nicomms-screen · 스킬 nova-ui-verify |
| quality | `ops-auditor` | 검증 · 판정 | 읽기 전용 | /deep-audit |
| quality | `performance-engineer` | 검증 · 판정 | 읽기 전용 | /deep-audit |
| quality | `security-auditor` | 검증 · 판정 | 읽기 전용 | /deep-audit · /review-request · /task-run · /verify |
| quality | `tester` | 검증 · 판정 | 읽기 전용 | /converge · /finish · /task-run · /test |
| quality | `verifier` | 검증 · 판정 | 읽기 전용 | /converge · /finish · /release · /task-run · /verify |
| docs | `doc-writer` | 기록 | 쓰기 | /docs-write · /history-new · /postmortem · /review-request · /session-end |
| docs | `ux-writer` | 기록 | 쓰기 | /task-run · 스킬 nicomms-screen · 스킬 nova-screen |
| ops | `change-manager` | 운영 | 읽기 전용 | /change |
| ops | `design-asset-keeper` | 운영 | 읽기 전용 | /spec · 스킬 nicomms-screen · 스킬 nova-screen |
| ops | `incident-responder` | 운영 | 쓰기 | /hotfix |
| ops | `project-manager` | 운영 | 읽기 전용 | /release · /round-close · /session-end · /session-start |
| ops | `registry-keeper` | 운영 | 읽기 전용 | /spec · /task-run |
| ops | `release-manager` | 운영 | 쓰기 | /release |
| meta | `agent-creator` | 메타 | 쓰기 | 스킬 nova-subagent-creator |
| domain | `example-specialist` | 도메인 | 읽기 전용 | <팩>-specialist 자리 |
<!-- 편제표 끝 -->

## 정의 파일 형식
- 위치: `.claude/agents/<폴더>/<이름>.md` — 루트에는 이 README 만(A18)
- frontmatter: `name`(파일 이름과 같다) · `description`(한국어 40~400자, "…할 때 부른다" 같은 호출 조건, 끝에 "…는 X 몫이다" 경계 문장, 상시 자동 호출 문구 금지) · `tools`(쉼표 구분). `model` 은 쓰지 않는 것이 기본(상속) — 쓰면 claude_check A15 가 값을 검사한다
- 본문: 제목 · 6절을 이 순서로 — `## 언제 나를 부르나` → `## 따르는 규칙` → `## 수행 절차` → `## 반환 형식` → `## 하지 않는 것` → `## 실패·불확실 처리`
- 링크는 폴더 깊이에 맞게(`../../../docs/…` · `../../commands/…`) · `/명령` 은 실재해야 한다 · 색 값 리터럴 금지
- 검사 규칙 전체(A1~A19 · S1~S4)는 `scripts/claude_check.py` 머리말
- 정의에 임계 · 개수 · 판본 번호를 적지 않는다 — 정본(규약 문서 · 원장 · 편제표)을 가리킨다

## 새 에이전트를 만들 때
`agent-creator` 를 부르거나 직접 — 만들기 전 세 가지를 확인한다. ① 같은 일이 두 번 이상 다른 명령에서 나왔는가(쓸 곳이 하나면 프롬프트다) ② 기존 정의의 description 을 조금 넓히면 되는가 ③ 그 에이전트를 부를 명령 · 스킬의 자리(단계 번호)가 있는가. 셋 중 하나라도 아니면 만들지 않는다. 만들면 폴더를 고르고, 부르는 명령 · 스킬 문서에도 이름을 넣고(안 부르면 A11 경고), 위 '상황 → 에이전트' 표에 한 줄, `--write` 뒤 `--check` 를 통과시킨다. 절차는 nova-subagent-creator 스킬을 따르고, 겹침 판정 · 초안이 필요하면 `agent-creator` 에이전트를 부른다.
