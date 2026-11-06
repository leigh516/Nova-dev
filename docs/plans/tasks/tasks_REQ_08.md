# tasks_REQ_08 · 계획 자동 진행 — main 운전자 · 병렬 배치 · 재개 · 안전장치 — 할 일 체크리스트

계획: [plan_REQ_08 v1.0](../plan_REQ_08.md) · 화면 미리보기는 계획 §4 · 규칙: [README §3](../README.md#3-task-작성법--쉽게)
표시: `- [x]` 확인 끝(코드 · 테스트) · `🆕` 작업 중 추가된 일 · `~~취소~~ — 이유` 하지 않기로 함

| 문서 ID | 생성 | 위치 | 원천 | 연결 |
|---|---|---|---|---|
| tasks_REQ_08 | 2026-11-05 · `docs_new.py plan` | `docs/plans/tasks/tasks_REQ_08.md` | [REQ-261105-09](../../requirement/requirement_261105_09.md) | [plan_REQ_08](../plan_REQ_08.md) |

## 1단계 · 기계 판정 부품 (`scripts/task_batch.py` · `tests/test_task_batch.py`)
- [x] T08-1.01 `feat/req-agent-ops` 병합 여부를 확인하고 아직이면 사용자에게 병합 순서를 묻기 (끝난 기준: 현재 브랜치에 `docs/conventions/agents.md` 와 에이전트 README 부르는 규칙 9 가 있다 — 없으면 4단계를 시작하지 않고 멈춤) — 2026-11-05: main 병합 daf0ce1 · 푸시 5121684 · 두 파일 존재 확인
- [x] T08-1.02 tasks 문서를 읽어 task 별 ID · 상태(열림 · 끝남 · 취소) · 본문 · 단계를 내는 `parse_tasks` 만들기 (`tests/test_task_batch.py::test_parse_tasks_states` — `- [x]` · `- [ ]` · 취소선 · 🆕 줄을 구분)
- [x] T08-1.03 task 본문에서 건드릴 경로를 뽑는 `task_paths` 만들기 (`파일:` 줄 · 백틱 경로 · 괄호 안 테스트 경로를 모으고, 경로가 없으면 빈 목록 — `tests/test_task_batch.py::test_task_paths_extracts_and_empty`)
- [x] T08-1.04 두 task 의 겹침을 판정하는 `overlaps` 만들기 (같은 경로 · 한쪽이 다른 쪽의 폴더이면 겹침, 경로가 없는 task 는 모두와 겹침으로 간주 — `tests/test_task_batch.py::test_overlaps_same_dir_prefix_and_disjoint`)
- [x] T08-1.05 선행이 끝난 열린 task 만 겹침 없는 묶음으로 짜는 `next_batch` 만들기 (본문의 `(선행: T…)` 가 미완이면 제외 · 단계 관문 전에는 다음 단계 task 제외 · 최대 개수 인자 `max_parallel` — 기본값 없이 호출자가 준다 · `tests/test_task_batch.py::test_next_batch_prerequisite_stage_gate_and_max`)
- [x] T08-1.06 재개용 `pending_ids` 만들기 (체크된 · 취소된 task 는 건너뛰고 열린 ID 만 순서대로 — 같은 입력에서 `next_batch` 와 일치 · `tests/test_task_batch.py::test_pending_ids_skips_done_and_cancelled`)
- [x] T08-1.07 `uv run python scripts/task_batch.py <tasks 파일> --max N` 로 다음 묶음과 남은 수를 한국어로 출력하게 하기 (열린 task 가 없으면 종료 0 과 "끝" 안내 · 파일이 없으면 종료 1 · `tests/test_task_batch.py::test_cli_prints_batch_and_done`) — 2026-11-05 1.02~1.07: 커밋 e43555b · 486b621 · test_task_batch 9 통과(main 재실행) · tasks 8개 파일 CLI 종료 0 · task 검토 중요 3 고침 · 재검토 4건 처리됨 · 종료 코드 0 끝/1 인자/2 막힘/3 형식 이상

**단계 관문**: `python nova.py quick --stage T08-1` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 2단계 · `/task-run --auto` 절차 (`.claude/commands/task-run.md` 한 파일 — 차례로)
- [x] T08-2.01 `argument-hint` 에 `--auto` 를 더하고 절차 0 에 "인자가 없으면 지금과 같다 · `--auto` 는 subagent 방식 전제 · 사람 관문(요구 승인 · 계획 승인 · [DEEP] · 푸시 · 태그 · 의존성 · 권한 확대)은 넘지 않는다" 쓰기 (끝난 기준: `uv run python scripts/claude_check.py --check` 통과)
- [x] T08-2.02 자동 진행 고리 절 쓰기 — 다음 미완료 task 고르기 → 경로 → 구현자 표로 배치 → task 검토 고리 → 빠른 검사 → 체크 → 단계 관문 → 멈춤 조건까지 반복 (끝난 기준: 기존 절차 번호를 가리켜 다시 적지 않는다 · `claude_check` 통과)
- [x] T08-2.03 겹침 없는 묶음 병렬 배치 규칙 쓰기 — `task_batch.py` 출력대로 한 메시지에 동시 호출 · 같은 작업 트리 · 파일 분리 · 겹치면 차례로 · 겹침 판정 예시 2개(겹침 / 안 겹침) · 동시 수는 `--max` (끝난 기준: 예시가 1단계 테스트 입력과 같은 모양 · `claude_check` 통과)
- [x] T08-2.04 멈춤 조건 질문 모으기 쓰기 — 질문은 main 만 한다(하위 에이전트에서는 사용자 질문 도구가 늘 빠짐) · 한 번에 모아 묻기 · 기다리는 동안 독립 task 계속 · 푸시는 모아서 묻기 (끝난 기준: 7-1 표에 "사람 판단 포인트 모음" 행 · `claude_check` 통과)
- [x] T08-2.05 안전장치 절 쓰기 — 상한 표 3종(값은 plan §11.4 초안, 사용자 확정 뒤) · 시작 BASE 를 원장 첫 줄에 · 상한에 걸리면 멈춤 조건 · 전체 check 중에는 구현자 · 무거운 배경 작업을 새로 띄우지 않음(plan §11.1 '관문 중 부하') · 멈출 때 보고 내용(BASE · 브랜치 단위로 되돌리는 명령 · 마지막 실패) (끝난 기준: 상한 표가 저장소에서 이 값이 적힌 유일한 곳 · `claude_check` 통과)
- [x] T08-2.06 재개 절 쓰기 — 정본은 tasks 의 체크와 git 기록 · 원장은 보조 · 새 세션은 `task_batch.py` 출력으로 체크된 task 를 건너뜀 · 원장이 없으면 `git log` 로 BASE 찾기 (끝난 기준: 재개 순서가 명령 3줄 이내 · `claude_check` 통과)
- [x] T08-2.07 병렬 위임 규칙 한 줄 쓰기 — 분석 · 조사 · 검토 요청은 배경 읽기 전용 에이전트에, main 은 진행 중 task 를 계속, 정해진 다음 task 는 묻지 않음 (끝난 기준: 같은 문장이 4단계 agents README · agents.md 에도 들어갈 수 있게 한 줄로 · `claude_check` 통과) — 2026-11-05 2.01~2.07: 커밋 cca7d63 · a6070f2 · 7d37532 · task 검토(opus) 치명 2 · 중요 6 → 고치기 2회 · 재검토 2회 처리됨 · test_task_batch 11 · claude_check · docs_index 통과 · 되돌리기 · 보류 명령은 임시 브랜치 실측

**단계 관문**: `python nova.py quick --stage T08-2` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 3단계 · `/sdd` · `/session-start` 연결 (`sdd.md` · `session-start.md`)
- [x] T08-3.01 `sdd.md` 지금 단계 표의 "`- [ ]` 가 있는 계획" 행에 `/task-run --auto` 로 이어 갈 수 있다고 한 줄 더하기 (끝난 기준: 승인 관문 건너뛰기 금지 문장은 그대로 · `claude_check` 통과)
- [x] T08-3.02 `session-start.md` 에 4-2 추가 — 열린 자동 진행 알림: 원장(`.superpowers/sdd/<계획>/`)이 있거나 tasks 에 `- [ ]` 가 남은 계획이면 `task_batch.py` 출력으로 "이어 가려면 같은 명령" 한 줄 (끝난 기준: 원장이 없어도 tasks 체크만으로 안내 · `claude_check` 통과)
- [x] T08-3.03 `session-start.md` 5단계 요약에 열린 자동 진행 한 줄을 넣고 worktree 절(6-1)과 충돌하지 않는지 읽어 확인 (끝난 기준: worktree 안에서는 번호 기록을 쓰지 않는다는 문장 유지 · `claude_check` · `docs_index` 통과) — 2026-11-05 3.01~3.03: 커밋 b3d66e6 · claude_check · docs_index 통과 · 묶음 검토 요구 ✅

**단계 관문**: `python nova.py quick --stage T08-3` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 4단계 · 에이전트 규약 문서 · 단일 원천 테스트 (선행: T08-1.01 병합 확인)
- [x] T08-4.01 에이전트 README 부르는 규칙 1 을 사실대로 고치기 — 하위 에이전트는 기본 3층까지 부를 수 있으나 Nova 는 정의 `tools` 에 Agent 를 넣지 않아 일부러 막고, 사용자 질문 도구는 하위 에이전트에서 늘 빠진다 (끝난 기준: "못 부른다"를 플랫폼 제한처럼 쓴 문장이 없다 · 편제표(생성물)는 손대지 않음 · `claude_check` 통과)
- [x] T08-4.02 에이전트 README 부르는 규칙에 병렬 위임 한 줄(T08-2.07 문장)을 더하고 규칙 2 의 병렬 자리에 `/task-run --auto` 겹침 없는 구현을 더하기 (끝난 기준: 규칙 번호 뒤섞임 없음 · `claude_check` 통과)
- [x] T08-4.03 `agents.md` §1 · §2 표의 "못 한다"를 같은 사실로 고치고 §3 의 고치기 상한을 task-run 상한 표 참조로 바꾸기 (끝난 기준: §3 에 상한 숫자가 새로 적히지 않는다 · `docs_index` 통과)
- [x] T08-4.04 `agents.md` §5 병렬 표 "서로 다른 파일을 고치는 구현" 행을 task-run 겹침 판정 참조로 바꾸고 새 절 "무인 허용 목록 제안" 쓰기 (읽기 · 검사 명령 허용 · 되돌리기 어려운 것은 ask 유지 · 명령 + 하위명령 정확 일치 · 접두 일괄 허용 금지 · 적용은 [DEEP] 따로 승인 · settings.json 은 그대로 — 끝난 기준: `docs_index` 통과)
- [x] T08-4.05 `superpowers.md` §4.1 · §5 에 `--auto` 와 상한 참조 한 줄, 권한 확대 항목에 "무인 허용 목록 적용도 권한 확대" 더하기 (끝난 기준: §2.1 지도의 `/task-run` 설명과 맞다 · `docs_index` 통과)
- [x] T08-4.06 상한 값이 task-run 한 곳에만 있는지 지키기 (`tests/test_task_batch.py::test_limits_single_source` — task-run 상한 표의 항목 이름이 다른 규약 문서 · 명령 문서에 숫자와 함께 나오면 실패)
- [x] T08-4.07 무인 허용 목록이 접두 일괄 허용으로 새지 않게 지키기 (`tests/test_task_batch.py::test_settings_has_no_blanket_allow` — `.claude/settings.json` permissions.allow 에 `python nova.py` 접두 일괄 · push · tag 허용이 없다) — 2026-11-05 4.01~4.07: 커밋 875cfaf · 4c2e662 · test_task_batch 13 통과 · 묶음 검토 중요 2(테스트가 일부만 지킴) 고침 · 재검토 3건 처리됨

**단계 관문**: `python nova.py quick --stage T08-4` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 5단계 · 견본 계획 · 종료 조건 E3~E5 시험 (견본은 `tests/fixtures/auto_trial/` — docs 밖이라 인덱스 · 한글 검사 대상이 아님)
- [ ] T08-5.01 견본 계획 4 task 만들기 (`tests/fixtures/auto_trial/` 에 `plan_REQ_99.md` · `tasks_REQ_99.md` — 가 `trial/a.py` · 나 `trial/b.py` 는 겹치지 않고 다 · 라는 둘 다 `trial/shared.py` 를 고쳐 겹치며, 다 앞에 사람 판단 자리 1곳(미결 질문 1개)을 둔다 · 끝난 기준: `uv run python scripts/task_batch.py tests/fixtures/auto_trial/tasks_REQ_99.md --max 3` 의 첫 묶음이 가 · 나)
- [ ] T08-5.02 E3 의 배치 모양을 기계로 확인하기 (`tests/test_task_batch.py::test_trial_batches_shape` — 첫 묶음 {가, 나} · 다음 {다} · 그다음 {라} 로 겹치는 둘은 차례)
- [ ] T08-5.03 E4 의 재개를 기계로 확인하기 (`tests/test_task_batch.py::test_trial_resume_skips_checked` — 가 · 나를 체크한 사본에서 다음 묶음은 {다} 이고 가 · 나는 0번 나온다)
- [ ] T08-5.04 E5 용 변형 견본 만들기 — 라를 서로 모순된 단정 두 개를 요구하는 task 로 바꾼 `tasks_REQ_99_stuck.md` (끝난 기준: `tests/test_task_batch.py::test_trial_stuck_variant_same_shape` — 배치 모양은 5.02 와 같고 변형이라는 표시가 본문에 있다)
- [ ] T08-5.05 사람 시험 절차를 `tests/fixtures/auto_trial/README.md` 에 쓰기 — 어디에 두나(별도 작업 폴더 `git worktree add ..\Nova-trial -b trial/auto-run` 에 견본을 `docs/plans` 아래로 복사) · 시작 · 세션 끊기 · 이어 가기 · 지우기(`git worktree remove --force ..\Nova-trial` → `git branch -D trial/auto-run` → `.superpowers/sdd/tasks_REQ_99` 지우기 → `git worktree list` · `git status` 로 흔적 없음 확인) (끝난 기준: 적은 명령을 실제로 한 번 돌려 새로 생긴 파일까지 지워지는 것을 확인 — CLAUDE.md 규칙 10 · `docs_index` 통과)
- [ ] T08-5.06 사람 시험 E3 · E4 · E5 를 실행하고 요구 문서 종료 조건 판정 칸에 `충족 YYYY-MM-DD` 적기 (사전: 구현자 · 검토자 8회 이상 호출이라 크기를 먼저 말하고 사용자 확인 · 끝난 기준: `python nova.py exit-check REQ-261105-09` 가 E1~E5 모두 녹색)

**단계 관문**: `python nova.py quick --stage T08-5` → 전체 `python nova.py check` → 커밋 묶음 · 푸시 · `git_record.py`(main)

## 작업 중 발견 (단계와 별개)
- [ ] 🆕 T08-9.01 (판정: 다음 판본 — 새 요구 후보 · 이번 계획의 종료 조건을 깨지 않음, 재실행 녹색) 전체 check 중 하위 프로세스가 원인 없이 비정상 종료한다 — 2026-11-05 두 번: `validate_infra.py` 0xC0000409(1단계 관문 · 단독 재실행 2회 통과 · 인프라 변경 0) · `nova_common.migrate` 0xC0000005(🆕 T04-9.14) · 기대: 긴 check 에서도 결정적 · 조사 후보: 같은 시각 동시 프로세스 수 · uv 파이썬 3.12 바이너리 · 백신 실시간 검사 · 자동 진행(`--auto`)이 이 실패를 '진짜 실패'로 보고 멈추지 않게 하는 재시도 규칙은 만들지 않는다(빨강은 원인부터) · 환경: Windows 11 · `nova.py check`
