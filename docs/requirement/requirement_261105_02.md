# REQ-261105-02 · 교훈 원장을 JSONL 원천 + MD 보기로 바꾸고 승급 흐름을 soul-review 에 잇기

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-05 |
| 요청자 | jongyeolhan |
| 원문 | "F:\project-nuri\Nova-dev\docs\memo\lessons.md에 대한 결과는 어디에 있나요 이것은 md파일형식과 jsonl형식으로 만들어서 관리하는것이 더 좋은것아닌가요 판단을 정확 하고 알려주세요" → Claude 판단(JSONL 원천 + MD 생성 보기, soul-review 연결) 뒤 "진행해주세요" |
| 입력 자료 | `docs/memo/lessons.md` · `scripts/lessons.py` · `scripts/soul_review.py` · `.claude/commands/learn.md` · `soul-review.md` · [ADR-004](../adr/ADR-004-ledger-formats.md) |
| 크기 | 작은 변경 (superpowers.md §4) |
| 상태 | 승인됨 — tasks_REQ_04 뒤에 착수 |
| 계획 | (tasks_REQ_04 끝난 뒤 `/plan-new`) |
| 원천 | 사용자 원문(위) — `docs/memo/lessons.md` 결과 위치 질문 → Claude 판단 → "진행해주세요" |
| 연결 | 근거 [ADR-004](../adr/ADR-004-ledger-formats.md)(기록 형식) · 관련 [REQ-261105-01](requirement_261105_01.md) · [REQ-261105-03](requirement_261105_03.md)(형식 규칙) · 선행 [tasks_REQ_04](../plans/tasks/tasks_REQ_04.md) · 하위 계획 없음(착수 전) |

## 의도 (INTENT — 해법을 적기 전에)
| 칸 | 내용 |
|---|---|
| 문제 | 교훈이 쌓이기만 하고 어디로도 흐르지 않는다. '(승급 후보)'가 붙어도 `/soul-review` · `soul_review.py` 가 교훈 원장을 읽지 않아 규칙 · 게이트로 옮겨지지 않는다(2026-11-05 '짧은 알림 영어' 교훈은 원장이 아니라 별도 요구 REQ-261105-01 로 풀림). 또 원장이 MD 이고 스크립트가 MD 를 정규식으로 다시 읽어 ADR-004("MD 를 기계 입력으로 쓰지 않는다")를 어긴다. 손으로 덧붙이면 형식이 깨질 수 있다 |
| 결과 | 교훈마다 상태(열림 · 승급됨 · 폐기)와 승급 위치가 기계로 셀 수 있게 남고, `/soul-review` 가 승급 후보를 제안으로 올린다. 사람은 생성된 MD 보기로 읽는다 |
| 영향 | `scripts/lessons.py` · `scripts/soul_review.py` · `docs/memo/lessons.md`(→ 생성물) · 새 `docs/memo/lessons.jsonl` · 명령 `/learn` · `/soul-review` · `/session-start` · `/debug` · lint · 복제본(new-project 가 비워서 물려줌) |
| 제약 | 원천은 추가 전용(지난 줄 수정 금지 — 상태 변경도 새 줄로). MD 는 생성물(손수정 금지, lint `--check`). 기존 10줄을 잃지 않고 옮긴다. 승급 판단은 사람(soul-review 는 제안만). 명령 절차가 바뀌므로 이 요구가 그 근거 |
| 미해결 | 없음 |

## 목적과 이유
같은 실수를 막으려고 만든 원장이 실제 규칙 · 게이트로 이어지지 않으면 기록 비용만 든다. 형식을 ADR-004 와 맞추고 흐름을 닫는다.

## 종료 조건 (exit)
| ID | 확인 | 기대 | 방식 | 판정 |
|---|---|---|---|---|
| E1 | python nova.py test | 통과 | 명령 | |
| E2 | python nova.py lint | 통과(lessons MD 보기 최신 검사 포함) | 명령 | |
| E3 | python nova.py learn check | 기존 교훈 전부 JSONL 로 옮겨짐 · 형식 정상 | 명령 | |

## 목표 · 비목표 · 반목표
| 구분 | 내용 |
|---|---|
| 목표 | JSONL 원천(추가 전용) + MD 생성 보기 · `learn add / promote / retire / find / check / render` · soul-review 가 열린 승급 후보를 제안에 싣기 |
| 비목표 | 교훈을 자동으로 SOUL · STYLE · CLAUDE.md 에 반영하기(사람 승인 몫) · 교훈 내용의 재검토 · 기존 교훈을 소급해 규칙으로 승급하기 · 이 작업 중 새로 보인 개선(다음 판본 후보로만 적는다) |
| 반목표 | MD 를 손으로 고쳐도 lint 가 못 잡는 것 · 기존 교훈이 사라지는 것 · **개선이 개선을 낳는 고리**(교훈 원장 → 결함 발견 → 리뷰 → 또 개선)로 본 개발 task 가 밀리는 것 |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| 무한 개선을 어떻게 막나(사용자 2026-11-05 "lessons.md 결과를 반영해서 만든것이 또 다른 결함을 찾고 또 리뷰를하면서 계속 무한개선으로 진행해서 원래 목적인 본 개발 작업이 방해되고 개발시간만 소모되지 않게하는것도 고려해주세요") | ① 시간 상자 2시간 — 넘으면 멈추고 남은 것은 다음 판본 ② 종료 조건 E1~E3 녹색이면 끝, 이 작업 중 보인 것은 고치지 않고 적기만 ③ 별도 코드 리뷰 · 심층 감사를 돌리지 않는다(관문 check 로 충분) ④ 착수는 본 개발 요구(REQ-261104-12)가 끝난 뒤 |
| MD 와 JSONL 중 무엇으로 관리하나 | JSONL 원천 + MD 생성 보기(Claude 판단 · 사용자 "진행해주세요" 2026-11-05) |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261105-02-1 | 교훈 원천을 `docs/memo/lessons.jsonl` 추가 전용으로 | 기존 10줄 이전 · 상태 변경은 새 줄 · 테스트 | |
| REQ-261105-02-2 | `lessons.md` 를 JSONL 에서 생성 | 손수정 시 lint 실패 | |
| REQ-261105-02-3 | 승급 · 폐기 명령 | `learn promote <ID> --to <위치>` · `learn retire <ID> --reason` | |
| REQ-261105-02-4 | soul-review 가 열린 승급 후보를 읽는다 | `soul_review.py` 출력에 후보가 나온다 · 테스트 | |
| REQ-261105-02-5 | 명령 문서 정합 | `/learn` · `/soul-review` · `/session-start` · `/debug` 가 새 경로를 가리킨다 · claude_check 통과 | |

## 방법 — 고객이 정한 것 / 맡긴 것 / Claude 판단
| 항목 | 정한 사람 | 내용 |
|---|---|---|
| 형식 | Claude 판단(사용자 진행) | ADR-004 표에 '교훈 — JSONL 이력 + MD 보기' 행을 더한다 |

## 미결 질문
| 질문 | 누구 몫 | 답 |
|---|---|---|

## 추가 요청 (같은 날)
| 원문 | 반영 |
|---|---|

## 적용 · 결과
