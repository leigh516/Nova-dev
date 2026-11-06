---
description: 계획(psg05 이름 /plan) — 승인된 요구 하나의 세부 계획(§0~§13)과 task 분해를 만든다. Nova 의 /plan-new 와 같은 일이다
argument-hint: <계획 제목> REQ-YYMMDD-NN
---

# /plan — 세부 계획 (Nova 이름 `/plan-new`)

인자: `$ARGUMENTS`

psg05 의 `/plan` 이름으로 부르는 입구다. **절차는 [/plan-new](plan-new.md) 를 그대로 따른다**(여기에 다시 적지 않는다).

- 요구가 승인되지 않았으면 멈추고 `/req-analyze` 로 돌아간다(승인 관문)
- 여러 요구를 잇는 전체 지도는 `/masterplan`
