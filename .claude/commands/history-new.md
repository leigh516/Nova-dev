---
description: 작업 단위 종료 기록 — history 문서를 만들고 task·계획을 갱신한다
argument-hint: <작업 제목>
---

# /history-new — 작업 이력 기록

인자: `$ARGUMENTS`

## 절차
1. `uv run python scripts/docs_new.py history "$ARGUMENTS" --plan plan_REQ_NN`
2. 긴 본문은 `doc-writer` 에이전트에게 1번 파일 경로를 주고 맡겨도 된다(검증 숫자는 main 이 실행한 출력). 완료를 주장하기 전에 `superpowers:verification-before-completion` — 검증 명령을 지금 실행해 출력 숫자를 적는다. 채운다: 한 일(파일 · 함수 단위) · 발견 · 주의 · 결정 · **검증(실행한 테스트와 결과 숫자)** · 다음
3. tasks 를 **세 갈래로 대조**한다 — 했음(`- [x]`, 테스트로 확인한 것만) · 넘김(🆕 · 다음 요구로, 이유) · 기각(취소선 + 이유). 일괄 체크 금지, 계획서 진척 줄 · §12 체크리스트 · §12.1 실측 정정 갱신
4. 생성물을 만들거나 지웠으면 `uv run python scripts/registry.py sync --by <이름> --note "<사유>"` 와 `uv run python scripts/ledgers.py`(대장 4종)
5. `python nova.py check` 통과(이력은 단계 · 작업 단위로 — task 마다 쓰지 않는다, 분량은 `/docs-write` 등급) → 커밋 · 푸시 → `uv run python scripts/git_record.py "<요약>"`
