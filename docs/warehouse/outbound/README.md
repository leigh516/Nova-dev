# docs/warehouse/outbound — 출고 (사람에게 건네는 결과물)

> 한 줄 요약: 입고 자료를 분석하고 인터뷰해 만든 **결과물을 입고와 같은 분류로** 내보낸다. 🔴 **여기는 정본이 아니다** — 정본은 [`docs/product/`](../../product/README.md). 입고 쪽: [inbound](../inbound/README.md)

| 폴더 | 무엇이 나가나 | 만드는 법 |
|---|---|---|
| [`checklist/`](checklist/README.md) | ⓪ `checklist.html`(입고 폼의 사본) ① `gaps.md` — 부족한 것 질문표(고객에게 보내 채워 받는다) ② `acceptance.md` — PRD 수용 기준으로 만든 **인수 점검표** ③ `analysis_checklist.md` | 자동(`warehouse.py out`) — 폼은 `checklist.py build` 결과의 사본, 나머지는 `intake.json` 의 부족 항목 · `prd.json` 의 수용 기준에서 |
| [`prd/`](prd/README.md) | **최종 PRD** — `prd.md` · `prd.html`(파일 하나로 열림) · `prd.json` + `analysis_prd.md` | 자동 — 정본 `docs/product/prd.json` 에서 파생 |
| [`spec/`](spec/README.md) | **최종 SPEC** — `spec.md` · `spec.html` · `spec.json` + `analysis_spec.md` | 자동 — 정본 `docs/product/spec.json` 에서 파생 |
| [`db-sql/`](db-sql/README.md) | `schema.sql`(SPEC 데이터 모델 → MariaDB DDL 초안, 기본키 UUIDv7 `CHAR(36)`) · 짝으로 `rollback.sql` · `analysis_db-sql.md`(입고 db-sql 분석 발견 — 우리 모델과의 차이는 `/intake` 가 발견 · 부족 항목으로 기록) | 자동 — `spec.json` `data_model` 에서. 🔴 실행 DB 에 적용하는 것은 사람 승인 후 건별로 |
| [`html-mockup/`](html-mockup/README.md) | `analysis_html-mockup.md`(화면 목록 · 상태 · 데이터) · 우리가 만든 목업 사본(정본은 `docs/plans/mockups/REQ_NN/`) | 분석은 자동, 목업은 `python nova.py mockups` 후 필요한 것만 복사 |
| [`screenshot/`](screenshot/README.md) | `analysis_screenshot.md` · 우리가 찍은 구현 증빙 캡처(`ui-smoke` · `kmp-snapshots` 결과에서 골라 복사) | 분석은 자동, 캡처는 손으로 골라 복사 |
| [`claude-code-handoff/`](claude-code-handoff/README.md) | `analysis_claude-code-handoff.md` · 저장소 **밖으로** 넘기는 인계서 `handoff_<대상>_YYYYMMDD.md`(우리 명령 · 경로를 모르는 사람도 읽게 다시 쓴다) | 분석은 자동, 인계서는 요청 시 작성 |
| [`etc/`](etc/README.md) | `intake_report.md` — 입고 분석 전체 보고(파일별 요약 · 영역별 근거 · 부족 항목) · `analysis_etc.md` | 자동 — `docs/product/intake.json` 에서 |

- 만들기: `uv run python scripts/warehouse.py out` (정본이 없으면 그 파생본은 만들지 않고, 이전에 만든 것은 지운다). 검사: `uv run python scripts/warehouse.py check` — `lint` 에 포함
- 생성물 표시: md 는 첫 줄 `<!-- 생성물: … -->`, sql 은 첫 줄 `-- 생성물: …`, html 은 본문 첫머리에 같은 표시, `prd.json` · `spec.json` 은 이름으로 생성물이다. 생성물은 손으로 고치지 않는다. 손으로 고른 캡처 · 목업 사본 · 인계서만 사람이 관리한다
- html 은 파일 하나로 브라우저에서 열린다(외부 스크립트 없음, 밝은 · 어두운 화면)
