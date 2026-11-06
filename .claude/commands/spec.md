---
description: SPEC — 승인된 PRD 와 foundation 으로 서비스 · 데이터 모델 · API · 이벤트 · 화면 · 테스트 맵을 docs/product/spec.json 에 쓰고 승인 후 출고(spec · DDL)
argument-hint: (선택) 범위 · 기능 ID
---

# /spec — 기술 명세 만들기

인자: `$ARGUMENTS`
규약: [docs/product/README.md](../../docs/product/README.md)

## 입력 게이트
- `prd.json` 이 `status: "승인"` 이다
- `spec.json` `foundation` 이 채워져 있다(`/foundation`). 없으면 먼저 `/foundation`
- `spec.json` 의 `prd_version` 이 PRD `version` 과 같다. PRD 가 바뀌었으면 바뀐 기능부터 다시 맞춘다

## 절차
1. **영향 조회**(새 프로젝트가 아니면): 대장 4종을 먼저 본다 — [화면](../../docs/registry/screens.md) · [DB 사전](../../docs/registry/db-dictionary.md) · [권한](../../docs/registry/permissions.md) · [이벤트](../../docs/registry/events.md). 이미 있는 표 · API · 화면은 새로 만들지 않고 재사용한다
2. 채운다(기능 ID 로 PRD 와 잇는다 — 서비스 · 데이터 모델 · API · 이벤트 · 화면 골격 초안은 `api-designer`(API · 이벤트) · `database-architect`(데이터 모델) · `screen-architect`(화면) 에이전트를 한 메시지에 함께 맡겨도 된다. 새 이름은 `registry-keeper` 로 먼저 조회)
   - `services`: 이름(영문 소문자) · 그룹 · 책임 · 맡은 기능. 모듈러 모놀리스면 서비스 1~2개에 모듈 경계를 책임 칸에 적는다
   - `data_model`: 표(snake_case) · 서비스(서비스는 자기 DB 만) · 의미 · 칸(`type` · `nullable` · **`comment` 필수** · 다른 표를 가리키면 `ref`). `id` · `tenant_id` 는 쓰지 않는다(자동)
   - `api`: `API-01`… · 메서드 · 경로(`/v1/…`) · 서비스 · **권한 `<모듈>.<행위>`** · 기능 · 요청 · 응답 · 오류 코드. 목록은 paging 계약, 서버 쓰기 버튼은 useAction 전제
   - `events`: 서비스 사이 변화는 이벤트(아웃박스) — 토픽 `<도메인>.<개체>.<과거형>` · 발행 · 구독 · 내용
   - `screens`: `S-01`… · 이름 · 앱 · 경로 · 템플릿(ListPage · DetailPage · FormPage …) · 기능
   - `test_map`: PRD 수용 기준마다 테스트 하나(경로::이름 또는 `ui-smoke` 단계). 이 표가 `/task-run` 의 실패 테스트 목록이 된다
   - `open_questions`
3. `uv run python scripts/warehouse.py check` 통과까지 고친다. 승인 상태에서는 모든 PRD 기능이 API 나 화면을 가져야 하고, 모든 수용 기준이 테스트 맵에 있어야 한다
4-0. **체크리스트의 화면 결정을 먼저 반영한다** — 완료본 `checklist_*.md` 의 '목업 · 기존 화면 채택' · '화면 부품' · '디자인 결정'
   - **'그대로 채택'한 목업은 화면 배치 · 기능의 근거**다. `screens` 에 그 목업 경로를 적고, 목업에 없는 화면만 새로 설계한다
   - 목업의 색 · 글꼴은 `mockup.design` 답에 따라 토큰으로 옮긴다(화면에 색 코드를 직접 쓰지 않는다)
   - '화면 부품'에서 고른 Nova 부품은 `screens.template` 으로 쓰고, 'Nova 에 없는 부품'은 task 로 만든다. `parts.source` 답대로 공통 부품으로 만들거나 외부 부품을 들이고, 외부 부품은 라이선스를 확인한다
4-0. 채택한 목업이 있으면 `mockup-analyst` 로 화면 · 부품을 대응시키고, Nova 에 없는 부품은 `design-asset-keeper`(있는 것으로 조립 · 새 부품 후보) · `design-researcher`(밖의 형), 디자인 값이 정본과 다르면 `design-rule-architect` 로 본다
4. 화면이 있으면 핵심 화면 1~3개를 목업으로 만든다(`docs/plans/mockups/REQ_NN/*.html` → `python nova.py mockups`). 목업은 [ux-heuristics](../../docs/conventions/ux-heuristics.md) H1~H10 으로 점검하고, 필요한 것은 `outbound/html-mockup/` 에 복사한다
5. **빌더 점검**: `req-analyst` 에이전트(빌더 점검 모드)에게 `prd.json` · `spec.json` 경로만 주고 "이것만으로 계획 · 구현을 할 수 있나"를 묻는다. 셋으로 나눈다(이미 답 있음 / 사소함 → Claude 판단 / 고객 몫 → 한 번에 모아 질문)
6. `uv run python scripts/warehouse.py out` → `outbound/spec/spec.md` · `spec.html` · `spec.json`, `outbound/db-sql/schema.sql` · `rollback.sql`(초안 — 실행 DB 에 자동 적용하지 않는다)
7. **승인 관문**: 사용자가 승인하면 `status: "승인"` · `approved` 를 채우고 다시 `out`
8. **구체화로 넘기기**(승인 뒤)
   - 서비스: `python nova.py new-service <이름> --group <그룹> --scope <범위>` (spec `services` 마다)
   - 역할 · 권한: `services/gateway/gateway/rbac.json` 에 역할 먼저
   - 계획: 기능 묶음마다 `/req-new` → `/plan-new "<제목>" REQ-…`. 계획 §0 · §7 은 spec 의 표 · API 를 가져다 쓰고, §11.1 전역 제약에는 foundation 결정을 적는다. task 의 실패 테스트는 `test_map` 에서 가져온다
   - 마스터플랜: 계획 묶음 순서를 `docs/plans/drafts/` 초안으로 → 사용자 확인 후 채택
   - 생성물 원장: 서비스 · 표 · 화면을 만들면 `registry.py sync` · `ledgers.py`
9. 보고: spec 경로(html), 서비스 · 표 · API · 화면 · 테스트 수, Claude 판단 목록, 다음 명령
