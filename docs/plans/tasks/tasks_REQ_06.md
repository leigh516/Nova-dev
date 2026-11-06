# tasks_REQ_06 · 도구 호출 전 한국어 검사 훅 — 할 일 체크리스트

계획: [plan_REQ_06 v1.0](../plan_REQ_06.md) · 규칙: [README §3](../README.md#3-task-작성법--쉽게)
표시: `- [x]` 확인 끝(코드 · 테스트) · `🆕` 작업 중 추가된 일 · `~~취소~~ — 이유` 하지 않기로 함

## 1단계 · 도구 호출 전 검사
- [x] T06-1.01 PreToolUse 시점에 직전 글이 기록에 있는지 실측한다 (세션 기록에서 글 → tool_use 순서 확인 — 계획 §1)
- [x] T06-1.02 `--pretool` 모드로 직전 조각 · description 의 영어 문장을 거부한다 (`tests/test_persona_guard.py::test_pretool_blocks_english_note_right_before_tool` · `test_pretool_checks_only_latest_segment` · `test_pretool_blocks_english_description` · `test_pretool_never_crashes` · `test_pretool_hook_is_registered`)
  - 파일: 고치기 `.claude/hooks/persona_guard.py` · `.claude/settings.json` · 테스트 `tests/test_persona_guard.py`
- [x] 🆕 T06-1.03 기록 파일을 끝에서 거꾸로 읽는다 (`tests/test_persona_guard.py::test_pretool_reads_tail_of_large_transcript` — 53MB 에서 2.4초 → 0.3~0.5초)

**단계 관문**(단계 마지막 task 뒤 한 번): `python nova.py quick --stage T06-1` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 작업 중 발견 (단계와 별개)
- [x] 🆕 T06-9.01 (2026-11-05 — `tests/test_persona_guard.py::test_stop_skips_segment_already_denied_by_pretool`) 응답 끝(Stop) 검사가 도구 호출 전 검사가 이미 막은 줄을 다시 잡는다 — 같은 사과를 두 번 하게 됨(2026-11-05 두 번 관측). 기대: 거부(deny) 결과가 뒤따른 글 조각은 Stop 판정에서 뺀다 · `tests/test_persona_guard.py` 에 사례 추가
- [x] 🆕 T06-9.02 (2026-11-05 — 한글은 따옴표 · 인라인 코드 밖에서 찾는다 · `tests/test_persona_guard.py::test_english_line_with_quoted_korean_word_is_caught`) 한글 낱말이 하나라도 섞인 영어 문장 줄은 검사를 빠져나간다(2026-11-05 "The intent table row name must be '미해결'. Fixing that." 관측) — 기대: 줄에서 인용 · 코드 조각을 뺀 뒤 한글 비율이 낮고 영어 기능어가 있으면 잡는다 · 거짓 양성 사례(식별자 나열 · 한국어 문장 속 영어 명칭)는 계속 통과 · `tests/test_persona_guard.py` 에 사례

**닫음(2026-11-05 사용자 지적 — 무한 개선 금지)**: 이 계획은 여기서 닫는다. 훅 판정의 새 빈틈은 **실제로 세 번 이상 새어 나간 뒤에만** 다음 판본 요구 후보로 모은다(그 사이에는 고치지 않는다). 훅 개선이 본 개발 task 를 밀어내지 않게 한다.
