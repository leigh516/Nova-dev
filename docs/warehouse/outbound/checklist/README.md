# outbound/checklist — 출고

> 나가는 것: ⓪ `checklist.html` — 고객에게 보내는 **요구 체크리스트 폼**(자료에서 미리 채운 판, 원본 `inbound/checklist/checklist.html` 의 사본 — [규칙](../../inbound/checklist/README.md)) ① `gaps.md` — 부족한 것 질문표(고객에게 보내 채워 받는다) ② `acceptance.md` — PRD 수용 기준으로 만든 **인수 점검표** ③ `analysis_checklist.md`

- 만드는 법: `checklist.html` 은 `inbound/checklist/checklist.html`(`checklist.py build` — 원천 `scripts/checklist_form/tree.json` · `checklist_prefill.json`)의 사본, 나머지는 자동(`warehouse.py out`) — `intake.json` 의 부족 항목 · `prd.json` 의 수용 기준에서
- 🔴 정본이 아니다 — 고칠 일이 있으면 정본(`docs/product/`)을 고치고 `uv run python scripts/warehouse.py out`
- 입고 쪽 같은 이름 [inbound/checklist](../../inbound/checklist/README.md) 은 **받은 것**, 여기는 **우리가 만든 것** — 방향이 반대다

관련: [출고 규칙](../README.md)
