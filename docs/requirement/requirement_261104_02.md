# REQ-261104-02 · 자료 창고 입고 분석 → 부족분 인터뷰 → PRD · foundation · SPEC

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-04 |
| 요청자 | jongyeolhan |
| 원문 | "F:\project-nuri\Nova-dev\docs\warehouse\inbound에 에  프로그램 개발에 필요한 인룻 이나 재료들을 넣으면 이것을 심층 분석을 해서 고객의 요구사항과 필요한 것들을 충분히 파악을 위해 사용을 하고 여기에 있는 디렉토리와 동일한 형태의 디텍토리를 F:\project-nuri\Nova-dev\docs\warehouse\outbound에 만들어서 여기에서 출력결과물을 각각의 디렉토리의 성격에 맞게 넣어주세요 그리고 F:\project-nuri\Nova-dev\docs\warehouse\inbound에서 고객에 요구사항 분석에 필요한것중 부족한것을 다시 superpowers를 이용해서 인터뷰를 해서 최종 prd.md(prd.json)를 만들고 /foundation 커맨드 — 언어/프레임워크·아키텍처 스타일·DB·횡단관심사 채택 매트릭스 4단계 질의를 통해(F:\project-nuri\project-start-guide-05\.claude\commands\foundation.md에 있는것을 우리시스템에 맞게 구성) spec.md(spec.json)등을 만들어서 이것을 통해서 구체화할 수 있도록 해주세요" |
| 원문 주 | 원문의 `/foundation` 에는 psg05 기준 상대 링크 `../../commands/foundation.md` 가 붙어 있었다 — Nova 에서는 `.claude/commands/foundation.md` |
| 입력 자료 | 사용자가 만든 `docs/warehouse/inbound/` 하위 8개 폴더(checklist · claude-code-handoff · db-sql · etc · html-mockup · prd · screenshot · spec) · project-start-guide-05 `.claude/commands/{foundation,spec,interview}.md` · `docs/warehouse/**/README.md` |
| 크기 | 프로젝트(규칙 · 명령 · 도구 · 테스트) — 제품 코드 변경 없음 |
| 상태 | 적용됨(상시 규칙) |
| 계획 | [product README](../product/README.md) · [ADR-006](../adr/ADR-006-product-canonical-json.md) |

## 목적과 이유
받은 자료를 깊게 분석하고, 부족한 것만 고객에게 물어 최종 PRD 를 만든다. 기반(기술 · 구조) 결정과 SPEC 까지 이어서 바로 계획 · 구현으로 구체화할 수 있게 한다.

## 목표 · 비목표 · 반목표
| 구분 | 내용 |
|---|---|
| 목표 | 입고 8분류 ↔ 출고 8분류 대칭. 분석 → 부족 항목 → 인터뷰 → PRD → foundation → SPEC → 계획이 명령 · 정본 · 검사로 이어진다 |
| 비목표 | psg05 의 체크리스트 폼(html) · 버스 · 병렬 게이트 같은 고유 장치를 옮기는 것 |
| 반목표 | 정본이 둘(md 와 json 을 각각 손으로), 자료에 이미 있는 것을 고객에게 다시 묻는 인터뷰, 받은 DDL 을 그대로 실행 |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| prd.md 와 prd.json 중 정본 | Claude 판단 — JSON 정본, md · html 은 생성(ADR-004 원칙 · ADR-006) |
| foundation 질의 내용 | Claude 판단 — Nova 기본 스택 · 자산이 있으므로 "기본을 쓸지, 어디서 벗어날지"를 묻는다. 표준 3종 판정은 4단계 안에서(정본 `nova.project.json`) |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261104-02-1 | 입고 자료 심층 분석 | `/intake` 명령. `warehouse.py scan` 이 새로 · 바뀜 · 사라짐을 지문(sha256)으로 잡는다. 파일마다 요약 · 발견(E-*, PRD 영역 12 · 종류 · 원문 인용)을 `intake.json` 에 남긴다(테스트 `test_scan_tracks_new_changed_removed`) | `/intake` |
| REQ-261104-02-2 | outbound 에 같은 구조 · 분류별 결과물 | outbound 8폴더 + README. 분류마다 정해진 결과물을 둔다: prd/spec md · html · json, checklist 질문표 · 인수 점검표, db-sql DDL · 되돌림, 분류별 분석, etc 전체 보고. 대칭 · 드리프트를 lint 로 검사(`test_full_flow_out_and_drift` · `test_symmetry`) | [warehouse README](../warehouse/README.md) |
| REQ-261104-02-3 | 부족한 것을 Superpowers 인터뷰로 | `warehouse.py gaps` 가 근거 없는 영역 · 열린 부족 항목을 낸다. `/req-interview` 2-1 단계가 그것만 질문 큐로 삼고, 답은 `G-*` 에 `답함` 으로 되돌린다(`test_gaps_lists_empty_areas_and_open_items`) | `/req-interview` |
| REQ-261104-02-4 | 최종 prd.md(prd.json) | `/prd` 명령에 빌더 점검 · 승인 관문. `prd.json` 스키마 검사(수용 기준 · 근거 · 사용자 참조 · 승인 정보) → `prd.md` · 출고 md/html/json(`test_prd_rules`) | `/prd` |
| REQ-261104-02-5 | /foundation 4단계 질의 | 언어 · 프레임워크 / 아키텍처 · 배포 / DB / 횡단관심사 11종 [내장 채택 · 직접 구현 · 미사용] + 표준 판정. 결과는 `spec.json foundation` · ADR 3건 · `nova.project.json standards`. 판정이 빠지면 검사 실패(`test_spec_rules`) | `/foundation` |
| REQ-261104-02-6 | spec.md(spec.json) → 구체화 | `/spec` 명령: 서비스 · 데이터 모델 · API · 이벤트 · 화면 · 테스트 맵. 승인 시 모든 기능이 API 나 화면을, 모든 수용 기준이 테스트를 가진다. DDL 초안 생성. 승인 뒤 new-service · rbac · plan-new 로 넘긴다 | `/spec` |

## 방법 — 고객이 정한 것 / 맡긴 것 / Claude 판단
| 항목 | 정한 사람 | 내용 |
|---|---|---|
| 분류 8개 · 이름 | 사용자 | inbound 에 만든 폴더 그대로 |
| 정본 위치 `docs/product/` | Claude 판단 | 출고본과 정본을 나누기 위해(psg05 와 같은 원칙) |
| 횡단관심사 목록 11개 | Claude 판단 | psg05 6행을 Nova 자산 기준으로 나눔(이벤트 · 목록 · 파일 추가) |

## 미결 질문
| 질문 | 누구 몫 | 답 |
|---|---|---|
| 첫 실제 자료를 inbound 에 넣고 `/intake` 를 돌릴 시점 | 사용자 | |
