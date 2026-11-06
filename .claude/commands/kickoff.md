---
description: 착수(새 프로젝트 · 큰 기능의 시작점) — 입고 자료나 한 줄 아이디어를 받아 체크리스트 · 입고 분석 · 인터뷰로 이어 docs/PROJECT.md(북극성 · 문제 · 사용자 · 판정형 성공 기준)를 고정하고 /req-interview 로 넘긴다
argument-hint: [입고 자료 경로 | 한 줄 아이디어] (비우면 docs/warehouse/inbound/ 를 훑는다)
---

# /kickoff — 착수

인자: `$ARGUMENTS`
규칙: [CLAUDE.md](../../CLAUDE.md) 문서 규칙 0 · [product README](../../docs/product/README.md) · 북극성 틀 [_template_PROJECT.md](../../docs/_template_PROJECT.md) · 흐름 지도 [superpowers.md §2](../../docs/conventions/superpowers.md)

`/kickoff` 는 **첫 단계를 고르고 북극성을 고정하는 입구**다. 체크리스트 · 입고 분석 · 인터뷰의 절차는 각 명령이 정한다(여기서 다시 적지 않는다). 그 뒤 전체 흐름은 `/sdd` 가 잇는다.

## 절차
0. **본 작업 트리(main)에서** — `docs/PROJECT.md` · 인터뷰 기록은 main 이 쓴다(단일 기록자). worktree 안이면 멈추고 `python nova.py send --to main …` 으로 알린다
1. 지금 상태를 읽는다 — `docs/PROJECT.md`(틀 그대로인가 · 채워졌나), `docs/product/intake.json` · `prd.json` 유무, `docs/warehouse/inbound/` 의 파일(README 제외). 이미 채워진 단계는 다시 하지 않는다(무엇을 건너뛰는지 한 줄로 알린다)
1-0. **규모 프로파일**을 정한다 — `python nova.py profile suggest`(서비스 · 웹 앱 · 팩 수로 추천) → 사용자에게 추천 · 대가를 한 줄로 → `python nova.py profile set <값> --why "<이유>"`. `lite` 면 체크리스트 · 입고 · PRD · SPEC · 마스터플랜을 건너뛰고 `docs/PROJECT.md` 북극성만 고정한 뒤 `/req-new` → `/plan-new` 로 간다(승인 관문 · 안전 검사 · 기록 하한은 그대로)
1-1. 저장소가 처음 생성된 직후라 맥락이 없으면 `project-starter` 에이전트로 저장소 요약부터 받는다
2. 입력으로 길을 고른다

   | 입력 | 다음 |
   |---|---|
   | 입고 자료가 있다(목업 · PRD · 회의록 · 체크리스트) | 3 → 4 |
   | 한 줄 아이디어뿐 | 5(인터뷰로 바로) |
   | 기존 코드베이스 합류 · 현황 파악 | `/analyze` 로 보낸다(이 명령의 일이 아니다) |
   | 요청 하나(제품 전체가 아님) | `/req-interview` 또는 `/req-new` 로 보낸다 |
3. **체크리스트 먼저**: `/checklist`(`fill` — 자료로 폼을 자동 채움 → 고객 확인 · 보충 → `read`). 완료본(`status: complete`)만 반영한다 — 작성중은 "작성중 N건"으로만 알린다. 고객이 아직 답하지 않았으면 기다리지 않고 4로 간다(체크리스트는 렌즈이지 관문이 아니다)
4. **입고 분석**: `/intake` — 결과는 `docs/product/intake.json`(발견 E-* · 부족 항목 G-*). 파일이 많거나 크면 `/intake` 가 `inbound-analyst` · `mockup-analyst` 에이전트를 파일마다 한 메시지에 함께 띄운다
5. **인터뷰**: `/req-interview "<주제>"` — 부족 항목(G-*)과 체크리스트 빈 칸만 묻는다. 아이디어뿐이면 문제 · 주 사용자 · 성공 모습 · 하지 않을 것을 먼저 묻는다
6. **북극성 고정** — 인터뷰에서 고객이 확인한 것만으로 `docs/PROJECT.md` 를 채운다(틀: `_template_PROJECT.md`): 북극성 · 문제 · 주 사용자 · 성공 기준(판정형 — 숫자 목표를 박지 않고 예/아니오로 답하는 상태 + 판정 근거). 고객이 말하지 않은 것은 "Claude 판단"으로 표시한다
7. **멈춤 — 사용자 확인**: 북극성 · 문제 · 사용자 · 성공 기준 한 문단을 사용자에게 보여 주고 확인을 받는다. 확인 전에는 `/prd` · `/foundation` · 코드 · 골격으로 가지 않는다
8. `uv run python scripts/docs_index.py --check` → 다음을 알린다: 제품 전체면 `/sdd full <이름>`(→ `/prd` → `/foundation` → `/spec` → 계획), 요청 하나로 줄었으면 `/req-analyze INT-YYMMDD-NN`

## 하지 않는 것
- 체크리스트 · 입고 분석 · 인터뷰 절차를 여기서 따로 하기 — 그 명령을 부른다
- 프로파일 등급(psg05 `solo|product|platform`)을 묻기 — Nova 는 표준 판정(`nova.project.json` `standards`)이 그 자리이고 `/foundation` 몫이다
- `docs/state/` · `INVENTORY.md` · `TRACE.md` 만들기 — Nova 는 `docs/product/*.json` 이 정본이다
- 기술 결정(언어 · 아키텍처 · DB · 횡단관심사) 확정 — `/foundation`
