# ADR-006 · 제품 정본 PRD · SPEC 은 JSON, 출고본은 파생

| 항목 | 내용 |
|---|---|
| 일자 | 2026-11-04 |
| 상태 | 채택 |
| 대체 | - |
| 요구 | [REQ-261104-02](../requirement/requirement_261104_02.md) |

## 배경
사용자는 다음 흐름을 요청했다.
1. `docs/warehouse/inbound` 에 넣은 자료를 심층 분석한다
2. 부족한 것은 Superpowers 인터뷰로 채운다
3. 최종 `prd.md(prd.json)` 을 만든다
4. `/foundation` 4단계 질의로 `spec.md(spec.json)` 을 만든다
5. 결과물은 입고와 같은 분류의 `outbound` 로 낸다

같은 내용을 md 와 json 두 곳에 손으로 쓰면 정본이 둘이 되고, 어느 쪽이 맞는지 알 수 없게 된다. project-start-guide-05 는 PRD · SPEC 정본을 md 로 두고 해시로 출고본 드리프트를 잰다. Nova 는 ADR-004 에서 "선언 · 상태는 JSON, 보기는 생성 MD, MD 를 기계 입력으로 쓰지 않는다"로 정했다.

## 결정
- 정본은 `docs/product/intake.json` · `prd.json` · `spec.json` 셋이다. `intake.md` · `prd.md` · `spec.md` 는 `scripts/warehouse.py out` 이 만드는 보기다
- 출고본 `docs/warehouse/outbound/<분류>/` 는 정본에서 파생한다
  - prd · spec: md · html · json
  - checklist: 질문표 · 인수 점검표
  - db-sql: DDL 초안 + 되돌림
  - 분류별: 분석 보고
- 생성 파일에는 생성물 표시를 단다. `lint`(`warehouse.py check`)가 스키마 · 참조 · 드리프트 · 입고/출고 대칭을 검사한다
- ID 체계
  - 입고 분석: 발견 `E-001` · 부족 `G-001`
  - PRD: 사용자 `U-01` · 기능 `F-001` · 수용 기준 `F-001-AC1` · 비기능 `N-01` · 지표 `M-01` · 질문 `Q-01`
  - SPEC: API `API-01` · 화면 `S-01`
- 승인 관문: `status: 승인` 에는 `approved.by` · `date` 가 있어야 한다. SPEC 의 `prd_version` 이 PRD `version` 과 다르면 검사에 실패한다
- 표준 판정의 정본은 계속 `nova.project.json` `standards` 다. spec 은 보여 주기만 한다

## 검토한 대안
| 대안 | 장점 | 단점 | 버린 이유 |
|---|---|---|---|
| md 정본 + 해시 드리프트(psg05) | 사람이 바로 쓴다 | 표를 기계가 다시 읽어야 한다(열 순서에 깨짐) · 참조 검사가 어렵다 | ADR-004 와 충돌 |
| md · json 둘 다 손으로 | 자유롭다 | 정본이 둘 | 반목표 |
| JSON 정본 + 생성 보기(채택) | 참조 · 형식을 기계로 검사, 출고 · DDL · 점검표를 자동으로 만든다 | 사람이 JSON 을 직접 고치기 불편 | Claude 가 명령(/prd · /spec)으로 쓰고, 사람은 md · html 로 읽는다 |

## 결과
- 좋아지는 것: 입고 → 인터뷰 → PRD → SPEC 의 근거를 ID 로 따라갈 수 있다. 수용 기준은 테스트 맵에서 실패 테스트로, 데이터 모델은 DDL 초안으로 이어진다
- 감수하는 것: PRD 를 고치려면 JSON 을 고치고 `warehouse.py out` 을 돌려야 한다
- 지킬 것: 출고본 · 보기 md 를 손으로 고치지 않는다. DDL 초안을 실행 DB 에 자동으로 적용하지 않는다
