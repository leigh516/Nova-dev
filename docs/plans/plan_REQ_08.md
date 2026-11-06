# plan_REQ_08 · 계획 자동 진행 — main 운전자 · 병렬 배치 · 재개 · 안전장치 v1.0

**대상 시스템** Nova 작업 체계 — `/task-run` · `/sdd` · `/session-start` 명령 · 에이전트 규약(`.claude/agents/README.md` · `docs/conventions/agents.md`) · 작은 판정 스크립트(`scripts/task_batch.py`)
**변경점** `/task-run --auto` — main 이 겹치지 않는 task 를 한 층 병렬로 배치 · 검토 · 확인 · 체크하며 끝까지 가고, 사람 판단 자리에서만 모아서 묻고, 상한에 걸리면 멈추고, 끊겨도 이어 간다

> **한 줄 요약** — 현장 감독(main)이 작업자(에이전트)들에게 겹치지 않는 일을 동시에 나눠 주고, 검수하고, 결재가 필요한 것만 모아서 사장(사용자)에게 올린다.

| 항목 | 값 |
|---|---|
| 버전 | **v1.0** · 기준 마스터플랜 v1.3 |
| 요구 | [REQ-261105-09](../requirement/requirement_261105_09.md) |
| task | [tasks/tasks_REQ_08.md](tasks/tasks_REQ_08.md) — 진행 상황의 정본 |
| 원칙 | 단계마다 전체 테스트 녹색 · 생성물 원장 sync · 문서 기록 |
| 실행 방식 | (사용자 선택) subagent — superpowers:subagent-driven-development / native — superpowers:executing-plans ([superpowers.md §5](../conventions/superpowers.md)) |
| 문서 ID | plan_REQ_08 |
| 생성 | 2026-11-05 · `docs_new.py plan` |
| 위치 | `docs/plans/plan_REQ_08.md` |
| 원천 | [REQ-261105-09](../requirement/requirement_261105_09.md)(사용자 2026-11-05 자동화 · 병렬 질문 4건) · 자문 `.claude/state/reports/req09-advice.md` · 본문 초안 task-planner(`.claude/state/reports/plan08-draft.md`) |
| 연결 | 선행 [REQ-261105-08](../requirement/requirement_261105_08.md) · 가이드 [agents.md](../conventions/agents.md) · [superpowers.md](../conventions/superpowers.md) · 규칙 [plans README](README.md) · task [tasks_REQ_08](tasks/tasks_REQ_08.md) |

> **진척 (2026-11-05, tasks 기준)** — 0 / 0

## 0. 영향분석 (착수 전 조회)
```
1) 대상: 위 대상 시스템
2) 직접 영향: /task-run 절차(--auto 추가) · /sdd 의 task-run 연결 · /session-start 알림 · 에이전트 부르는 규칙 · 에이전트 운영 가이드 · 크기 판정 가이드
3) 간접 영향: /task-run 을 부르는 명령(/sdd · /dispatch · /orchestrate — 인자가 없으면 지금과 같아 의미 변경 없음) · claude_check lint(명령 문서 한국어 · 도구 경계) · docs_index lint
4) 등급: 보통~큼 - 명령 절차를 바꾼다(IDENTITY 경계: 명령 의미는 승인 없이 못 바꿈 → 요구 REQ-261105-09 승인이 근거). 기존 호출은 인자가 없으면 그대로라 되돌리기 쉽다. 권한 설정(settings.json)은 건드리지 않는다
5) 갱신 산출물: 명령 문서 3 · 에이전트 README(편제표는 생성물 - 손대지 않음) · agents.md · superpowers.md. 생성물 없음(gen 불필요)
6) 대장 조회: 새 표 · 새 API · 새 토픽 · 새 화면 · 새 권한 모두 없음 → 대장 4종 영향 없음
7) 표준 판정: 테넌시 해당 없음 · 도메인 팩 해당 없음 · AX 자동화 등급 - 무인 진행이 푸시 · 태그 · 의존성 · 권한 확대를 못 하게 막는 것이 핵심(AX 해당, 사람 관문 유지)
8) 훅: .claude/settings.json 훅 · 권한 변경 없음(허용 목록은 제안 문서까지, 적용은 별도 승인). 4단계 테스트가 settings.json 에 접두 일괄 허용이 없는지 지킨다
```
- 실측: `docs/conventions/agents.md` 와 에이전트 README 의 부르는 규칙 9(REQ-261105-08)는 브랜치 `feat/req-agent-ops` 에만 있다(현재 브랜치 `feat/plan_REQ_04-cookie` 에는 없음) → **1단계 첫 task 가 병합 여부를 확인**하고, 병합 전에는 4단계를 시작하지 않는다
- 실측: `scripts/` 를 설명하는 README 는 없다(`quick_check` · `progress.py` 를 README 에서 찾아 0건) → 새 스크립트의 사용 설명은 `task-run.md` 한 곳에 두고 `nova.py` 에는 연결하지 않는다(`docs_new.py` · `git_record.py` 처럼 `uv run python scripts/…`)
- 실측 못 한 것: `python nova.py impact` 는 120초 안에 끝나지 않아 중단(이 PC 의 `.pytest_tmp` 가 커서 저장소 전체 검색이 느림) — 영향은 Grep 으로 대신 조회했다. `exit-check REQ-261105-09 --dry` 는 요구 문서가 아직 저장소에 없어 못 돌림 → 요구의 종료 조건 표(E1~E5)와 눈으로 대조(아래 §11.3)

## 1. 설계의 중심축
> **핵심 인사이트** — 새 명령도 새 에이전트도 필요 없다. `/task-run` 에 이미 있는 것(경로 → 구현자 표 · 단계 관문 · 멈춤 조건 · 독립 task 병렬)을 `--auto` 한 가지로 묶고, **빠진 두 가지(겹침 판정 · 재개 목록)만 기계가 계산**하게 한다. 나머지는 문장 규칙이다.

```
tasks 읽기 → 열린 task 중 선행이 끝난 것 → 겹침 판정(scripts/task_batch.py)
  → 겹치지 않는 묶음을 한 메시지로 동시에 구현자 호출(main 한 층)
  → task 마다 새 검토자 → main 이 quick 재실행 → 체크
  → 단계 끝이면 단계 관문(전체 check)
  → 멈춤 조건이면 질문을 모아 한 번에 묻고, 기다리는 동안 독립 task 는 계속
```

## 2. 모델 변경
해당 없음 — 표 · 개체 · 이벤트를 만들지 않는다(명령 절차 · 규약 문서 · 작은 판정 스크립트).

## 3. 선행 관계
- 선행: REQ-261105-08(보고서 파일 규칙 · 모델 등급 · 호출 원장 · agents.md) — main 병합 완료 2026-11-05(daf0ce1)
- 이 계획 안: 1단계(판정 부품) → 2단계(task-run 절차) → 3 · 4단계(연결 · 규약) → 5단계(견본 시험)

## 4. 표면 (화면 · API)
해당 없음 — 화면 · API · 표 · 권한이 없다. 명령 절차 · 규약 문서 · 작은 스크립트 하나만 바뀐다(§4.1 UX 점검도 해당 없음).

## 5. 생애주기
해당 없음 — 상태를 가진 개체가 없다. 자동 진행의 진행 상태는 tasks 체크 · git 기록(정본)과 `.superpowers/sdd/` 원장(보조)으로 본다(§1).

## 6. 핵심 분기
| 실패 지점 | 동작 | 이유 |
|---|---|---|
| task 가 건드릴 경로를 판정할 수 없다(경로 표기 없음) | 그 task 는 혼자 한 묶음으로 둔다(겹침 가능성을 가정) | 모르면 차례로 — 같은 파일 동시 수정이 반목표 |
| 앞 task 가 실패한 채 독립 task 만 남음 | 독립 task 는 계속하되, 연속 실패 상한에 걸리면 모두 멈춘다 | 비용 폭주 차단. 앞 결과에 기대는지는 선행 표기로만 안다 |
| 고치기 상한 초과 | 멈추고 BASE · 되돌리는 명령 · 마지막 실패 내용을 보고 | 무인 고치기 고리 차단 |
| 세션이 끊김 | 새 세션에서 같은 명령 → tasks 의 체크된 task 를 건너뛰고 다음 묶음 | 정본은 체크 + git 기록, 원장은 보조(git 무시) |
| 원장(`.superpowers/sdd`)이 없는 PC | 체크된 task 만으로 이어 가고 BASE 는 `git log` 로 찾는다 | 원장이 그 PC 에만 있다 |
| 푸시 · 태그 · 의존성 · 권한 확대가 필요 | 자동으로 하지 않고 질문 모음에 올린다 | 사람 관문(요구 제약) |

## 7. 데이터 모델
해당 없음 — DB 표 · 칸을 만들지 않는다.

## 8. 재사용
- `/task-run` 의 멈춤 조건(7-1) · 경로 → 구현자 표(2-1) · 단계 관문(5-0)을 그대로 쓴다 — 새 명령을 만들지 않는다
- superpowers subagent-driven-development 의 원장 · 검토 고리 · 고치기 상한(5회)
- REQ-261105-08 의 보고서 파일 규칙(부르는 규칙 9) · 모델 등급 표

## 9. 범위 밖 (요구 비목표 그대로)
| 안 하는 것 | 이유 · 어디서 |
|---|---|
| 새 `/autorun` 명령 | `/task-run --auto` 로 확장(자문 C-1) |
| 오케스트라 하위 에이전트 · 다층 에이전트 호출 · 에이전트끼리 직접 통신 | 총괄은 main 한 층. 단일 기록자 · 판단 요청은 main 만 가능 |
| 계획 · task 작성 자동화(`/plan-new` 까지 이어 가기) | 승인 관문(요구 · 계획 승인) — 자문 A-3 |
| 계획에서 다음 계획으로 자동 이동 | 이번은 한 계획 · 다음 판본 후보 |
| 사람 관문 자동 통과 · 원격 푸시 자동화 | 요구 제약 · SOUL 되돌림 원칙 |
| `.claude/settings.json` 허용 목록 실제 적용 | 권한 확대 — 제안 문서까지, 적용은 따로 승인([DEEP]) |
| 실행 환경 자동화(stack) · 생성물 연쇄 안내 · worktree 실행 준비 · Workflow 도구 시험 | 원문 밖 — 별도 요구 후보(한 세대 규칙) |
| 상한 값을 설정 파일 · 환경 변수로 빼기 | 값은 task-run 문서 한 곳에만 둔다 |

## 10. 테스트 맵
| 단계 | 코드 경로 | 테스트 | slow | 수용 기준 |
|---|---|---|---|---|
| 1 | `scripts/task_batch.py` | `tests/test_task_batch.py` | 아니오 | 09-2 · 09-3 |
| 2 | `.claude/commands/task-run.md` | `claude_check`(lint 단계) | 아니오 | 09-1 · 09-2 · 09-3 · 09-4 · 09-5 |
| 3 | `.claude/commands/sdd.md` · `session-start.md` | `claude_check` | 아니오 | 09-3 |
| 4 | `.claude/agents/README.md` · `docs/conventions/agents.md` · `superpowers.md` | `tests/test_task_batch.py::test_limits_single_source` · `test_settings_has_no_blanket_allow` · `claude_check` · `docs_index` | 아니오 | 09-4 · 09-5 · 09-6 · 09-7 |
| 5 | `tests/fixtures/auto_trial/` | `tests/test_task_batch.py` 의 견본 시험 + 사람 시험(E3~E5) | **사람 시험은 slow** — 구현자 · 검토자 8회 이상 호출, 시작 전 크기를 말하고 확인 | E3 · E4 · E5 |

## 11. 후속 · 예외
### 11.1 전역 제약
| 제약 | 값 · 출처 |
|---|---|
| 언어 | 한국어(CLAUDE.md 규칙 0) |
| 총괄 | main 이 병렬 에이전트를 **한 층**으로 직접 부른다 — 에이전트가 다른 에이전트를 부르지 않는다(Claude Code 는 기본 3층까지 허용하지만 Nova 는 정의 `tools` 에 Agent 를 넣지 않아 일부러 막는다 · 사용자 질문 도구는 하위 에이전트에서 늘 빠진다) |
| 사람 관문 | 요구 승인 · 계획 승인 · [DEEP] · 푸시 · 태그 · 의존성 · 권한 확대는 자동으로 넘지 않는다 |
| 기존 명령 의미 | 확장만 — `--auto` 가 없으면 `/task-run` 은 지금과 같다 · 훅 의미 유지 |
| 병렬 조건 | 겹침 없는 묶음만 동시에(같은 작업 트리 · 파일 분리). 같은 파일을 두 구현자가 동시에 고치지 않는다 |
| 단일 기록자 | 번호 기록 · 원장 · 커밋 · 푸시는 main 만. 구현 에이전트에게 전체 `test` · `check` 를 시키지 않는다 |
| 관문 중 부하 | 전체 `check` 가 도는 동안에는 구현자 · 무거운 배경 작업을 새로 띄우지 않는다(읽기 전용 검토 · 자문 하나까지) — 2026-11-05 배경 에이전트와 겹쳐 저장소 테스트가 30분 제한에 끊기고 migrate 하위 프로세스가 비정상 종료한 실측 |
| 재개의 정본 | tasks 의 `- [x]` 와 git 기록. `.superpowers/sdd` 원장은 보조 |
| 상한 3종 | task 당 고치기 회차 · 회차당 호출 수 · 연속 실패 수 — **값은 task-run.md 한 곳**(초안 값은 11.4) |
| 시작 지점 | 시작 BASE 커밋을 원장 첫 줄에 적고, 멈출 때 되돌리는 명령(`git reset` 대신 브랜치 단위 — 작업은 늘 `feat/…` 브랜치)을 보고에 넣는다 |
| 무인 허용 목록 | 제안만. `python nova.py` 접두 일괄 허용 금지. 명령 + 하위명령 정확 일치. push · tag · release ship/publish · 삭제 · 의존성은 ask 유지 |
| 개선 범위 | 이 작업 중 새로 보인 것은 다음 판본(plans README §5 한 세대 규칙) |

### 11.2 검토 초점
| 입력 · 상황 | 기대 동작 | 테스트를 넣은 task |
|---|---|---|
| 두 task 가 `services/sample/` 와 `services/sample/items.py` 처럼 폴더 안팎으로 겹친다 | 같은 묶음에 넣지 않고 차례로 | T08-1.04 |
| task 에 경로가 하나도 적혀 있지 않다 | 혼자 한 묶음(겹침 가능으로 가정) | T08-1.03 |
| 뒤 task 가 `(선행: T08-1.02)` 인데 1.02 가 아직 미완 | 선행이 끝나기 전에는 배치하지 않음 | T08-1.05 |
| 세션을 끊고 같은 명령으로 이어 가는데 체크된 task 가 있다 | 체크된 · 취소된 task 는 다시 배치하지 않음 | T08-1.06 · T08-5.03 |
| 고치기가 계속 실패해 상한을 넘는다 | 멈추고 BASE · 되돌리는 명령을 보고 — 다음 task 로 안 감 | T08-2.05 · T08-5.04 |
| 누군가 접두 일괄 허용(`python nova.py` 로 시작하는 모든 명령)을 settings.json 에 넣는다 | 테스트가 실패 | T08-4.07 |
| 상한 값이 task-run 밖 문서에 따로 적힌다 | 테스트가 실패 | T08-4.06 |

### 11.3 자체 점검
| 점검 | 결과 | 비고 |
|---|---|---|
| 요구 반영 | 통과 | 09-1→2.02·2.04, 09-2→1.03~1.05·2.03, 09-3→1.06~1.07·2.06·3.02, 09-4→2.05, 09-5→2.07·4.02, 09-6→4.04·4.07, 09-7→4.01·4.03. 종료 조건 E3→5.01·5.02·5.06, E4→5.03·5.06, E5→5.04·5.06, E1·E2→단계 관문 |
| 단계 명확성 | 통과 | 단계 = 같은 파일 묶음(스크립트 / task-run / sdd·session-start / 규약 문서 / 견본). 5단계 · 30 task |
| 타입 일관성 | 통과 | 함수 이름을 1단계에서 정하고 이후 단계는 그 이름만 쓴다: `parse_tasks` · `task_paths` · `overlaps` · `next_batch` · `pending_ids` |
| 검토 초점 | 통과 | 7가지 모두 담당 task 지정 |
| 분량 | 통과 | 단계당 3~7 task, 가장 큰 task 도 반나절 이내 |
| 검사 묶음 | 확인 필요 | `uv run python scripts/quick_check.py --check-tasks` 는 main 이 파일을 만든 뒤 돌린다 |

### 11.4 초안 값 (요구에 숫자가 없어 Claude 판단 — 사용자 확인 대상)
| 상한 | 초안 값 | 근거 |
|---|---|---|
| task 당 고치기 회차 | 5 | 기존 값(agents.md §3 — 구현 고치기 5회차)을 그대로 |
| 한 번의 `--auto` 실행당 호출 수 | 20 | 한 task 가 구현자 + 검토자 2회 호출 → 한 단계 분량 |
| 연속 실패 수 | 2 | 두 task 가 연달아 실패하면 계획 문제로 보고 사람에게 |
| 동시에 띄우는 구현자 수 | 3 | 이 PC 에서 무거운 테스트가 겹치면 시간 초과가 났던 전례(agents.md §5 대가) |

## 12. 체크리스트
- [ ] 1단계 · 기계 판정 부품(`task_batch.py`)
- [ ] 2단계 · `/task-run --auto` 절차
- [ ] 3단계 · `/sdd` · `/session-start` 연결
- [ ] 4단계 · 에이전트 규약 문서 · 단일 원천 테스트
- [ ] 5단계 · 견본 계획 · 종료 조건 E3~E5 시험

### 12.1 실측으로 정정된 자리
- (착수 전) 없음

## 13. task 분해
[tasks/tasks_REQ_08.md](tasks/tasks_REQ_08.md)

---
## 변경 이력
- v1.0 · 2026-11-05 · 최초 작성(요구 REQ-261105-09 승인 뒤)

> **다시 한 줄 요약** — 반장 한 명이 일을 겹치지 않게 나눠 동시에 시키고, 사람이 정할 일만 모아 묻고, 꼬이면 멈춰서 되돌릴 자리를 알려 준다.
