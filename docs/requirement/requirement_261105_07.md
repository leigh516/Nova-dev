# REQ-261105-07 · psg05 훅 채택 — 비밀 읽기 금지 · 되돌림 · 셸 쓰기 · SOUL 편집 · 호출 기록 · 컨텍스트 인계 · 세션 스냅샷

| 항목 | 내용 |
|---|---|
| 문서 ID | REQ-261105-07 |
| 생성 | 2026-11-05 · `docs_new.py req` |
| 위치 | `docs/requirement/requirement_261105_07.md` |
| 원천 | 사용자 요청 2026-11-05 "project-start-guide-05\.claude\settings.json를 참고해서 우리시스템 채택해서 반영할것인 있는지 신중하게 검토해주세요" → Claude 검토(A 5 · B 3 · C 채택 안 함) → "A와 B를 채택해서 구현해주세요" |
| 연결 | 기존 훅 [REQ-261105-01](requirement_261105_01.md)(`persona_guard.py`) · 교훈 원장 `docs/memo/lessons.md`(되돌림 사고 · 셸 heredoc 사고) · [review_261105_01](../reviews/review_261105_01.md) N5(호출 기록 원천 없음) · [review_261105_02](../reviews/review_261105_02.md) 축 4(명령 사용 계측 없음) |
| 요청일 | 2026-11-05 |
| 요청자 | jongyeolhan |
| 원문 | "A와 B를 채택해서 구현해주세요" |
| 입력 자료 | `F:\project-nuri\project-start-guide-05\.claude\settings.json` · 같은 저장소 `.claude/hooks/*.mjs`(읽기만) |
| 크기 | 작은 변경 |
| 상태 | 승인됨(2026-11-05) — 훅 순서 · 의미 변경 승인(IDENTITY 경계) |
| 계획 | 이 요구의 '요구사항 분해'가 task |

## 의도 (INTENT — 해법을 적기 전에)
| 칸 | 내용 |
|---|---|
| 문제 | 오늘 실제로 난 사고들(남의 미커밋 작업을 checkout 으로 되살림 · 셸 heredoc 으로 NUL · 줄바꿈이 파일에 들어감)을 규칙 문장으로만 막고 있다. 비밀 파일 읽기를 막는 장치가 없다. SOUL 편집 · 에이전트 · 명령 호출을 셀 원천이 없다. 컨텍스트가 차서 압축될 때 인계가 기억에 기댄다 |
| 결과 | 위 사고가 도구 호출 순간에 막히거나 기록되고, 호출 기록 · 세션 스냅샷이 남는다 |
| 영향 | `.claude/settings.json` 훅 배선 · `.claude/hooks/` · 모든 세션의 도구 호출 지연 · 복제본 |
| 제약 | 이벤트마다 파이썬 한 번(지연) · 고장 나면 통과(fail-open) · **막는 것은 둘(비밀 읽기 · 저장소 파일에 셸로 쓰기)뿐**, 나머지는 기록 · 경고 · 기존 훅 의미는 그대로 |
| 미해결 | 없음 |

## 목적과 이유
같은 실수를 규칙 문장이 아니라 장치가 막게 한다(교훈 2026-11-05 "더 세게 적지 말고 기계 검사를 세운다").

## 종료 조건 (exit)
| ID | 확인 | 기대 | 방식 | 판정 |
|---|---|---|---|---|
| E1 | python nova.py test | 통과 | 명령 | |
| E2 | python nova.py lint | 통과 | 명령 | |
| E3 | 이 세션에서 셸 heredoc 으로 저장소 파일에 쓰려 하면 막히고, 에이전트 호출이 기록에 한 줄 남는다 | 그렇다 | 사람 | (일부 확인 2026-11-05 — 셸 쓰기 거부 실제 동작 · `shell_writes.jsonl` 기록 확인. 에이전트 호출 기록은 배선 뒤 호출이 아직 없어 다음 세션에서 확인) |

## 목표 · 비목표 · 반목표
| 구분 | 내용 |
|---|---|
| 목표 | A: 비밀 읽기 금지 · 되돌림 경고/기록 · 셸 쓰기 거부 · SOUL 편집 기록 · 에이전트/스킬/명령 호출 기록 / B: 컨텍스트 임계 인계 권고 · 압축 직전 · 세션 종료 스냅샷 · 세션 시작 때 인계서 요약 주입 |
| 비목표 | C(rail-check · slice-hint · tdd-order-track · soul-bootstrap · 상태 줄 · stop-sync-check · `git push` 자동 허용) — 절차를 무겁게 하거나 psg05 전용 원장을 전제한다 |
| 반목표 | 모든 도구 호출이 눈에 띄게 느려지는 것 · 훅 고장이 일을 막는 것 · 거짓 거부로 정상 명령(git status · pytest)이 막히는 것 |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| 무엇을 채택하나 | A 5 · B 3 채택, C 채택 안 함(2026-11-05) |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261105-07-1 | 비밀 파일 읽기 금지 | `settings.json` `permissions.deny` — `.env` · `.env.*` · `*.key` · `*.pem` · `credentials.json` | |
| REQ-261105-07-2 | 셸로 저장소 파일 쓰기 거부 | heredoc · `>` 리다이렉트 · `python -c` 로 저장소 안 추적 파일을 쓰면 deny + 한국어 대안(Edit · Write 도구) · 저장소 밖(스크래치) · 읽기 명령은 통과 · 테스트 | |
| REQ-261105-07-3 | 되돌림 경고 · 기록 | `git checkout --` · `git restore` · `git reset --hard` 가 지금 미커밋 파일을 지우려 하면 경고 + JSONL 기록 · 테스트 | |
| REQ-261105-07-4 | SOUL 편집 기록 | SOUL 5종 Edit · Write 를 JSONL 에 기록(막지 않음) · 테스트 | |
| REQ-261105-07-5 | 호출 기록 | 에이전트(Agent · Task) · 스킬(Skill) · 사용자 슬래시 명령을 JSONL 1줄씩 · 요약 명령 · 테스트 | |
| REQ-261105-07-6 | 컨텍스트 임계 인계 권고 | UserPromptSubmit 에서 기록 크기로 사용률을 추정해 임계를 넘으면 `/session-end` 권고 주입 · 테스트 | |
| REQ-261105-07-7 | 압축 직전 · 세션 종료 스냅샷 | PreCompact · SessionEnd 에서 인계서 · 진행 중 tasks 를 백업 폴더로 복사 · 테스트 | |
| REQ-261105-07-8 | 세션 시작 인계 주입 | SessionStart 에서 `docs/session/LATEST.md` 요약을 주입(길이 상한) · 테스트 | |

## 방법 — 고객이 정한 것 / 맡긴 것 / Claude 판단
| 항목 | 정한 사람 | 내용 |
|---|---|---|
| 기록 위치 | Claude 판단 | `.claude/state/*.jsonl`(git 무시 — 기계마다 로컬 기록). 백업은 `.claude/state/backups/` |
| 구현 언어 · 묶음 | Claude 판단 | 파이썬 하나(`.claude/hooks/nova_hooks.py <이벤트>`), PreToolUse 는 기존 `persona_guard --pretool` 판정을 같은 프로세스에서 부른다 |

## 미결 질문
| 질문 | 누구 몫 | 답 |
|---|---|---|

## 추가 요청 (같은 날)
| 원문 | 반영 |
|---|---|
| (2026-11-06) "현재 세션 컨텍스트가 15%로 나오고 있는데 앞에서는 컨텍스트가 거의 차서 세션인수인계를 하라고 하였습니다 컨텍스트인수인계는 약 65% 정도일때 진행해도 되지 않나요" → 선택지 A(임계만) · B(창 크기 환경 변수) · C(statusLine 실측) 중 "c로 진행" | 원인: 분모를 200k 로 고정 — 1M 세션 120k(실제 12%)를 60% 로 권고. 해결: `nova_hooks.py statusline`(settings `statusLine`)이 Claude Code 가 주는 `context_window.context_window_size` · `used_percentage` 를 `.claude/state/context_window.json` 에 세션별로 남기고, `prompt` 가 그 창을 분모로 쓴다(없으면 추정). 원래 statusLine(사용자 전역 — Orca)은 같은 입력으로 이어 부른다. 임계 기본 60 → 65. 테스트 7개(`tests/test_nova_hooks.py` 실제 창 절) · 실세션 기록 확인(창 1,000,000 · 19%) |

## 적용 · 결과
- 2026-11-05 `nova_hooks.py`(이벤트 6 + usage) · settings 배선 · `permissions.deny` · `.claude/state/` 무시 · `tests/test_nova_hooks.py` 101 통과(담당 보고) · 셸 쓰기 거부 실제 동작(main 이 직접 확인 — 리다이렉트 · `cat >>` 둘 다 거부)
- 2026-11-06 컨텍스트 창 크기 판단 해소 — statusLine 실측 분모 · 임계 65%(추가 요청 표)
- 남은 판단(다음 세션): 되돌림을 경고 대신 사람 확인(ask)으로 바꿀지 · 경고 출력 키(additionalContext)가 스키마에서 받아지는지
