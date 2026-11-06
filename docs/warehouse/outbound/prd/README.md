# outbound/prd — 출고

> 나가는 것: **최종 PRD** — `prd.md` · `prd.html`(파일 하나로 열림) · `prd.json` + `analysis_prd.md`

- 만드는 법: 자동 — 정본 `docs/product/prd.json` 에서 파생
- 🔴 정본이 아니다 — 고칠 일이 있으면 정본(`docs/product/`)을 고치고 `uv run python scripts/warehouse.py out`
- 입고 쪽 같은 이름 [inbound/prd](../../inbound/prd/README.md) 은 **받은 것**, 여기는 **우리가 만든 것** — 방향이 반대다

관련: [출고 규칙](../README.md)
