---
description: 작업 마무리 — 증거로 완료를 확인하고 병합 · PR · 유지를 정한 뒤 기록한다(superpowers:verification-before-completion · finishing-a-development-branch)
argument-hint: [plan_REQ_NN]
---

# /finish — 작업 마무리

인자: `$ARGUMENTS`

## 절차
1. **검증**(`superpowers:verification-before-completion`): 아래를 지금 실행하고 출력을 확인한다. 출력 없이 "통과"라고 말하지 않는다. 출력이 길면 `tester`(실행 테스트) · `verifier`(lint 단계별) · 화면이면 `e2e-tester` 에이전트를 한 메시지에 함께 띄워 통과 · 실패 요약을 받는다
   - `python nova.py check`(test · lint 를 동시에 — 실패한 축 이름이 나온다). 마무리에서는 빠른 검사(`quick`)로 대신하지 않는다
   - 요구의 종료 조건 `python nova.py exit-check REQ-…` — 모두 녹색이어야 끝이다
   - 화면을 바꿨으면 `nova-ui-verify` 스킬(`web-build` · `ui-smoke`), 모바일이면 `kmp-test`
   - tasks 에 `- [ ]` 가 남았는지, 남았으면 이유(🆕 · 보류)를 적었는지
2. **마무리**(`superpowers:finishing-a-development-branch`): 기준 브랜치를 확인하고 사용자에게 고르게 한다 — ① 로컬에서 기준 브랜치에 병합 ② 푸시 후 PR ③ 브랜치 유지. 혼자 하는 초기 단계는 `main` 직접 커밋도 된다([git.md](../../docs/conventions/git.md)). 작업 폴더(worktree)를 썼으면 커밋 안 된 파일이 없는지 확인하고 정리한다
3. **기록**: `/docs-write` — 등급으로 기록 하한을 정하고(`python nova.py docs-write grade`) 요구 · 이력 · tasks 3갈래 · 판본 노트 · git 기록까지 한다. 요구 상태(완료 · 적용됨) · 계획 진척 · 마스터플랜 체크를 갱신한다
4. 다시 날 수 있는 함정을 겪었으면 `/learn`
5. 컨텍스트를 많이 썼으면 `/session-end`
