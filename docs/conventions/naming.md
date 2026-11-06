# 명명 규약 (표 · 칸 · 이벤트 · 권한 · API · 컴포넌트)

> 한 줄 요약: 이름은 센스로 짓지 않고 **공식으로 산출**한다. 서로를 모르는 두 세션(병렬 worktree)이 같은 개념에 **같은 이름**으로 도달해야 한다 — 안 되면 규약이 아니라 취향이다.

- 선언 정본(기계 입력): [`registry/naming.json`](../../registry/naming.json) — 형식 · 금지 축약 · 불규칙 과거형 · 예외 · baseline · 프로젝트 추가 형식
- 개념 원장: [`registry/entities.json`](../../registry/entities.json)(상태 — 생성물) · [`registry/entities.jsonl`](../../registry/entities.jsonl)(이력 — 추가 전용). 형식 결정 [ADR-004](../adr/ADR-004-ledger-formats.md)
- 검사: `python nova.py naming check`(lint 단계) · 조회: `python nova.py naming lookup <개념>`
- 이 문서의 **형식 표 구간**(맨 아래)은 `naming.json` 에서 생성한다 — 규칙을 바꾸려면 JSON 을 고치고 `python nova.py naming --write`(또는 `gen`)

## 1. 대원칙
1. **개체(명사)는 발명하지 않는다** — 새 표 · 개체를 만들기 전에 `python nova.py naming lookup <개념>`. 원장에 없는 개체는 존재하지 않는 개체다
2. **이름 공식**: `[개체] + [속성] + [타입 표지]` — 예: 항목의 만든 시각 → `created_at`(표 `item` 안), 보관 여부 → `is_archived`, 다른 서비스 회원을 가리키는 칸 → `member_id`
3. **층마다 하나** — 케이스 · 구분자 · 단수/복수를 대상마다 하나로 고정한다(아래 표). "둘 다 허용"은 규약이 아니다
4. **신규만 막는다** — 이 규약 이전의 위반은 `baseline` 에 이유와 함께 올리고, 고치면 지운다(check 가 "더 이상 위반 아님"을 실패로 알려 목록이 줄기만 한다). 만성 빨강은 꺼진 게이트와 같다

## 2. 개념 원장과 조회 — 5갈래
`lookup` 은 정규화(camel · 구분자 통일 → 복수 → 잡음 `master` · `tbl` · `마스터` 제거, `_log` · `_history` 같은 파생 표지는 **남김**) 뒤 원장의 키 · 표 · 별칭과 대조한다. 항상 종료 0(조회는 막지 않는다).

| 판정 | 뜻 | 처방 |
|---|---|---|
| 정확 | 같은 개체가 이미 있다 | **만들지 않는다** — 그 개체를 쓴다. 다른 서비스 개체면 `<개체>_id` 칸으로 가리킨다 |
| 별칭 | 같은 개념이 다른 이름으로 있다 | **만들지 않는다** — 정본 이름을 쓴다(이 사고를 막으려는 원장이다) |
| 유사 | 비슷하나 다를 수 있다 | 다른 개념이면 그 근거를 계획 §0 · §7 에 적고 진행 |
| 은퇴 | 전에 있었고 지금은 없다 | 복원인지 신설인지 **사람이 판정**(은퇴 사유가 재료) |
| 없음 | 새 개념 | **사람 승인 후** `python nova.py naming entity add <키> --title … --service … --table … --layer …` |

- 항목: `key · title_ko · service · table · layer(platform | core | pack) · pack · lookup_aliases · forbidden_aliases · status(active | deprecated | retired) · since · note`
- **층(layer)**: `platform` = nova_common 이 모든 서비스에 주는 것(`outbox` · `processed_event`, service `*`) · `core` = 서비스의 업무 개체 · `pack` = 도메인 팩 개체(`packs/<팩>/pack.json` `entities` 에도 적는다 — [STD-DOMAIN-PACK-001](../std/STD-DOMAIN-PACK-001.md))
- **금지 별칭**(`forbidden_aliases`): 그 개념을 이 말로 부르지 않는다 — 대장(표 · 칸 · 토픽 · 권한 · API · 컴포넌트) 이름의 마디로 쓰이면 check 실패
- **삭제는 묘비**: 지우지 않고 `naming retire <키> --why …`. 지우면 다음 조회가 '없음'을 내고 같은 개념이 다른 이름으로 다시 생긴다
- check 가 원장 ↔ 실물(DB 사전)을 양방향으로 본다: **좀비**(원장에만 있는 표) · **미등재**(실물에만 있는 업무 표) 모두 실패. 자동으로 은퇴시키지 않는다 — 판정은 사람
- 쓰기(entity · alias · retire · layer)는 **본 작업 트리(main)만**(단일 기록자 — [ADR-008](../adr/ADR-008-parallel-bus-release.md)). worktree 는 조회만 하고, 새 개념은 메시지 버스로 main 에 올린다
- `new-service` 는 템플릿의 첫 개체(`record`)를 `<패키지>_record` 로 자동 등재한다 — 업무 이름으로 바꾸면 `naming retire` 후 새 개체를 `entity add`
- 새 프로젝트(`new-project`)는 이 규약(`naming.json`)을 물려받고, 원장은 플랫폼 · 샘플 개념만 남겨 **이력을 새로** 시작한다(코어 개념의 금지 별칭은 비운다 — 새 프로젝트의 도메인어가 플랫폼의 금지어에 걸리지 않게)

## 3. 대상별 규칙

### 3.1 DB — 표 · 칸
- **표**: snake_case **단수**(`item` · `order_line`, `items` ✗). 도메인 접두는 **소유가 갈릴 때만**(한 서비스 DB 안에서 같은 낱말이 두 뜻일 때) — 서비스마다 DB 가 따로라 `<서비스>_<개체>` 접두는 기본으로 붙이지 않는다
- **기본키**: 단일 칸 `id` = `id_column()`(UUIDv7 CHAR(36) — [ADR-003](../adr/ADR-003-uuid-v7-ids.md)). 정수 일련번호 · 복합키 ✗. 사람이 읽는 업무 번호는 별도 `code` 칸(UNIQUE)
- **다른 개체를 가리키는 칸**: `<개체>_id` = `ref_column()`. **다른 서비스의 개체여도 같은 이름**이고 DB FK 는 걸지 않는다(서비스는 자기 DB 만 — [backend.md](backend.md) §2). 가리키는 개체 이름을 바꾸지 않는다(`dept_id` ✗ → `department_id`)
- **타입 표지**: 시각은 `<속성>_at`(DATETIME · UTC — `created_at` · `sent_at`, 맨 `at` ✗), 참거짓은 `is_` · `has_` · `can_`(`is_archived`). 반대로 `_at` 인데 시각이 아니거나 `is_` 인데 BOOLEAN 이 아니면 위반
- **감사 칸 4종**: `created_at · created_by · updated_at · updated_by`(템플릿이 준다). 테넌트 칸은 `tenant_id = tenant_column()`(손으로 선언하지 않는다 — [STD-TENANCY-001](../std/STD-TENANCY-001.md))
- **의미**: 모든 칸에 `comment=`(DB 사전의 '의미' 열)
- **팩 확장 표**: `<팩>_<개체>_ext`(같은 서비스 DB, 코어 표를 가리키는 칸은 `ref_column`). 코어 표에 업종 전용 칸 ✗

### 3.2 이벤트(토픽)
- **3단 `<서비스(밑줄) | platform>.<개체>.<과거형>`** — 일어난 사실(`sample.item.created`). 끝 마디는 `-ed` 또는 불규칙 과거형(`sent` · `paid` …)
- 첫 마디는 발행하는 서비스 이름(하이픈 → 밑줄) 또는 패키지 이름. 플랫폼 공통 사실만 `platform`
- **테넌트는 토픽에 넣지 않는다** — 봉투(`Envelope.tenant`)가 싣는다(토픽 폭증 방지 · STD-TENANCY-001 ④)
- 등재는 `infra/k3s/base/kafka-topics.txt`, f-string 토픽 금지(`tests/test_topic_catalog.py` — 형식 정규식은 `naming.json` 에서 읽는다)

### 3.3 권한
- **2단 `<모듈>.<행위>`** — 모듈 = `services.json` `perm`(없으면 서비스 이름) 또는 선언 모듈(`declared_permission_modules` — 예: 게이트웨이 운영 `ops`), 행위 = `read · create · update · delete`(HTTP 메서드에서 — 대장이 코드에서 파생), 모듈 전체 `<모듈>.*`, 전부 `*`
- 개체 단위 3단(`<모듈>.<개체>.<행위>`)은 쓰지 않는다 — 행위가 라우트 메서드에서 자동으로 정해지는 구조와 맞지 않는다

### 3.4 API
- 서비스 경로는 `/<서비스 경로>/<개체 복수>` 소문자 kebab, 자리표시는 `{snake}`(`/sample/items/{item_id}/archive`). 외부에는 게이트웨이가 `/v1` 을 붙인다 — 서비스 코드는 `/v1` 을 쓰지 않는다. 내부 API 는 `/internal/` 접두
- 요청 · 응답 키는 **칸 이름 그대로 snake_case**(기계 변환 · 손 개명 없음)
- 오류: `{"error": {"code": "<개체>_<사유>", "message": "…"}}` — code 는 snake_case(`item_not_found`), message 는 화면에 그대로 보일 한국어 문장
- 목록: `?page&size&sort&q` → `{items, total, page, size}`

### 3.5 화면 · 컴포넌트
- 컴포넌트는 PascalCase, 웹 ↔ 모바일 대응은 같은 개념 같은 이름([ui.md](ui.md) 9번). 훅은 `use*`, 함수는 camelCase, 상수는 UPPER_SNAKE
- 화면 이름 · 상태는 화면 머리 주석 `/** @screen 이름 · @status … */`, 화면 문구의 낱말은 [용어집](glossary.md)

### 3.6 서비스 · 범위 · 팩
- 서비스 `order-hub`(소문자 kebab — k8s · URL · DB 스키마), 파이썬 패키지는 하이픈 → 밑줄, 범위(scope) `ORDER`(대문자 2~16자), 팩 `pharma`(소문자 · 숫자 · 밑줄)

### 3.7 금지 축약
`emp` · `dept` · `org` · `usr` · `cust` · `prod` · `mgr` · `addr` 같은 **개체 축약**은 모든 식별자 마디에서 금지 — 낱말을 다 쓴다. 목록은 아래 생성 구간.

## 4. 이름 바꾸기 — Expand → Migrate → Contract
저장된 데이터 · 외부 소비자 · 이벤트 구독자가 있는 이름(표 · 칸 · 토픽 · 권한 · API 경로)을 바꾸는 것은 **L3**(되돌리기 어려움)이다.
1. `python nova.py impact <이름>` 으로 참조를 센다(개념 원장도 함께 본다) → 등급 판정(`contract-auditor`)
2. ADR 과 요구를 남긴다
3. **Expand**: 새 이름을 더한다(새 칸 · 새 토픽 · 새 경로) — 옛 이름과 함께 산다
4. **Migrate**: 데이터를 옮기고 쓰는 쪽을 새 이름으로 바꾼다(이벤트는 두 토픽 동시 발행 기간)
5. **Contract**: 옛 이름을 지운다 → `registry.py sync`(생성물 원장) · `naming retire`(개념 원장) · baseline 에서 지운다

## 5. 채택하지 않은 것 (project-start-guide-05 대비)
| psg05 | Nova | 이유 |
|---|---|---|
| 칸 접미사표 `_nm` · `_cd` · `_yn` · `_cnt` · `_amt` | 낱말을 다 쓴다(`name` · `code` · `is_…` · `count` · `amount`) | 축약 접미사는 그 자체가 금지 축약과 같은 문제(읽는 사람이 표를 외워야 함). 타입 표지는 `_at` · `is_` 두 가지만 고정 |
| JSON 필드 camelCase(snake ↔ camel 기계 변환) | 칸 이름 그대로 snake_case | 변환 계층이 하나 줄고, 대장(DB 사전)의 이름으로 API 를 바로 grep 한다. 웹 · 모바일 SDK 도 같은 키 |
| 경로 `/api/v1/…` | 게이트웨이 `/v1/<서비스 경로>` | 판본은 게이트웨이 한 곳이 붙인다 — 서비스는 판본을 모른다 |
| 오류 코드 대문자 `HR-404` · RFC 9457 | `{error:{code: snake, message}}` | 기존 계약([backend.md](backend.md) §5) · 화면 오류 표시가 이미 이 모양 — 바꾸면 L3 |
| 권한키 `{domain}:{entity}:{action}` | `<모듈>.<행위>` 2단 | 행위가 라우트 메서드에서 자동 파생되는 Nova 구조(권한 대장) |
| 테넌트 토픽 `tenant.{tid}.…` | 토픽에 넣지 않고 봉투로 | 토픽 수가 테넌트 수만큼 늘지 않게(STD-TENANCY-001) |

## 6. 강제력 — 어디서 무엇이 도나
| 자리 | 무엇 | 강도 |
|---|---|---|
| `/plan-new` 2단계 | `naming lookup <개념>` 결과를 계획 §0 · §7 에 인용 | 절차(읽어야 지켜진다) |
| `python nova.py lint` | `naming check` — 형식 · 금지 축약 · 금지 별칭 · 좀비 · 미등재 · 이 문서 생성 구간 최신 | **실패**(baseline · 예외만 통과) |
| `new-service` · `new-pack` | 이름 형식(같은 정규식) · 템플릿 개체 자동 등재 | 거절 |
| 원장 쓰기 | `require_main` — worktree 에서 거절 | 거절 |

## 7. 형식 표 (생성 구간)

<!-- naming:begin — 생성물: registry/naming.json 에서 `python nova.py naming --write` 가 만든다. 손으로 고치지 않는다 -->

### 형식 표

| 규칙 | 대상 | 형식 | 예 | 이유 |
|---|---|---|---|---|
| `table` | DB 표 | `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` | item · order_line · item_activity | snake_case 하나로 고정해야 SQL · ORM · 대장에서 같은 이름으로 찾힌다 |
| `table_singular` | DB 표(단수) | 아님 `(?<![su])s$` | item (items ✗) · status · address 는 단수 | 표는 개체 하나의 모양을 정의한다 — 복수 · 단수가 섞이면 같은 개념이 두 이름이 된다. 진짜 단수인 -s 낱말은 exceptions 에 이유와 함께 |
| `column` | 칸 | `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` | name · created_at · item_id | 표와 같은 snake_case — API 응답 키도 같은 이름(기계 변환 없음) |
| `column_datetime` | 시각 칸(DATETIME · TIMESTAMP) | `^[a-z][a-z0-9]*(_[a-z0-9]+)*_at$` | created_at · sent_at · archived_at | 타입 표지 _at 이 '시각(UTC)'을 뜻한다. 맨 'at' 은 무엇의 시각인지 없다 — <속성>_at. 반대로 _at 으로 끝나면 시각 타입이어야 한다 |
| `column_bool` | 참거짓 칸(BOOLEAN) | `^(is\|has\|can)_[a-z0-9_]+$` | is_parked · has_error · can_retry | 읽자마자 참/거짓 질문으로 읽힌다. 반대로 is_ · has_ · can_ 으로 시작하면 BOOLEAN 이어야 한다 |
| `pk` | 기본키 | `^id$` · 타입 `VARCHAR(36)` | id = id_column() (UUIDv7, CHAR(36)) | ADR-003 — 기본키는 단일 칸 id, UUIDv7 문자열. 정수 일련번호 · 복합키는 서비스 · 오프라인 생성과 이벤트 ID 체계를 깨뜨린다 |
| `column_ref` | 참조 칸(…_id · …_by) | `^(?!tenant_id$)[a-z][a-z0-9_]*_(id\|by)$` · 타입 `VARCHAR(36)` | item_id · created_by = ref_column() (UUIDv7, CHAR(36)) | 다른 개체를 가리키는 칸은 그 개체의 기본키(UUIDv7 36자)와 같은 형식 — 손으로 쓴 String(40) · INTEGER 는 길이 · 비교가 어긋난다(REQ-261104-12-7). 이 정규식에 맞는 칸만 본다. tenant_id 는 뺀다 — tenant_column 헬퍼(VARCHAR(40))가 정하고 길이 통일은 모든 서비스 표가 바뀌는 별도 요구 |
| `permission` | 권한키 | `^\*$\|^[a-z][a-z0-9_-]*\.(\*\|read\|create\|update\|delete)$` | sample.read · order-hub.* · * | 2단 <모듈>.<행위> — 모듈은 services.json perm(없으면 서비스 이름) 또는 declared_permission_modules, 행위는 HTTP 메서드에서 온다(대장이 코드에서 파생) |
| `topic` | 이벤트 토픽 | `^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$` | sample.item.created · platform.rbac.changed | 3단 <서비스(밑줄) \| platform>.<개체>.<과거형> — 일어난 사실. 첫 마디는 서비스 이름(하이픈 → 밑줄) · 패키지 이름 · topic_domains 중 하나, 끝 마디는 -ed 또는 past_tense_irregular. 테넌트는 토픽이 아니라 봉투에(STD-TENANCY-001) |
| `error_code` | 오류 코드 | `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` | item_not_found · tenant_required | {error:{code,message}} 의 code — snake_case <개체>_<사유>. 화면은 message 를 보이고 code 로 분기한다 |
| `api_segment` | API 경로 마디 | `^([a-z][a-z0-9-]*\|\{[a-z][a-z0-9_]*\})$` | /sample/items/{item_id}/archive | 경로는 소문자 kebab, 자리표시는 {snake}. 외부 경로는 게이트웨이 /v1 아래(서비스는 /v1 을 쓰지 않는다) |
| `component` | UI 컴포넌트 | `^[A-Z][A-Za-z0-9]*$` | DataTable · EmptyState (모바일 DataList) | React · Compose 관례 PascalCase. 웹 · 모바일 대응은 같은 개념 같은 이름(ui.md 9번) |
| `web_export` | @nova/ui 내보내기 | `^(use[A-Z][A-Za-z0-9]*\|[A-Z][A-Za-z0-9]*\|[a-z][A-Za-z0-9]*\|[A-Z][A-Z0-9_]*)$` | useApi · Button · fmtAt · DEFAULT_SHORTCUTS | 훅 use* · 컴포넌트 · 타입 PascalCase · 함수 camelCase · 상수 UPPER_SNAKE — 밑줄 · 하이픈으로 시작하는 공개 이름 금지 |
| `service` | 서비스 이름 | `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` | sample · order-hub | k8s 이름 · URL 경로 · DB 스키마로 그대로 쓰인다 — 소문자 · 숫자 · 하이픈. 파이썬 패키지는 하이픈 → 밑줄 |
| `scope` | 범위(scope) | `^[A-Z][A-Z0-9]{1,15}$` | SAMPLE · ORDER | 생성물 원장 ID <종류>-<범위>-NNNN 의 가운데 — 대문자 2~16자 |
| `pack` | 도메인 팩 이름 | `^[a-z][a-z0-9_]{1,30}$` | pharma · fresh_food | 파이썬 패키지(packs.<팩>)와 확장 표 접두어로 쓰인다 — 소문자 · 숫자 · 밑줄 |
| `pack_ext_table` | 팩 확장 표 | `^{pack}_[a-z0-9_]+_ext$` | pharma_item_ext | STD-DOMAIN-PACK-001 ② — 코어 표에 칸을 더하지 않고 <팩>_<개체>_ext 로 뺀다({pack} 은 팩 이름으로 바뀐다) |
| `entity_key` | 개념 원장 키 | `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` | item · item_activity · processed_event | 개념 하나 = 키 하나. 보통 표 이름과 같다 |

### 금지 축약 (모든 식별자 마디)

| 축약 | 대신 쓰는 말 |
|---|---|
| `emp` | `employee` |
| `dept` | `department` |
| `org` | `organization` |
| `usr` | `user` |
| `cust` | `customer` |
| `prod` | `product` |
| `mgr` | `manager` |
| `addr` | `address` |

### 토픽 끝 마디 — 불규칙 과거형

`built` · `bought` · `done` · `held` · `lost` · `made` · `paid` · `put` · `read` · `reset` · `run` · `sent` · `set` · `shut` · `sold` · `split` · `won` · `written`

### 토픽 첫 마디 · 권한 모듈로 더 허용하는 말

| 구분 | 말 | 이유 |
|---|---|---|
| 토픽 도메인 | `platform` | 플랫폼 공통 사실(게이트웨이 캐시 무효화 — 기능 플래그 · 권한 표 변경) |
| 권한 모듈 | `ops` | 게이트웨이 운영 API — services/gateway/gateway/routing.py OWN_PERMS(서비스가 아닌 모듈) |

### baseline — 이 규약 이전부터 있던 위반(신규만 막는다 · 고치면 지운다)

| 규칙 | 대상 | 이유 |
|---|---|---|
| `column_ref` | `*:outbox.event_id` | 플랫폼 공통 표의 이벤트 ID 가 VARCHAR(40)(column_ref 이전). 바꾸면 모든 서비스 DB 의 플랫폼 분기 마이그레이션이다 — REQ-261104-11(R7 · P1) 몫(plan_REQ_04 §9) |
| `column_ref` | `*:processed_event.event_id` | 플랫폼 공통 표의 이벤트 ID 가 VARCHAR(40)(column_ref 이전, 복합 기본키의 한 칸). 바꾸면 모든 서비스 DB 의 플랫폼 분기 마이그레이션이다 — REQ-261104-11(R7 · P1) 몫(plan_REQ_04 §9) |

### 의도한 예외

| 규칙 | 대상 | 이유 |
|---|---|---|
| `pk` | `*:outbox` | 의도한 예외(ADR-012 D3) — INTEGER 자동 증가 id 가 발행 순서를 보장한다(아웃박스 릴레이가 id 순으로 보낸다). UUIDv7 로 바꾸면 순서 보장을 다른 칸으로 옮겨야 하고 이득이 없다 |
| `pk` | `*:processed_event` | 의도한 예외(ADR-012 D3) — (event_id, consumer) 복합 기본키가 멱등성 자체를 보장하는 설계. 단일 id 로 바꾸면 같은 보장을 UNIQUE 로 다시 세워야 한다 |

### 프로젝트 추가 형식

(없음 — `registry/naming.json` `project` 절에 더한다)

<!-- naming:end -->
