---
description: 요구 체크리스트 — 입고 자료를 역으로 분석해 checklist.html 을 자동으로 채워 만들고, 고객이 클릭으로 확인 · 보충한 답(json + md)을 요구 분석에 반영한다
argument-hint: (선택) fill | send | read
---

# /checklist — 요구 체크리스트 자동 채움 · 배포 · 회수

인자: `$ARGUMENTS`
- `fill`: 자동 채움과 폼 만들기(기본)
- `send`: 고객에게 보내기
- `read`: 받은 답을 반영하기

규칙: [docs/warehouse/inbound/checklist/README.md](../../docs/warehouse/inbound/checklist/README.md) · 질문 트리 정본 `scripts/checklist_form/tree.json`

## fill — 자료를 역으로 분석해 폼을 채운다
1. 다른 입고 자료(prd · spec · db-sql · html-mockup · screenshot · handoff · etc)를 분석한다. `docs/product/intake.json` 에 아직 분석되지 않은 파일이 있으면 `/intake` 의 1 · 3 · 4단계를 먼저 해서 발견(E-*)을 만든다(파일마다 `inbound-analyst` · 목업 · 캡처는 `mockup-analyst` 에이전트)
2. **자동 채움 쓰기** — `docs/product/checklist_prefill.json`:
   ```json
   {"answers": {"<질문 id>": {"value": "<보기 id>" | ["<보기 id>", …] | "<글>", "other": "", "evidence": ["E-003"], "why": "근거 한 줄"}}}
   ```
   - 질문 · 보기 id 는 `scripts/checklist_form/tree.json` 에 있는 것만 쓴다(`checklist.py check` 가 검사)
   - 🔴 **근거가 있는 것만 채운다.** 답마다 `evidence`(intake 의 E-*)를 단다. 자료에 없는 것은 비워 두고 고객이 답하게 한다 — 추측으로 채우면 고객이 "맞아요"만 누르고 넘어간다
   - 하위 질문을 채우려면 부모 보기도 채운다(예: `what.replace.current` 는 `what.kind = replace` 가 있어야 보인다)
   - 체크리스트에서 온 발견(`quote` 가 `체크리스트 …` 로 시작)은 근거로 쓰지 않는다. 고객 답은 [불러오기]로 다시 연다
   - 자료끼리 답이 부딪히면 채우지 않고 `intake.json` gaps 에 남긴다
2-1. **목업 목록**: `uv run python scripts/checklist.py mockups` → 입고된 목업 · 캡처(`inbound/html-mockup` · `inbound/screenshot`)를 `checklist_prefill.json` `mockups` 에 맞춘다. 분석한 목업에는 `summary`(무슨 화면인지 한 줄)를 직접 채워 넣는다 — 폼의 '목업 · 기존 화면 채택' 표에 함께 보인다
3. `uv run python scripts/checklist.py build` → `docs/warehouse/inbound/checklist/checklist.html`. 자동 채움 답에는 "자료에서 채움 · 확인 필요" 배지와 근거가 붙는다
4. `uv run python scripts/warehouse.py out` → 고객에게 건넬 사본 `docs/warehouse/outbound/checklist/checklist.html`
5. `uv run python scripts/checklist.py check` · `uv run python scripts/warehouse.py check`
6. 보고: 자동 채움 수 / 기본 질문 수, 비워 둔 주요 영역, 보내는 방법(아래 send)

## send — 고객에게 보내기 (둘 중 하나)
- **같이 앉아서** · 이 PC 에서: `python nova.py checklist` → 브라우저가 열린다
  - [임시저장] · [완료하고 제출]을 누르면 `inbound/checklist/checklist_YYYYMMDD_NN.json` 과 `.md` 가 바로 생긴다
  - 같은 세션에서 다시 저장하면 같은 파일을 덮고 판(revision)이 오른다
- **멀리 있는 고객**: `docs/warehouse/outbound/checklist/checklist.html` 파일 하나를 보낸다(외부 스크립트가 없어 더블클릭으로 열린다)
  - 고객은 [완료하고 제출]로 `checklist_YYYYMMDD_01.json` 을 내려받아 돌려준다(중간에 멈출 때는 [임시저장] — 같은 브라우저로 다시 열면 이어진다)
  - 돌려받은 파일은 `inbound/checklist/` 에 넣는다
- 고객 안내 문구(한국어로 함께 보낸다):
  - 아는 것만 클릭하세요. 답하기 어려운 질문은 오른쪽 [건너뛰기] 스위치를, 섹션 전체가 어려우면 [이 섹션 답하기] 스위치를 끄세요
  - 보기 밑의 설명과 [쉬운 설명] · [용어 풀이]를 참고하세요. 'Nova 기본' 배지는 이미 준비된 선택입니다
  - 노란 "자료에서 채움"은 맞으면 [맞아요]를 누르고, 틀리면 다른 보기를 누른다
  - 중간에 멈출 때는 [임시저장], 다 됐으면 [완료하고 제출]

## read — 받은 답을 반영한다
1. `uv run python scripts/checklist.py md` — 받은 json 마다 읽기 쉬운 `checklist_YYYYMMDD_NN.md` 를 만든다(손으로 고치지 않는다)
2. `uv run python scripts/checklist.py import` — **완료(status: complete)** 로 표시된 최신본만 반영한다
   - 고객 답 · 확인한 답 → intake 발견(E-*)
   - 비었거나 건너뛴(스위치) · 확인 전인 기본 질문, 건너뛴 섹션의 기본 질문 → 부족 항목(G-*)
   - 작성중은 반영하지 않고 보고만 한다
3. `uv run python scripts/warehouse.py out` → `outbound/checklist/gaps.md`(남은 질문표) 등 갱신
4. 다음: 부족 항목이 남았으면 `/req-interview`(부족한 것만 묻는다), 충분하면 `/prd`
