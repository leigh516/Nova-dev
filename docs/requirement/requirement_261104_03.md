# REQ-261104-03 · 요구 체크리스트 — 클릭형 계층 폼 · 자료 역분석 자동 채움 · json + md

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-04 |
| 요청자 | jongyeolhan |
| 원문 | "F:\project-nuri\project-start-guide-05\docs\warehouse\inbound\checklist\checklist.html가 있어 이것을 작성하여서 요구사항을 구체적으로 분석을 하게 되어 있고 이 분석결과를 json(또는jsonl)과 해석하기 쉬운 checklist_YYYYMMDD_NN.md파일로 생성을 하고 있습니다 우리 프로젝트도 checklist.html을 만드는데 복잡도를 줄이고 가능한한 고객이 쉽게 클릭으로 선택을하게 하고 계층구조로 위에서 질의한것을 클릭하면 하위로 구체적인것들을 클릭하면서 쉽게 선택을 하면서 판단 및 작성을 할 수 있게 해주고 또 역공학적으로 inbound에 있는 다른것들을(요구사항)들을 심층분석을해서  checklist.html에 반영을 해서 자동으로 checklist.html을 채워만들어주고 부족한것을 더 채워넣을 수도 있게 만들어서 checklist.html을 활용할수있도록 해주세요(F:\project-nuri\project-start-guide-05\docs\warehouse\inbound\checklist\README.md는 참조해서 위의 요구사항에 맞게 우리시스템에 맞게 구성을 해주세요 )" |
| 입력 자료 | psg05 `docs/warehouse/inbound/checklist/checklist.html`(337KB · 섹션 30여 개 · 레벨 3단 · 탭 6개) · 같은 폴더 `README.md` |
| 크기 | 프로젝트(폼 · 도구 · 명령 · 테스트) |
| 상태 | 적용됨(상시 규칙) |
| 계획 | [inbound/checklist README](../warehouse/inbound/checklist/README.md) |

## 목적과 이유
고객이 기획 용어를 몰라도 **클릭만으로** 요구를 고르게 한다. 받은 자료로 알 수 있는 것은 **미리 채워** 고객은 확인만 하고, 부족한 것만 더 채우게 한다. 그 답을 요구 분석(intake → 인터뷰 → PRD)에 그대로 잇는다.

## 목표 · 비목표 · 반목표
| 구분 | 내용 |
|---|---|
| 목표 | 계층형 클릭 질문(보기를 고르면 세부 질문이 펼쳐짐) · 자료 역분석 자동 채움(근거 표시 · 확인) · 고객 답 json + 읽기 쉬운 md · 요구 분석 연결 |
| 비목표 | psg05 의 탭 ②~⑥(저장소 규약 · 문서 지도) — Nova 는 CLAUDE.md · README 가 그 역할을 한다 |
| 반목표 | 글을 길게 써야 하는 폼, 근거 없는 자동 채움(고객이 "맞아요"만 누르게 됨), 폼과 md 의 정본이 둘 |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| json 인가 jsonl 인가 | Claude 판단 — **JSON**. 고객 답 한 벌은 그 시점의 상태(스냅샷)이고 이력은 revision · git 이 가진다(ADR-004) |
| 파일 이름 | 사용자 지정 — `checklist_YYYYMMDD_NN`(psg05 는 YYMMDD) |
| 레벨 | Claude 판단 — 3단 → **2단(기본 · 자세히, 누적)** 으로 줄임 |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261104-03-1 | 복잡도를 줄인 클릭형 폼 | 질문은 거의 다 보기 클릭(one · many), 글 입력은 이름 · 한 줄 설명 등 소수. 질문마다 "모름 · 나중에". 섹션 목차 · 진행률 · [채울 것만] · [요약 보기]. 파일 하나로 열리고(외부 스크립트 없음) 휴대폰 폭에서 가로 스크롤이 없다(스모크 8단계) | `scripts/checklist_form/` |
| REQ-261104-03-2 | 계층 구조 | 보기마다 `children` 질문이 있고, 고르면 바로 아래에 펼쳐진다(최대 3단). 부모를 풀면 하위 답은 저장에서 빠진다(스모크 2단계 · `test_md_hierarchy`) | `tree.json` |
| REQ-261104-03-3 | 자료 역분석 자동 채움 | `/checklist fill` 이 입고 자료의 발견(E-*)으로 `checklist_prefill.json` 을 쓰고 `build` 가 폼에 넣는다. 자동 채움에는 근거가 필수이고, 폼에 "자료에서 채움 · 확인 필요" 배지 · 근거 · [맞아요]가 보인다(스모크 1단계 · `test_prefill_needs_evidence`) | `/checklist` |
| REQ-261104-03-4 | 부족한 것을 더 채움 | 확인 전 · 모름 · 빈 기본 질문은 [채울 것만]에 모이고, import 하면 부족 항목(G-*)이 되어 `/req-interview` 로 이어진다(`test_import_complete_only_and_idempotent`) | `checklist.py import` |
| REQ-261104-03-5 | json + 해석하기 쉬운 md | [저장] → `checklist_YYYYMMDD_NN.json` + `.md`(frontmatter status · 계층 들여쓰기 · 채울 것 · 표준 판정 후보). 저장 서버는 번호를 매기고 같은 세션은 덮는다(스모크 6단계 · `test_save_numbering`) | `checklist.py serve · md` |
| REQ-261104-03-6 | Nova 에 맞게 | 디자인 토큰(`tokens.css`)을 그대로 넣음. 질문 영역은 PRD 영역 12개. 표준 3종 질문에 배지. lint 가 트리 · 자동 채움 · 폼 · md 드리프트를 검사. 새 프로젝트는 빈 폼으로 시작 | `checklist.py check` |

## 방법 — 고객이 정한 것 / 맡긴 것 / Claude 판단
| 항목 | 정한 사람 | 내용 |
|---|---|---|
| 질문 14섹션 · 보기 | Claude 판단 | psg05 섹션 · PRD 영역 12개 · Nova 표준 기준으로 다시 짰다. 기술 결정(언어 · 아키텍처)은 `/foundation` 몫이라 넣지 않고 "꼭 써야 하는 기술이 있나"만 묻는다 |
| 폼 위치 | Claude 판단 | psg05 와 같이 `inbound/checklist/`(원본)이고, 고객에게 보내는 사본은 `outbound/checklist/` |

## 미결 질문
| 질문 | 누구 몫 | 답 |
|---|---|---|
| 업종별 질문(예: 예약업 전용)을 도메인 팩처럼 갈아 끼울지 | 사용자 | (첫 실제 프로젝트 뒤) |
