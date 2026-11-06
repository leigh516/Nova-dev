# docs/warehouse — 자료 창고 (입고 · 출고)

> 한 줄 요약: 고객 · 외부에서 받은 **원본 자료는 `inbound/`(입고)** 에 넣고, 우리가 분석 · 작성해 **사람에게 건네는 결과물은 `outbound/`(출고)** 에 나온다. 두 폴더는 **같은 이름의 하위 폴더 8개**로 대칭이다. 규약: [product README](../product/README.md)

## 흐름
```
inbound/<분류>/  원본을 넣는다(고치지 않는다)
   │  /intake          심층 분석 → docs/product/intake.json(파일별 요약 · 근거 · 부족 항목)
   │  /req-interview   부족한 것만 골라 고객 인터뷰(superpowers:brainstorming, 방식 A · B · C)
   │  /prd             최종 PRD 정본 docs/product/prd.json (+ prd.md 보기) — 승인 관문
   │  /foundation      기반 4단계 질의(언어 · 프레임워크 / 아키텍처 · 배포 / DB / 횡단관심사 + 표준 판정) → ADR
   │  /spec            SPEC 정본 docs/product/spec.json (+ spec.md) — 서비스 · 데이터 · API · 이벤트 · 화면 · 테스트 맵
   ▼  uv run python scripts/warehouse.py out
outbound/<분류>/  사람에게 건네는 파생본(md · html · json · sql) — 정본이 아니다
   │  /plan-new        spec 의 기능 묶음마다 세부 계획 → /task-run
```

## 규칙
- **정본은 `docs/product/`**(intake · prd · spec JSON)이다. `outbound/` 는 파생본이라 **손으로 고치지 않는다** — 정본을 고치고 `warehouse.py out` 으로 다시 낸다. `lint` 가 출고본이 정본과 어긋나면(드리프트) 실패시킨다
- `inbound/` 원본은 편집하지 않는다. 같은 파일을 새 판으로 받으면 새 이름으로 넣는다(예: `_v2`). 고치거나 지우면 `/intake` 가 다시 분석할 파일로 잡는다(지문 sha256 비교)
- 읽는 순서: checklist → prd → spec → db-sql → html-mockup → screenshot → claude-code-handoff → etc
- 큰 바이너리(영상 · 디자인 원본)는 넣지 않고 경로 · 링크를 `etc/` 메모로 남긴다. 개인정보 · 비밀번호가 든 자료는 지우고 넣는다
- 하위 폴더를 늘리면 `inbound/` · `outbound/` 양쪽에 같은 이름으로 만들고 `scripts/warehouse.py` 의 `CATEGORIES` 에도 더한다(`warehouse.py check` 가 대칭 · 목록을 검사한다)
