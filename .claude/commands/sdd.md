---
description: 명세 주도 개발 묶음(SDD) — 크기 판정(빠른 일 · 작은 변경 · 프로젝트)으로 길을 고르고, 체크리스트 → PRD → 기반 → SPEC → 계획 → 실행 → 검토 → 마무리를 승인 관문을 건너뛰지 않고 차례로 부른다. 산출물로 지금 단계를 판정해 이어서 시작한다
argument-hint: [full | light | fast] <기능 · 묶음 이름>
---

# /sdd — 명세 주도 개발 묶음

`/sdd` 는 새 로직 없이 **기존 명령을 순서대로 부르는 묶음**이다. 각 단계의 절차 · 관문 · 부르는 에이전트는 그 명령이 정한다(여기서 다시 적지 않는다).

인자: `$ARGUMENTS` — 첫 낱말이 `full`(프로젝트) · `light`(작은 변경) · `fast`(빠른 일)면 길, 나머지는 이름. 길을 비우면 1단계 크기 판정으로 정한다

규칙: 크기 판정 [superpowers.md §4](../../docs/conventions/superpowers.md) · 흐름 지도 §2 · 끝이 있는 일 [CLAUDE.md](../../CLAUDE.md) · [plans README §5](../../docs/plans/README.md)

## 절차
0. **규모 프로파일**을 읽는다 — `python nova.py profile get`. 인자로 길을 주지 않았으면 프로파일의 기본 길(`lite` → light · `product` · `platform` → full)에서 시작하고, 그래도 아래 크기 판정이 더 크면 큰 쪽으로 간다([DEEP] 필수 목록은 프로파일과 무관 — superpowers.md §4.1)
1. **크기 판정**(superpowers.md §4)을 사용자 말로 알린다 — 빠른 일(바로 한다) · 작은 변경(요구 문서 → task) · 프로젝트(제품 전체 · 큰 범위). 애매하면 한 단계 큰 쪽
2. **지금 단계 판정** — 산출물이 있는지로 정하고, 있는 단계는 건너뛰어 이어서 시작한다(어디서 시작하는지 근거와 함께 한 줄로 알린다)

   | 있는 것 | 여기서 시작 |
   |---|---|
   | 없음 | 길의 첫 단계 |
   | `docs/product/intake.json` | `/req-interview`(부족한 것만) 또는 `/prd` |
   | `docs/product/prd.json` 승인됨 | `/foundation` |
   | `spec.json` 승인됨 | `nova-masterplan` 스킬(마스터플랜이 이미 맞으면 `/plan-new`) |
   | 요구 문서 승인됨(`승인 \| …` 한 줄) | `/plan-new` |
   | `plan_REQ_NN` + `tasks_REQ_NN` 에 `- [ ]` | `/task-run` — 겹치지 않는 task 를 이어서 자동으로 진행하려면 `/task-run <tasks_REQ_NN> subagent --auto`(절차 · 멈춤 조건은 [task-run.md](task-run.md)가 정한다 · 위 승인 관문은 그대로) |
   | task 가 모두 판정됨 | `/review-request` → `/finish` |
3. **길에 따라 차례로 부른다**

   | 길 | 순서 |
   |---|---|
   | 프로젝트(full) | `/checklist` → `/intake` → `/req-interview`(부족한 것만) → `/prd`(**승인**) → `/foundation` → `/spec`(**승인**) → `nova-masterplan` 스킬 → `/plan-new` → `/task-run` → `/review-request` → `/finish` → `/round-close` |
   | 작은 변경(light) | `/req-new` 또는 `/req-analyze`(**승인**) → `/plan-new` → `/task-run` → `/review-request`(선택) → `/finish` |
   | 빠른 일(fast) | 바로 고친다 → `python nova.py check` → `/docs-write` |
4. **승인 관문은 건너뛰지 않는다** — PRD · SPEC · 요구 문서의 승인 전에는 다음 단계(계획 · 코드 · 골격 · 설치)로 가지 않는다. "급하니 건너뛰자"는 요청이 와도 멈추고, 빠른 길이 필요하면 크기를 다시 판정해 빠른 일로 줄일 수 있는지 사용자에게 묻는다
5. **끝** — 요구의 종료 조건 `python nova.py exit-check REQ-…` 가 모두 녹색이면 끝이다. 중간에 새로 보인 것은 이번 일을 넓히지 않고 새 요구(`/req-new`) · 다음 판본으로 보낸다. 빠른 일이 5파일을 넘거나 계약에 닿으면(`python nova.py docs-write grade`) 작은 변경 · 프로젝트로 올린다

## 하지 않는 것
- 승인 관문 건너뛰기 · 승인 없이 계획 · 코드 시작
- 각 명령의 절차 · 에이전트를 여기 다시 적기 — 정본은 그 명령이다
- 이미 있는 산출물을 다시 만들기(2단계로 이어서 시작한다)
- 종료 조건 밖으로 넓히기 — 새로 보인 것은 새 요구로
