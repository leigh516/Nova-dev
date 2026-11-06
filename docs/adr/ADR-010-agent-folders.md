# ADR-010 · 에이전트 폴더형 편제 — psg05 역할을 폴더로 묶어 대부분 살린다

| 항목 | 내용 |
|---|---|
| 일자 | 2026-11-04 |
| 상태 | 채택 |
| 대체 | [ADR-009](ADR-009-commands-skills-agents.md) 의 일부(에이전트 '평면 · 기능별로 합침'과 대안 표의 '42개 그대로 = 기각') |
| 요구 | [REQ-261104-13](../requirement/requirement_261104_13.md)(사용자 지시 2026-11-04: "성격이 비슷한 에이전트를 폴더로 묶어 정리 … 대부분 필요하다고 판단") |

## 배경
- ADR-009 는 psg05 에이전트 40개를 기능별로 합쳐 평면 편제로 들였다.
- 재분석해 보니 합치는 과정에서 원본 고유의 판단 기준이 빠졌다.
  - 예: 숫자를 지어내지 않는다 · 참조 0건을 영향 없음으로 읽지 않는다 · 형은 받고 값은 받지 않는다.
  - 다섯 역할을 한 정의에 담은 `implementer` 는 본문이 얇아졌다.
- 사용자는 대부분의 역할이 필요하다고 판단했다.
- Claude Code 는 `.claude/agents/` 를 하위 폴더까지 읽고 `name` 으로만 식별한다(공식 문서 · 이 세션 실측). 폴더가 달라도 이름이 같으면 하나만 실린다.

## 결정
- **폴더 여덟 개에 둔다**: research · planning · development · quality · docs · ops · meta · domain. 루트에는 README 만 둔다.
- **psg05 역할 40개를 모두 살린다.** Nova 고유 docs-auditor · ops-auditor 를 더해 핵심 편제로 한다(개수는 편제표가 정본).
  - 이름은 psg05 를 기본으로 한다.
  - 명령이 이미 부르던 `req-analyst`(← spec-analyst) · `contract-auditor`(← contract-guardian)는 Nova 이름을 유지한다.
  - `planner` 는 `task-planner` 로 되돌린다.
  - `orchestrator` 는 '설계만' 한다. 오케스트레이션은 main 하나가 한다.
- **합쳤던 정의는 다시 나눈다.**
  - synthesizer → project-manager · integrator
  - implementer → backend-developer · frontend-developer · devops-engineer · refactorer
  - ui-auditor → accessibility-auditor · design-token-guardian
  - 옛 이름은 폐지한다. 명령이 옛 이름을 부르면 lint 가 새 이름을 안내한다.
- **폴더가 정본이다.** 묶음과 읽기 전용 여부는 폴더에서 파생하고, 정의에 `> 묶음:` 줄은 쓰지 않는다.
  - research · planning · quality · domain: 읽기 전용, Bash 필수
  - ops: 기본 읽기 전용. 쓰기는 release-manager · incident-responder 만
  - development · docs · meta: 쓰기
- **도메인 팩 에이전트**는 `domain/<팩>-specialist` 다. 프로젝트 소유라 상류 받기 대상이 아니다.
- **선택 피로를 줄이는 장치 셋**
  - ① 명령 · 스킬 단계가 부를 이름을 고정한다(예: task-run 의 '경로 → 구현자' 표).
  - ② README '상황 → 에이전트' 빠른 표를 둔다(lint A19).
  - ③ description 끝에 "…는 X 몫이다" 경계 문장을 둔다.
- **쓰이는 자리가 얇은 정의**(project-starter · design-director · design-asset-keeper · design-rule-architect · agent-creator)는 두 판본 동안 부른 기록이 없으면 합친다.
- **만들고 고치는 절차**는 스킬로 둔다: nova-subagent-creator · nova-skill-creator · nova-command-creator. 겹침 판정은 `agent-creator` 가 한다.

## 검토한 대안
| 대안 | 장점 | 단점 | 버린 이유 |
|---|---|---|---|
| 평면 합친 편제 유지 | 파일이 적다 | 판단 기준 손실 · 얇은 본문 · 사용자 판단과 다름 | 사용자가 대부분의 역할이 필요하다고 판단 |
| 폴더 없이 전부 평면 | 검사기 변경이 적다 | 성격 · 도구 원칙이 이름에만 걸려 선택 피로가 커짐 | 폴더가 묶음 · 도구 원칙의 단일 원천이 된다 |
| `> 묶음:` 줄과 폴더를 함께 | 정의 안에서 묶음이 보인다 | 원천이 둘이 되어 어긋날 수 있다 | 폴더 하나에서 파생(A16 이 그 줄을 금지) |
| 프론트와 모바일을 나눔 | 모바일 전문성 | psg05 에 없음, 같은 규약(ui.md §2 대응 이름) | frontend-developer 가 KMP 를 포함 |

## 결과
- **좋아지는 것**
  - 역할마다 고유 기준이 살아 있다.
  - 폴더만 보고 도구 원칙을 안다.
  - 명령 · 스킬이 부를 이름이 단계마다 고정된다.
- **감수하는 것**
  - 정의 파일이 늘어나고, description 이 매 세션 컨텍스트를 더 차지한다.
  - 복제본은 옛 평면 파일을 한 번 정리해야 한다(`/sync-upstream` 6-1).
- **이후 규칙**
  - 새 정의는 폴더를 고르고 '상황 → 에이전트' 표에 한 줄을 더한다.
  - 정의에 개수 · 판본 번호를 적지 않는다.
  - 검사 규칙은 `scripts/claude_check.py` 머리말이 정본이다.
