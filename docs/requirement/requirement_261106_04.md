# REQ-261106-04 · 표준 디자인 킷 — 킷 선택 · 토큰 한 벌 · 체크리스트 채택(newtype)

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-06 |
| 요청자 | jongyeolhan |
| 원문 | "첨부한 것을 심층분석해서 우리 디자인킷에서도 표준킷으로 선정하면 사용할수있도록 하고 checklist.html에. 디자인과 컴퍼넌트 부분등 필요한부분에 넣어서 표준을 선택하면 채택되도록 선택할수있도록해주세요" → 권고 1~3 "디자인킷을 권고로 구현해주세요" |
| 입력 자료 | 첨부 `assets.zip`(CSS 11 · JS 13 · HTML 2 · sha256 4e0406bc…) — 저장소 밖 보관 · 2026-11-06 design-asset-keeper 판정 |
| 크기 | 작은 변경 (superpowers.md §4) |
| 상태 | 진행 중 |
| 계획 | (이 문서 분해표로 직행) |
| 문서 ID | REQ-261106-04 |
| 생성 | 2026-11-06 · `docs_new.py req` |
| 위치 | `docs/requirement/requirement_261106_04.md` |
| 원천 | 2026-11-06 세션 사용자 원문 · 첨부 킷 · 판정 보고 |
| 연결 | 결정 [ADR-016](../adr/ADR-016-nicomms-g1.md) · 디자인 시스템 [README](../design-system/README.md) · 규약 [ui.md](../conventions/ui.md) |

## 의도 (INTENT — 해법을 적기 전에)
| 칸 | 내용 |
|---|---|
| 문제 | 고객이 쓰고 싶은 디자인 킷이 있어도 Nova 는 브랜드 한 벌(`brand.tokens.json`)만 받아, 킷을 고르는 길이 없고 체크리스트에서 골라도 채택되지 않는다 |
| 결과 | 체크리스트에서 표준 킷을 고르면 기록되고, `/foundation` 승인 뒤 `kit use` 한 번으로 토큰(웹 tokens.css · 모바일 DesignTokens.kt)이 그 킷이 된다 — 대비 검사를 통과한 킷만 |
| 영향 | `design/tokens/` · `scripts/gen_tokens.py` · `nova.project.json` · `scripts/checklist*` · `/foundation` · 디자인 시스템 문서 · nicomms G1 |
| 제약 | 원본 CSS/JS 는 들이지 않는다(jQuery · CDN · 접근성 결함) — 토큰 값만 · 의미 토큰 규칙 그대로 · WCAG AA 자동 검사 · 기본 킷은 nova(바꾸지 않으면 지금과 같은 생성물) |
| 미해결 | 없음 |

## 목적과 이유
킷이 토큰 한 벌이면 화면 코드를 바꾸지 않고 프로젝트마다 다른 모습을 고를 수 있고, 대비 검사 · 다크 · 모바일이 그대로 따라온다.

## 종료 조건 (exit)
| ID | 확인 | 기대 | 방식 | 판정 |
|---|---|---|---|---|
| E1 | python nova.py test | 통과 | 명령 | |
| E2 | python nova.py lint | 통과 | 명령 | |
| E3 | `python nova.py kit use newtype` → tokens.css 가 newtype 값 · 대비 검사 통과 → `kit use nova` 로 원래 생성물과 같아짐 | 테스트 통과 | 명령 | |
| E4 | checklist.html 디자인 섹션에서 킷을 고르면 미리보기가 바뀌고 저장 · import 뒤 킷 결정 · 갭이 나옴 | checklist-smoke 통과 | 명령 | |

## 목표 · 비목표 · 반목표
| 구분 | 내용 |
|---|---|
| 목표 | 킷 목록 · newtype 토큰 · 킷 합치기 · `kit` 명령 · 체크리스트 질문 · 미리보기 · import 반영 · 문서 |
| 비목표(하지 않을 것) | 킷 원본 CSS/JS 이식 · 새 부품 구현(Tooltip · PeriodSearch 등 — 🗺 등재만) · Glendale 킷(AA 미달) |
| 반목표(돌아가도 실패인 것) | 기본 킷 nova 의 생성물이 바뀌는 것 · 대비 미달 킷이 선택되는 것 |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| 들이는 방식 | 안 A — 킷 = 토큰 한 벌 + 부품 갭 목록 |
| 값 | newtype hex 를 그대로 옮기되 토큰 파일로만 · 대비 미달(경계선 line-2 1.53)은 조정 · nicomms '원본 값 금지'는 킷 경로만 예외 |
| 결정 기록 | 킷 축 ADR(nicomms G1 해소) |
| 채택 시점 | (처음 권고: 체크리스트는 기록 · 변경은 `/foundation` 뒤) → 사용자 수정 "3의 채택시점은 체크리스트에서 설정하고 .foundation kit use에서 확인하고 다시 설정을 할 수 있도록 해주세요 그래야 파운데이션에서 놓치는것을 방지합니다" — 체크리스트 import 가 설정(출처 기록) · `/foundation` 5단계가 `kit show` 로 확인하고 필요하면 `kit use` 로 다시 설정(건너뛰지 않는 관문) |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261106-04-1 | `design/tokens/kits/catalog.json` · `newtype.tokens.json` · gen_tokens 킷 합치기 · 모든 킷 대비 검사 · `nova.project.json` `design.kit` · `kit list|use` | E3 | |
| REQ-261106-04-2 | 체크리스트 `design.kit` 질문 · 미리보기 · `check_tree` catalog 대조 · md 킷 결정 · import 갭 | E4 | |
| REQ-261106-04-3 | 문서 — 디자인 시스템 README 킷 절 · foundation 5단계 · inbound checklist README · nicomms style-map G1 · ui.md 🗺 행(Tooltip · PeriodSearch · 약관 창 · 입력 마스크 · 표 행 선택) | docs_index | |
| REQ-261106-04-4 | 정보 · 성공 상태색 겹침 검사(브랜드가 초록일 때) | 테스트 | |

## 방법 — 고객이 정한 것 / 맡긴 것 / Claude 판단
| 항목 | 정한 사람 | 내용 |
|---|---|---|
| 원본 보관 | Claude 판단 | 첨부 원본은 **저장소 밖** `C:\Users\han\tools\design-kits\newtype-assets.zip`(sha256 4e0406bc9351151e192a53fcd450f21ac522c5600047ebd337dc60781cacceb6) — Nova 는 복제본의 출발점이라 입고 폴더에 특정 고객 자료를 두지 않는다(처음 넣었다가 checklist · warehouse 테스트 고정구가 깨져 확인) |

## 미결 질문
| 질문 | 누구 몫 | 답 |
|---|---|---|

## 추가 요청 (같은 날)
| 원문 | 반영 |
|---|---|

## 적용 · 결과
