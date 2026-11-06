---
name: nova-ui-verify
description: Nova 화면을 실제로 띄워 눈으로 확인한다 — "화면 확인해줘", "스크린샷 찍어줘", "목업 PNG 만들어줘", "UI 고친 뒤 회귀 확인", "다크 모드 확인", "모바일 화면 PNG" 때 쓴다. doctor 점검 → 목업이면 mockups, 웹이면 stack up(게이트웨이 + 데모 로그인 웹) → ui-smoke → stack down, 체크리스트 폼이면 checklist-smoke, 모바일이면 kmp-snapshots 를 돌리고 PNG 를 직접 읽어 판정한다.
---

# nova-ui-verify — 초록은 종료 코드 0 + 콘솔 오류 0 + 눈으로 본 PNG

테스트가 통과해도 화면이 비어 있을 수 있다. 이 스킬은 **실제로 띄워서 본다.** 무엇을 고쳤는지에 따라 표면을 고른다.

## 0. 점검
`python nova.py doctor` — node · npm · java(JAVA_HOME) · Playwright 가 있는가. 없는 표면은 "판정 불가(무엇이 있으면 되는지)"로 보고한다.

## 1. 표면 고르기(이 절차 전체를 `e2e-tester` 에이전트에 맡길 수 있다)
| 바꾼 것 | 표면 | 명령 |
|---|---|---|
| 계획의 화면 목업 | 목업 PNG | `python nova.py mockups [파일]` |
| 웹 화면 · `@nova/ui` | 웹 앱 | 아래 2 |
| 체크리스트 폼 | 폼 | `python nova.py checklist-smoke` |
| 모바일 · `kr.nova.uikit` | KMP | `python nova.py kmp-test` · `kmp-build` · (`stack up --no-web` 뒤) `kmp-snapshots` |
| 토큰 | 전부 | `python nova.py tokens` 뒤 위 표면 중 바뀐 것 + 다크 모드 |

## 2. 웹 앱 순서 (`scripts/ui_smoke.py` 머리말이 정본)
1. `python nova.py stack up` — 게이트웨이(메모리 DB) + 데모 로그인 웹 빌드 · 기동. 빈 포트를 스스로 고르고(8080 · 3100 부터) 주소를 `.stack/state.json` 에 적는다. 지난 빌드를 다시 쓰려면 `--no-build`(주소가 같을 때만)
2. `python nova.py ui-smoke` → 캡처 `docs/screenshots/app-*.png` (주소는 stack 에서 읽는다 · 캡처가 바뀌면 체크리스트 폼 · 출고본을 다시 만든다)
3. `python nova.py stack down` — 자식 프로세스까지 내리고 포트가 비었는지 확인(남은 것이 있으면 종료 1)
4. 모바일도 같은 스택에 붙는다 — `kmp-smoke` · `kmp-snapshots` 가 stack 주소를 `-Papi` 로 넘긴다(`NOVA_API` 가 있으면 그것)

## 3. 이 PC 의 함정
- **3000 · 8080 포트는 다른 프로그램이 쓸 때가 있다** → `stack up` 이 다음 빈 포트를 고르고 `GW_CORS_ORIGINS` 를 맞춘다(손으로 띄우면 이 둘을 직접 맞춰야 한다)
- **데모 로그인 버튼은 `NEXT_PUBLIC_DEV_LOGIN=1` 빌드에만** 있다 — 없으면 스모크가 로그인에서 멈춘다
- **JAVA_HOME** 을 명령마다 지정(JDK 21 — CLAUDE.md '이 PC 환경')
- 무거운 테스트(`python nova.py test`)와 동시에 돌리면 시간 초과가 난다 — 순서대로
- 그 밖의 함정은 [references/gotchas.md](references/gotchas.md)

## 4. 판정
- **초록** = 스크립트 종료 코드 0 **그리고** 콘솔 · 페이지 오류 0 **그리고** PNG 를 Read 로 직접 열어 빈 화면 · 겹침 · 잘림 · 다크 대비가 없음
- 하나라도 아니면 빨강 — 다시 돌려 초록을 만들지 않는다(원인부터 `/debug`)
- 보고: 돌린 명령 · 단계 수 · 본 PNG 이름 · 발견(심각도 0~4, ux-heuristics)

## 하지 않는 것
- 캡처를 손으로 고치거나 지난 PNG 로 대신하기
- 확인 안 한 표면을 "통과"라고 쓰기 — "안 봤다"로 쓴다
