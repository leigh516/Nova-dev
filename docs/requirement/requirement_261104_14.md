# REQ-261104-14 · 명명 규약 · 분야별 확장 · 개념 원장 — psg05 를 Nova 에 맞게

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-04 |
| 요청자 | jongyeolhan |
| 원문 | "…project-start-guide-05 를 분석하면 개발을 하면서 사용할 명명규약 분야별(테넌트별)명명규약과 초기 개발 후에 분야별로 확장을 할 수 있는 구조등이 있고 이와 연동된 원장관리부분등이 있습니다 이 부분울 찾아서 우리시스템에 맞게 구성 적용해서 개발에 중요한 부분으로 채택해서 관련부분과 연동성등을 파악해서 적용을 해주세요" |
| 입력 자료 | psg05 `docs/guides/NAMING.md` · `docs/rules/ENTITY_LEDGER.md` · `entity-*.mjs` · `check-naming*.mjs` — 분석 에이전트 1 · 구현 담당 D(worktree) |
| 크기 | 작은 변경 |
| 상태 | 적용됨 |
| 계획 | [docs/conventions/naming.md](../conventions/naming.md) · `registry/naming.json` · `registry/entities.json` |

## 의도 (INTENT — 해법을 적기 전에)
"누가 왜 곤란한가"를 해법보다 먼저 적는다. 이것이 이미 해법을 담고 있으면 문제 진술이 아니다. `미해결` 은 비우지 않는다(없으면 "없음") — `docs_index --check` 가 검사한다.

| 칸 | 내용 |
|---|---|
| 문제 | 여러 프로젝트를 병렬로 만드는 개발자 · 에이전트가 같은 개념을 다른 이름(dept · department · org_unit)으로 만들고, 형식 규칙이 스크립트마다 흩어져 서로 달라도 아무도 모른다 |
| 결과 | 이름은 선언 한 곳(naming.json)에서 검사되고, 새 표 · 개체를 만들기 전에 개념 원장으로 같은 것이 있는지 조회한다. 분야(도메인 팩)는 층(platform · core · pack)으로 확장된다 |
| 영향 | 대장 · 생성물 원장 · new_service · packs · impact · /plan-new · contract-auditor · new_project · 상류 받기 |
| 제약 | 저장 데이터 구조(칸 이름 · PK 타입)는 이번에 바꾸지 않고 baseline 으로 — 신규만 막는다. MD 를 기계 입력으로 쓰지 않는다(ADR-004). psg05 의 접미사표 · camelCase · 테넌트 토픽은 채택하지 않는다 |
| 미해결 | 없음 — baseline 7건은 REQ-261104-11 · 12 에서 다룬다 |

## 목적과 이유
사용자 요청(2026-11-04). 권장안을 채택해 바로 적용했다.

## 종료 조건 (exit)
이 요구가 **끝나는** 조건. 1~7개, 한 번 돌리거나 한 번 보고 답이 나오는 것만(소진형 금지). 모두 녹색이면 닫고, 새로 보인 것은 새 요구로 — `python nova.py exit-check REQ-261104-14` · [plans README §5](../plans/README.md).
| ID | 확인 | 기대 | 방식 | 판정 |
|---|---|---|---|---|
| E1 | python nova.py test | 통과 | 명령 |  |
| E2 | python nova.py lint | 통과(naming check 포함) | 명령 |  |
| E3 | python nova.py naming lookup department | 5갈래 중 하나로 답하고 종료 0 | 명령 |  |

## 목표 · 비목표 · 반목표
| 구분 | 내용 |
|---|---|
| 목표 | 명명 형식 · 개념 원장 · 분야 층을 lint 가 지키는 개발 기반으로 |
| 비목표(하지 않을 것) | 기존 저장 데이터의 이름 변경 · 접미사표 강제 |
| 반목표(돌아가도 실패인 것) | 규칙이 너무 많아 첫날부터 새 프로젝트가 빨간 것 |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| 분석 · 설계 권장안을 채택하나 | 채택(사용자 지시 2026-11-04) |

## 요구사항 분해
하위 ID 는 `REQ-261104-14-n` 형식으로 쓴다.

| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261104-14-1 | 명명 규약 문서 + 선언 정본: naming.md · naming.json(형식 17) | naming check 통과 | - |
| REQ-261104-14-2 | 개념 원장 · 조회: entities.json · lookup 5갈래 | test_naming | - |
| REQ-261104-14-3 | 정규식 단일화 · 연결: new_service · packs · 토픽 테스트가 naming.json 을 읽음, impact · plan-new · contract-auditor 연결 | test_topic_catalog · lint | - |
| REQ-261104-14-4 | 새 프로젝트 · 상류: new_project 원장 재시작 · upstream 공통부에 naming.json | test_new_project | - |

## 방법 — 고객이 정한 것 / 맡긴 것 / Claude 판단
| 항목 | 정한 사람 | 내용 |
|---|---|---|

## 미결 질문
| 질문 | 누구 몫 | 답 |
|---|---|---|

## 추가 요청 (같은 날)
| 원문 | 반영 |
|---|---|

## 적용 · 결과
