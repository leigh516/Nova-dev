# 출구 — 없는 것이 필요할 때 Nova 의 어디로 가나

원본 psg05 는 출구를 BACKLOG(갭 · 대체) · 제안 원장(체계 변경) 둘로 나눴다. Nova 에는 그 원장이 없고, 같은 갈래가 아래 자리로 간다. 🔴 **갈래를 섞지 않는다** — "있는데 밖이 더 낫다(대체)"를 "없다(갭)"로 접수하면 원래 없던 것이 된다.

| 상황 | 가는 곳 | 갖춰야 할 것 | 부르는 에이전트 |
|---|---|---|---|
| **없는 부품**(탭바 · 폼 모달 · 밀러 칼럼 · AI 확인 카드 …) | `docs/conventions/ui.md` §3 표에 🗺 행 + 계획에 🆕 task. 먼저 만든 프로젝트는 Nova 로 **역제안** | 쓸 화면이 실제로 있다는 근거(화면 대장 행 · 계획) · 웹 ↔ 모바일 대응 이름(ui.md §2-9) | `design-asset-keeper` |
| **없는 템플릿**(골격 B 스플릿 · 골격 C 설정형) | `web/packages/ui/src/templates/` + ui.md §5 행 — 화면보다 먼저 | 이 골격을 쓸 화면 둘 이상(§2-2 두 번 나오면 올린다) | `design-asset-keeper` · 화면 배정은 `screen-architect` |
| **없는 토큰**(style-map 갭 G1~G8) | `design/tokens/brand.tokens.json` 에 **의미 토큰** 추가 → `python nova.py tokens`(라이트 · 다크 대비 자동 검사) → 사람 승인 | 역할 이름 · 두 모드 값 · 대비 검사 쌍(`contrast`) · 소비처 | `design-rule-architect` 가 변경안, `design-token-guardian` 이 화면 쪽 하드코딩 감시 |
| **있는데 밖이 더 낫다**(대체 — 부품 하나) | 새 요구로(`/req-new`) — 같은 부품을 고치는 변경이므로 영향 조회 후 `/change` | 근거 하나 이상: 측정값 · 대조(나란히 찍은 PNG) · 다른 프로젝트 채택 이력. **근거 없는 선호는 받지 않는다** | `design-asset-keeper` |
| **디자인 시스템 규칙 · 구조 변경**(형 축 G1 · 의미 반경 도입 · 셸 설정 확장) | 되돌리기 어려운 구조 결정 → `docs/adr/`(`uv run python scripts/docs_new.py adr`) + 요구 · 계획 | 근거 · 증거 · 얻는 것 · 잃는 것 넷 — 사용자 결정 전 구현 금지 | `design-rule-architect` |
| **없는 권한 · 역할** | `services/gateway/gateway/rbac.json` 먼저 → `uv run python scripts/ledgers.py` → `docs/registry/permissions.md` 확인 | `<모듈>.<행위>` 이름(`python nova.py naming lookup` 으로 먼저 조회) | — |
| **없는 메뉴** | `services/gateway/gateway/menu.json` | 권한과 짝 | — |
| **AI 쓰기 기능**(L2) | 계획서 §0 에 STD-AX 등급 판정 + `require_human` 승인 경로 · 감사(`actor_type`) — 화면 카드(C9)와 서버 경로가 **둘 다** 있어야 낸다 | `nova.project.json` `standards` 판정 | — |

- 형(form)은 받고 체계는 받지 않는다 — 원본 `--neo-*` 같은 외부 변수 체계 · data-style 속성을 그대로 들이자는 것은 출구가 아니라 금지다. 형이 필요하면 G1 로 Nova 의 의미 토큰 이름을 새로 정한다
- 출구에 낸 갭은 화면을 막지 않는다 — **갭 없이 먼저 내고**(근사 행으로), 갭은 다음 판본으로 보낸다(CLAUDE.md "이번 일을 넓히지 않는다")
- 명령 절차 · 게이트 의미를 바꾸자는 것은 승인 없이 하지 않는다(IDENTITY 경계) — 요구로 남긴다
