# tasks_REQ_{{NN}} · {{TITLE}} — 할 일 체크리스트

계획: [plan_REQ_{{NN}} v1.0](../plan_REQ_{{NN}}.md) · 화면 미리보기는 계획 §4 · 규칙: [README §3](../README.md#3-task-작성법--쉽게)
표시: `- [x]` 확인 끝(코드 · 테스트) · `🆕` 작업 중 추가된 일 · `~~취소~~ — 이유` 하지 않기로 함

| 문서 ID | 생성 | 위치 | 원천 | 연결 |
|---|---|---|---|---|
| tasks_REQ_{{NN}} | {{DATE}} · `{{CMD}}` | `{{TASKS_PATH}}` | {{TASKS_REQ_LINK}} | [plan_REQ_{{NN}}](../plan_REQ_{{NN}}.md) |

## 1단계 · (이름)
- [ ] T{{NN}}-1.01 (동사로 끝나는 일) (끝난 기준)
  - 파일: 만들기 `경로` · 고치기 `경로` · 테스트 `경로`
  - 인터페이스: 받는 것(앞 task 의 이름 · 시그니처) / 내주는 것(뒤 task 가 쓸 이름 · 타입)
  - [ ] 실패 테스트 작성 → `uv run pytest <경로>::<이름>` 실패 확인
  - [ ] 최소 구현 → 같은 명령 통과 확인(그 테스트 하나 — 몇 초)

**단계 관문**(단계 마지막 task 뒤 한 번): `python nova.py quick --stage T{{NN}}-1` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

(작은 task 는 한 줄만 써도 된다. 하위 줄은 /task-run 이 superpowers 로 실행할 때 쓰는 단계 — superpowers.md §5. 끝난 기준에 테스트 경로(`tests/test_x.py::이름`)를 적으면 단계 관문의 `quick --stage` 가 그것을 모아 한 번에 돌린다)

## 작업 중 발견 (단계와 별개)
