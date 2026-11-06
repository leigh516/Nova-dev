---
description: 상류 판본 받기 — Nova 로 만든 프로젝트(복제본)가 Nova 의 새 판본에서 공통부(공통 라이브러리 · 스크립트 · 명령 · 스킬 · 에이전트 · 규약)를 3-way 판정으로 받는다
argument-hint: <Nova 태그 예: v0.2.0>
---

# /sync-upstream — 상류 판본 받기

인자: `$ARGUMENTS`
규칙: [ADR-009](../../docs/adr/ADR-009-commands-skills-agents.md) · 공통부 목록의 정본은 `scripts/upstream.py` 의 상수 하나다

플랫폼 개선은 Nova 에서 하고, 프로젝트는 그 판본을 **받는다**. 이 명령은 그 받는 길이다. Nova 저장소 자신에서는 쓰지 않는다(상류가 아니라 원천).

## 절차
1. **본 작업 트리(main)에서** 실행한다. 커밋 안 된 변경이 있으면 먼저 커밋한다
2. `python nova.py upstream status` — 상류 주소 · 내가 갈라진 기준(base · tag) · 최신 정식 태그 · 그 사이 판본 수를 확인한다. 없으면 `nova.project.json` 의 `upstream` 을 채운다(`{"url": …, "base": …, "tag": …}`)
3. **후보 보기** — `python nova.py upstream tags`: 상류의 정식 태그 목록과 내 기준 판본(사전 판본 rc 는 빠진다)
4. **판본 고르기** — 받을 판본(태그)은 **사람이 고른다. 최신을 자동으로 고르지 않는다**(도구도 인자로만 받는다). Nova 의 릴리스 노트(`docs/releases/v<버전>.md`)에서 '복제본이 받을 때' · 되돌리기를 먼저 읽는다. 정식 태그가 아닌 대상(rc · 브랜치 · 커밋)은 `--allow-ref` 를 붙일 때만 받는다 — 번호 규칙은 Nova 의 `docs/conventions/versioning.md`
5. **plan** — `python nova.py upstream plan <태그>`: 파일마다 판정(아무것도 쓰지 않는다). 내 기준과 대상 사이에 **건너뛰는 판본**이 있으면 판본마다 노트의 '복제본이 받을 때' 절을 함께 보인다 — 사용자에게 그대로 보여 주고 확인한다
   | 판정 | 뜻 | 처리 |
   |---|---|---|
   | replace | 내가 안 고쳤고 상류가 바꿨다 | 받는다 |
   | already | 이미 같다 | 그대로 |
   | add | 상류에 새로 생겼다 | 받는다 |
   | skip | 내 프로젝트가 만든 것 | 건드리지 않는다 |
   | surface | 양쪽이 다 바꿨거나 상류가 지웠다 | **사람이 판정** |
5-1. surface 가 하나라도 있으면 **멈춘다**(도구가 적용을 거부한다). 파일마다 사용자에게 보여 준다
   - 내 변경을 버리고 상류를 받는다
   - 내 변경을 Nova 로 역제안한다(Nova 저장소에 `/issue --kind change`)
   - 이번에는 그 파일을 받지 않는다
   정한 뒤 손으로 맞추고 다시 `plan`
6. **apply** — 사용자 승인 뒤 `python nova.py upstream apply <태그>` — 덮어쓸 파일 스냅샷(`docs/releases/upstream/<시각>/`) · 적용 · `upstream.base` · `upstream.tag` 갱신 · 채택 기록(`docs/releases/adoption.json`)
6-1. **옛 평면 에이전트 파일 정리**(Nova 가 에이전트를 폴더형으로 바꾼 판본을 처음 받을 때 — ADR-010): 상류는 `.claude/agents/<이름>.md` 를 지우고 `.claude/agents/<폴더>/<이름>.md` 를 새로 만든다. 판정은 옛 파일을 surface(상류가 지움)로 올리므로, 내가 고치지 않은 옛 파일은 지우고(`git rm`), 고친 것은 새 폴더 파일에 옮겨 맞춘 뒤 지운다. 같은 `name` 이 두 곳에 남으면 Claude Code 가 하나만 싣는다 — `uv run python scripts/claude_check.py --check`(A2 이름 중복 · A18 위치)로 확인한다. 팩 에이전트는 `uv run python scripts/packs.py agent <팩>` 으로 `domain/` 에 다시 만든다
7. `python nova.py install`(의존성이 바뀌었으면) → `python nova.py check`. 빨강이면 스냅샷으로 되돌리고 원인을 본다
8. `/history-new`(받은 판본 · 파일 수 · surface 처리) → 커밋 · `git_record.py`

## 하지 않는 것
- 프로젝트 소유 파일(서비스 · 문서 기록 · `nova.project.json` · `services.json` · 토큰 값)을 상류로 덮기 — 목록 밖은 판정 대상이 아니다
- surface 를 자동으로 고르기
- 받을 판본을 '최신'으로 자동으로 고르기 — 건너뛰는 판본의 '복제본이 받을 때'를 사람이 읽고 고른다
