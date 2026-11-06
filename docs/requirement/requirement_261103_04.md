# REQ-261103-04 · project-start-guide-05 registry 대장 · docs/std 표준 채택

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-03 |
| 요청자 | jongyeolhan |
| 원문 | "위의 작업을 마치고 나서 F:\project-nuri\project-start-guide-05\registry에 있는 것들을 가지고 와서 우리 시스템에 맞게 사용하도록 해주세요 각 md파일로 하는것이 좋은지 json이 좋은지 jsonl을 사용하는것이 좋은지 판단해서 만들어서 우리도 규칙에 넣어서 사용하도록 해주세요 F:\project-nuri\project-start-guide-05\docs\std 도 채택을 해서 우리의 도메인별사용을 할 수 있도록 우리 시스템에 맞게 만들어주세요" |
| 입력 자료 | `project-start-guide-05/registry/{registry,screens,db-dictionary,permissions,events}.md` · `docs/std/{README,STD-TENANCY-001,STD-DOMAIN-PACK-001,STD-AX-001}.md` |
| 상태 | 완료 |
| 계획 | [plan_REQ_01](../plans/plan_REQ_01.md) 9단계 · [master_plan v1.1](../plans/master_plan.md) |

## 원본 분석 (착수 전)
| 원본 | 내용 | Nova 판단 |
|---|---|---|
| `registry/screens.md` | 화면ID `SCR-{모듈}-{3자리}` ↔ 라우트 ↔ 사용 API ↔ 사용 테이블 ↔ 상태(기획 · 설계 · 개발 · 완료) | 채택 — 화면이 선언하고(코드 안 메타) 도구가 읽어 파생 |
| `registry/db-dictionary.md` | 1행 = 1컬럼 평면 사전(테이블 · 컬럼 · 타입 · 의미 · 소유 도메인 · 상태) | 채택 — SQLAlchemy 모델에서 자동 파생(손으로 쓰지 않음) |
| `registry/permissions.md` | 권한키 `md.{domain}.{action}` · 역할 정본(UPPER_SNAKE) | 채택 — 역할은 손 선언, 권한키는 서비스 · 게이트웨이 권한 모듈에서 파생 |
| `registry/events.md` | 이벤트 `{domain}.{entity}.{과거형}` · 발행 · 구독 · 페이로드 | 채택 — 토픽 카탈로그 + `emit` · `@svc.on` 스캔으로 발행/구독 자동 |
| `registry/registry.md` | 5대 원칙(파생물 손편집 금지 · 실물이 이긴다 · 재입력 금지 · operationId 참조 · 0행 0통과) · 파서 계약 | 원칙 채택, **MD 표 파서 계약은 버림**(열 순서에 기대는 파서는 깨지기 쉽다 → 원천은 JSON/코드) |
| `docs/std/STD-TENANCY-001` | 멀티테넌시 5조 · 격리 모델 M1~M3 · SaaS 코어 체크리스트 | 채택 — `nova_common` 테넌트 컨텍스트 전파 지원 + 판정 의무 |
| `docs/std/STD-DOMAIN-PACK-001` | 코어 · 도메인 팩 분리, 가변점 5종, 금지 3조 | 채택 — **도메인별 사용**의 구조(`packs/<도메인>/`) + 포트 레지스트리 |
| `docs/std/STD-AX-001` | AI 자동화 등급 L0~L3 · 승인함 불변식 · 감사 분리 | 채택 — 기능별 등급 선언 + 감사 `actor_type` |
| `docs/std/README` | 선언형 표준 · 면제도 기록 · `STD-{주제}-{3자리}` | 채택 — 판정은 `nova.project.json` `standards` 에 기록, lint 가 "판정 없음"만 검사 |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261103-04-1 | 대장 형식(md · json · jsonl) 판단 | 대장별 형식과 이유가 ADR 로 남는다 | T01-9.01 |
| REQ-261103-04-2 | 화면 · DB 사전 · 권한 · 이벤트 대장을 Nova 원장에 통합 | `registry.py` 가 4대장을 파생하고 `check` 가 드리프트를 막는다 | T01-9.02~9.06 |
| REQ-261103-04-3 | 대장 사용을 규칙으로 | CLAUDE.md · 계획서 §0 · §8 · plan-new 명령에 대장 조회 · 갱신 절차 | T01-9.07 |
| REQ-261103-04-4 | std 3종 채택 · Nova 에 맞게 | `docs/std/` 에 Nova 경로 · 도구 기준으로 다시 쓴 표준 + 판정 기록 · 검사 | T01-9.08~9.09 |
| REQ-261103-04-5 | 도메인별 사용 | 도메인 팩 골격(`packs/<도메인>/`) · 포트 레지스트리 · 팩 생성 스크립트, 테넌트 컨텍스트 전파 | T01-9.10~9.12 |

## 적용 · 결과
| ID | 결과 |
|---|---|
| REQ-261103-04-1 | ✅ [ADR-004](../adr/ADR-004-ledger-formats.md) — 이력 JSONL · 선언/상태 JSON · 보기 MD |
| REQ-261103-04-2 | ✅ `scripts/ledgers.py` — 화면 · DB 사전 · 권한 · 이벤트를 코드에서 파생, 정합 검사 lint |
| REQ-261103-04-3 | ✅ CLAUDE.md · 계획 템플릿 §0 · §8 · plan-new · history-new |
| REQ-261103-04-4 | ✅ `docs/std/` 3종 + README(도메인별 사용), 판정 의무 lint |
| REQ-261103-04-5 | ✅ `nova_common.context`(테넌트 · 행위자 전파) · `nova_common.packs` + `packs/` · `nova.py new-pack` — 가변점 ②④⑤ 는 규약까지(🗺) |

검증: [history_261104_03](../history/history_261104_03.md)
