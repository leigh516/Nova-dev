---
description: 체계적 디버깅 — 원인을 찾기 전에는 고치지 않는다(superpowers:systematic-debugging)
argument-hint: <증상 · 오류 메시지 · 실패한 테스트>
---

# /debug — 체계적 디버깅

인자: `$ARGUMENTS`

## 절차
1. **스킬 호출**: `superpowers:systematic-debugging` 의 네 단계를 따른다 — 근본 원인 조사 → 패턴 분석 → 가설 검증 → 구현
1-1. **교훈부터**: `python nova.py learn find <증상 낱말>` — 같은 함정을 이미 겪었으면 그 규칙부터 본다(`docs/memo/lessons.md`)
2. 재현부터: 실패하는 명령 · 테스트를 정확히 다시 돌려 출력을 확보한다(`python nova.py test` · 서비스 테스트 · `ui-smoke`)
3. 이 저장소에서 먼저 의심할 곳(이전 이력에서 실제로 났던 일): 줄바꿈 CRLF · Windows 임시 폴더 권한(`.pytest_tmp`) · 환경 변수 누수(`NOVA_SKIP_LIFESPAN` 등) · 3000 포트 점유 · `uv sync` 중 실행 중인 서버 · 생성물 손수정(`lint --check`)
4. 가설은 한 번에 하나, 바꾸는 것도 하나. 확인 결과를 사용자에게 한국어로 짧게 보고한다
5. 고칠 때는 먼저 실패하는 회귀 테스트를 쓴다(`superpowers:test-driven-development`)
6. 세 번 고쳐도 안 되면 멈추고 구조 문제를 의심하며 사용자와 상의한다
7. 운영 결함이면 `/issue`(P0 는 `/hotfix`)로 원장에 남긴다. 노이즈가 큰 조사는 `debugger` 에이전트에 맡겨도 된다
8. 다시 날 수 있는 함정이면 `/learn` 으로 교훈 한 줄(트리거 → 규칙 · 근거 ID)
9. 원인 · 고친 곳 · 회귀 테스트를 history "발견 · 주의"에 남기고(`/history-new`), 다시 날 수 있는 함정이면 위 3번 목록과 CLAUDE.md "이 PC 환경"에 추가한다
