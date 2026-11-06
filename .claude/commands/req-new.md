---
description: 새 요구사항 기록 — 사용자 요청을 requirement 문서로 남기고 계획과 연결한다
argument-hint: <요구 제목>
---

# /req-new — 새 요구사항 기록

인자: `$ARGUMENTS` (요구 제목)

## 절차
1. `uv run python scripts/docs_new.py req "$ARGUMENTS"` → `docs/requirement/requirement_YYMMDD_NN.md` + 인덱스 한 줄
2. 표를 채운다: **원문은 사용자가 한 말 그대로**(비밀번호 · 키는 지운다), 입력 자료, 상태
3. 애매한 점은 사용자에게 묻고 답을 "확인한 결정" 표에 남긴다. 중요한 것이 빠져 있으면(누가 · 왜 · 성공 모습 · 하지 않을 것) `superpowers:brainstorming` 원칙으로 한 번에 질문 하나씩 묻는다. 고객 인터뷰가 필요하면 `/req-interview`, 빌더 점검 · 승인 관문까지 하려면 `/req-analyze`
4. "요구사항 분해" 표: 하위 ID `REQ-YYMMDD-NN-n`, 요구마다 **확인 가능한 수용 기준**
5. 계획 연결:
   - 규칙 · 정책이면 해당 `docs/conventions/*.md` 를 고치고 상태 `적용됨(상시 규칙)`
   - 구현이 필요하면 `/plan-new` 로 세부 계획을 만들거나 기존 plan 에 단계 · task 추가(🆕)
   - 마스터플랜에 영향이 있으면 `docs/plans/drafts/` 에 초안(README §1)
6. 인덱스의 `계획` 칸을 채우고 `uv run python scripts/docs_index.py --check`
