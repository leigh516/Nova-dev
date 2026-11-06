# 도메인 팩 (STD-DOMAIN-PACK-001)

같은 제품을 여러 업종 · 고객군에 내보낼 때, **업종 특성은 여기(팩)** 에 두고 코어(services · packages)는 그대로 둔다. 표준: [docs/std/STD-DOMAIN-PACK-001](../docs/std/STD-DOMAIN-PACK-001.md)

```
packs/<팩>/
  pack.json            이름 · 설명 · 확장하는 서비스 · 가변점 목록
  glossary.md          ① 용어 오버레이 — 이 업종에서 부르는 이름
  policies/<서비스패키지>.py   ③ 규칙 — 코어 포트(@packs.port) 구현(@implement)
  schema/<서비스패키지>.py     ② 데이터 — 확장 표 <팩>_<개체>_ext (코어 표에 컬럼 추가 금지) — 🗺 규약(읽는 구현은 첫 사용 시, 이름 lint 만 있음)
  screens.json         ④ 화면 — 추가 컬럼 · 라벨 오버레이 — 🗺 규약
  workflows/*.json     ⑤ 프로세스 — 단계 · 승인 정의 — 🗺 규약
```
- 켜기: `nova.project.json` 의 `"packs": ["<팩>"]` → 생성기가 `NOVA_PACKS` 로 배포 · 개발 서버에 넣는다. 서비스는 기동 때 `policies/<서비스패키지>.py` 를 불러온다
- 만들기: `python nova.py new-pack <팩> --title "<이름>" --extends <서비스>`
- 의존 방향: **팩 → 코어 → 플랫폼** 한 방향. 코어가 팩을 import 하거나 팩끼리 import 하면 `python nova.py lint`(`scripts/packs.py check`)가 실패
- `_template` 은 생성 원본, `example` 은 동작 예시(샘플 서비스의 이름 정규화 포트를 바꾼다)

## 도메인 에이전트 — 팩마다 업무를 아는 판정자 하나
- `python nova.py new-pack` 이 팩과 함께 `.claude/agents/domain/<팩>-specialist.md` 를 만든다(틀: `packs/_template/agent.md`). 기존 팩은 `uv run python scripts/packs.py agent <팩>` → `uv run python scripts/claude_check.py --write`
- 에이전트는 **지식을 베끼지 않는다** — 이 팩의 `glossary.md` · `policies/` · `workflows/` · `screens.json` · `pack.json` 과 개념 원장(`registry/entities.json` 의 layer pack)을 읽어 판정한다. 업무 지식은 팩에 채운다(단일 원천)
- 명령이 부르는 자리: `/req-analyze` 5-0 · `/plan-new` 0-2 · `/task-run` 5-1 · `/review-request` 2(켜진 팩이 있을 때)
- lint: 팩마다 짝 에이전트가 있어야 하고(`packs.py check`), 짝 없는 `-specialist` 는 실패(`claude_check.py` A17). 읽기 전용 판정자다(쓰기 도구 없음)
