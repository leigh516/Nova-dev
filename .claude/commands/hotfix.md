---
description: P0 긴급 수정 — 재현 회귀 테스트로 RED 를 먼저 확인한 뒤 최소 수정 → 검사 → 패치 릴리스 → 사후기록 → 종결. 급할수록 순서를 지킨다
argument-hint: <ISS-ID> [증상 한 줄]
---

# /hotfix — P0 긴급 수정(재현 테스트 먼저)

인자: `$ARGUMENTS`

재현 테스트 없이 고치면 그 장애가 다시 났는지 영원히 알 수 없다. 이 명령은 RED 를 확인하기 전에 수정 단계로 넘어가지 않는다.

## 들어가는 조건
- [/issue](issue.md) 로 **P0 으로 접수된 ISS** 가 있다(`python nova.py issue show <ISS-ID>`). 접수 없이 시작하지 않는다 — 나중에 무엇이 있었는지 재구성할 수 없다
- 본 작업 트리(main)에서 한다(원장 쓰기 — 단일 기록자)
- `python nova.py issue set <ISS-ID> --status in_progress`

## 절차(순서를 바꾸지 않는다)
1. **재현 테스트 먼저(RED)** — `superpowers:test-driven-development`
   - 접수된 재현 절차를 실행할 수 있는 회귀 테스트로 옮긴다(`tests/…` 또는 서비스 테스트)
   - 돌려서 **실패를 눈으로 확인한다**: `uv run pytest <파일>::<테스트> -q`
   - 여기서 통과해 버리면 **멈춘다** — 재현 절차가 모자라거나 · 환경이 다르거나 · 이미 고쳐졌다. 셋 중 무엇인지 가리기 전에 고치지 않는다(필요하면 [/debug](debug.md))
1-1. 재현 · 근본 원인 · 최소 수정은 `incident-responder` 에이전트에 맡길 수 있다(RED 먼저 — 커밋 · 기록 · 패치 릴리스는 main)
2. **최소 수정(GREEN)** — 문제를 푸는 최소 코드만. 급할 때 리팩터링을 끼워 넣지 않는다(되돌릴 범위가 넓어진다). 1의 테스트가 통과하는지 본다
3. **회귀 확인** — `python nova.py check`(test + lint 병렬). 출력의 통과 숫자를 증거로 남긴다
4. **패치 릴리스** — [/release](release.md) 로 patch 판본(예: 0.1.0 → 0.1.1). 노트의 **되돌리기** 절을 반드시 채운다
5. **사후기록(24시간 안)** — [/postmortem](postmortem.md) → 재발방지는 [/learn](learn.md) 으로
6. **종결**
   ```bash
   python nova.py issue set <ISS-ID> --status closed \
     --repro-test "tests/<파일>.py::<테스트이름>" \
     --postmortem "docs/issues/postmortem/<YYYY-MM-DD-주제>.md"
   ```
   둘 중 하나라도 없거나 파일이 실재하지 않으면 **거부된다** — 1 · 5단계를 건너뛸 수 없게 하는 장치다
7. 기록 — `/history-new` · 커밋 뒤 `git_record.py`

## 규칙
- 순서 불변: RED → 최소 수정 → 회귀 → 릴리스 → 사후기록 → 종결
- P0 수정 커밋에 관계없는 변경을 섞지 않는다(되돌릴 대상이 흐려진다)
- 오류 코드를 보고 원인이 떠올라도 최소 탐침으로 먼저 시험한다 — 처방이 있다는 것이 내 원인이 그것이라는 뜻은 아니다
- 증거 없이 "됐다" 고 하지 않는다(명령 출력으로)
