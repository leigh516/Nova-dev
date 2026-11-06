---
description: 인터뷰(psg05 이름 — Nova 는 /req-interview) — 체크리스트 · 입고 부족 항목부터 읽고 고객의 말로 숨은 가정을 드러내 인터뷰 기록을 남긴 뒤 /req-analyze 로 넘긴다. 절차는 /req-interview 를 따른다
argument-hint: <인터뷰 주제> [A|B|C]
---

# /interview — /req-interview 의 다른 이름

인자: `$ARGUMENTS`

`/interview`(psg05) 와 `/req-interview`(Nova) 는 **같은 일**이다.

## 절차
1. [`/req-interview`](req-interview.md) `$ARGUMENTS` 의 절차를 그대로 따른다

psg05 의 수치 모호성 관문(Ambiguity ≤ 0.2 · `spec-draft.md` frontmatter)은 들이지 않는다 — 스스로 매긴 주관 수치는 확인할 수 없고, Nova 는 그 자리를 빌더 점검 + 승인 관문([/req-analyze](req-analyze.md) 5 · 7단계 · [superpowers.md §3 · §4](../../docs/conventions/superpowers.md))이 맡는다.

## 하지 않는 것
- 여기에 절차를 따로 적기 — 정본은 `/req-interview` 하나다(두 곳에 적으면 갈라진다)
