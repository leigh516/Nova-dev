# docs/product — 제품 정본 (입고 분석 · PRD · SPEC)

> 한 줄 요약: 입고 자료를 분석하고 고객 인터뷰로 부족한 것을 채운 결과가 여기에 **정본 JSON** 으로 모인다. 사람이 읽는 md 와 출고본(`docs/warehouse/outbound/`)은 정본에서 **생성**한다. 요구: [REQ-261104-02](../requirement/requirement_261104_02.md) · 형식 원칙: [ADR-004](../adr/ADR-004-ledger-formats.md)(선언 · 상태는 JSON, 보기는 생성 MD)

## 1. 파일
| 정본 | 보기(생성) | 만드는 명령 | 담는 것 |
|---|---|---|---|
| `intake.json` | `intake.md` | `/intake` | 입고 파일마다 지문 · 상태 · 요약 · **발견**(E-001, PRD 영역 · 종류 · 원문 인용) + **부족 항목**(G-001, 인터뷰 질문) |
| `prd.json` | `prd.md` | `/prd` | 제품 · 배경 · 목표/비목표/반목표 · 성공 지표(M-01) · 사용자(U-01) · **기능(F-001) + 수용 기준(F-001-AC1)** · 비기능(N-01) · 제약 · 가정 · 미결 질문(Q-01) · 승인 |
| `spec.json` | `spec.md` | `/foundation` → `/spec` | **기반 결정**(언어 · 프레임워크 / 아키텍처 · 배포 / DB / 횡단관심사) · 서비스 · 데이터 모델 · API(API-01) · 이벤트 · 화면(S-01) · 테스트 맵 · 승인 |

빈 틀: [`_template_intake.json`](_template_intake.json) · [`_template_prd.json`](_template_prd.json) · [`_template_spec.json`](_template_spec.json). 처음 만들 때 복사해 `intake.json` · `prd.json` · `spec.json` 으로 둔다.

## 2. 흐름 — 입고 → 분석 → 인터뷰 → PRD → 기반 → SPEC → 계획
```
docs/warehouse/inbound/*    ─/intake──────▶ intake.json   (발견 E-* · 부족 G-*)
        부족 G-* · 빈 영역  ─/req-interview▶ interviews/INT-*  (superpowers:brainstorming — 부족한 것만 묻는다)
                            ─/prd──────────▶ prd.json      (승인 관문)
                            ─/foundation───▶ spec.json foundation + ADR (4단계 질의) + nova.project.json standards
                            ─/spec─────────▶ spec.json     (승인 관문)
                            ─warehouse.py out▶ outbound/*  (prd · spec md/html/json · 인수 점검표 · 질문표 · DDL · 분류별 분석)
                            ─/plan-new─────▶ plan_REQ_NN + tasks (기능 묶음마다) → /task-run
```

## 3. 규칙
- **정본은 JSON 하나다.** md · html · 출고본은 `uv run python scripts/warehouse.py out` 으로 만들고 손으로 고치지 않는다. `lint`(`warehouse.py check`)가 스키마 · 참조 · 드리프트를 검사한다
- **근거를 단다**: PRD 기능마다 `sources`(입고 파일 경로 · `INT-…` · `REQ-…`), 발견마다 원문 인용(`quote`). 고객이 말하지 않은 것은 `assumptions` 에 `"by": "Claude 판단"` 으로
- **수용 기준은 확인 가능해야 한다**: "빠르다" 대신 "목록 첫 화면이 2초 안에 뜬다(p95)". 기준마다 `test`(확인 방법) → SPEC `test_map` 이 테스트 이름과 잇는다
- **승인 관문**: `status: "승인"` 은 `approved.by` · `approved.date` 가 있어야 한다. 승인 전에는 다음 단계(PRD → foundation/spec, SPEC → 계획 · 구현)로 가지 않는다([superpowers.md §4](../conventions/superpowers.md))
- **바꿀 때**: 승인 뒤 고치면 `version` 을 올리고(0.1 → 0.2, 큰 변경은 1.0 → 2.0) 바뀐 내용을 요구 문서(REQ)로 남긴다. SPEC 의 `prd_version` 이 PRD `version` 과 다르면 검사가 실패한다 — PRD 가 바뀌면 SPEC 도 다시 맞춘다
- **표준 판정의 정본은 `nova.project.json` standards** 다(spec.md 는 보여 주기만). `/foundation` 이 그 자리를 고친다
- **DB**: SPEC `data_model` 에 `id` · `tenant_id` 는 쓰지 않는다(UUIDv7 · 테넌트 칸은 자동). 칸마다 `comment`(의미) 필수. 생성된 `outbound/db-sql/schema.sql` 은 **초안**이고, 실행 DB 적용은 사람 승인 후 건별로 한다

## 4. 칸 형식 요약
| 값 | 허용 |
|---|---|
| intake 파일 `status` | 미분석 · 분석됨 · 재분석 필요 · 삭제됨 |
| 발견 `area`(PRD 영역 12) | 목적 · 배경 / 사용자 · 역할 / 범위(목표 · 비목표) / 기능 / 화면 / 데이터 / 외부 연동 / 비기능 / 운영 / 일정 · 예산 · 제약 / 표준(테넌트 · 업종 · AI) / 성공 지표 |
| 발견 `kind` | 요구 · 화면 · 데이터 · API · 제약 · 사실 · 질문 |
| 부족 항목 `status` | 열림 · 인터뷰 중 · 답함 · 해당 없음 |
| PRD · SPEC `status` | 초안 · 승인 |
| 기능 `priority` | 필수 · 중요 · 선택 |
| 아키텍처 `style` | 모듈러 모놀리스 · MSA · 모놀리식 |
| 횡단관심사 `decision` | 내장 채택 · 직접 구현 · 미사용 (내장 채택이 아니면 `reason` 필수) |
| 칸 `type` | `string(N)` · `text` · `int` · `bigint` · `decimal(p,s)` · `bool` · `date` · `datetime` · `json` · `ref`(다른 개체 UUIDv7) |
| API `permission` | `<모듈>.<행위>`(게이트웨이 권한 — [backend.md](../conventions/backend.md)) |
