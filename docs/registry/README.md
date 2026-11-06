# 생성물 원장 (artifact registry)

> 생성 파일 — `uv run python scripts/registry.py sync` 가 `registry/events.jsonl`(원천)을 재생해 만든다. 직접 고치지 않는다.
> 새로 만들기 전에 여기서 이미 있는 것을 찾는다(계획서 §8 재사용). 삭제된 이름은 새로 만들지 말고 `restore <ID>`.

대장(코드에서 파생, ADR-004): [화면](screens.md) · [DB 사전](db-dictionary.md) · [권한](permissions.md) · [이벤트](events.md)

| 종류 | 활성 | 폐기 | 삭제 |
|---|---|---|---|
| 서비스 · 앱 (`SVC`) | 3 | 0 | 0 |
| DB 테이블 (`TBL`) | 4 | 0 | 0 |
| API (`API`) | 16 | 0 | 0 |
| 이벤트 토픽 (`EVT`) | 7 | 0 | 0 |
| 화면 (`SCR`) | 11 | 0 | 0 |
| UI 컴포넌트 (`CMP`) | 67 | 0 | 0 |

## 서비스 · 앱 (`SVC`)

| ID | 이름 | 위치 | 버전 |
|---|---|---|---|
| `SVC-SYS-0001` | sample | `services/sample` | 1 |
| `SVC-SYS-0002` | gateway | `services/gateway` | 1 |
| `SVC-SYS-0003` | web-app | `web/apps/app` | 1 |

## DB 테이블 (`TBL`)

| ID | 이름 | 위치 | 버전 |
|---|---|---|---|
| `TBL-SAMPLE-0001` | item | `services/sample/sample/models.py` | 1 |
| `TBL-SAMPLE-0002` | item_activity | `services/sample/sample/models.py` | 1 |
| `TBL-SAMPLE-0003` | outbox | `packages/common-py/nova_common/db.py` | 1 |
| `TBL-SAMPLE-0004` | processed_event | `packages/common-py/nova_common/db.py` | 1 |

## API (`API`)

| ID | 이름 | 위치 | 버전 |
|---|---|---|---|
| `API-GW-0001` | GET /v1/menu | `services/gateway/gateway/main.py` | 1 |
| `API-GW-0002` | GET /v1/me | `services/gateway/gateway/main.py` | 1 |
| `API-GW-0003` | POST /v1/auth/login | `services/gateway/gateway/main.py` | 1 |
| `API-GW-0004` | GET /v1/ops/monitoring/overview | `services/gateway/gateway/main.py` | 1 |
| `API-GW-0005` | GET /v1/ops/monitoring/alerts | `services/gateway/gateway/main.py` | 1 |
| `API-GW-0006` | POST /internal/alertmanager | `services/gateway/gateway/main.py` | 1 |
| `API-GW-0007` | GET /v1/ops/monitoring/query | `services/gateway/gateway/main.py` | 1 |
| `API-GW-0008` | GET /v1/ops/monitoring/range | `services/gateway/gateway/main.py` | 1 |
| `API-GW-0009` | POST /v1/auth/logout | `services/gateway/gateway/main.py` | 1 |
| `API-SAMPLE-0001` | GET /sample/items | `services/sample/sample/items.py` | 1 |
| `API-SAMPLE-0002` | GET /sample/items/{item_id} | `services/sample/sample/items.py` | 1 |
| `API-SAMPLE-0003` | POST /sample/items | `services/sample/sample/items.py` | 1 |
| `API-SAMPLE-0004` | PATCH /sample/items/{item_id} | `services/sample/sample/items.py` | 1 |
| `API-SAMPLE-0005` | POST /sample/items/{item_id}/archive | `services/sample/sample/items.py` | 1 |
| `API-SAMPLE-0006` | POST /sample/items/{item_id}/restore | `services/sample/sample/items.py` | 1 |
| `API-SAMPLE-0007` | DELETE /sample/items/{item_id} | `services/sample/sample/items.py` | 1 |

## 이벤트 토픽 (`EVT`)

| ID | 이름 | 위치 | 버전 |
|---|---|---|---|
| `EVT-KAFKA-0001` | sample.item.created | `infra/k3s/base/kafka-topics.txt` | 1 |
| `EVT-KAFKA-0002` | sample.item.updated | `infra/k3s/base/kafka-topics.txt` | 1 |
| `EVT-KAFKA-0003` | sample.item.archived | `infra/k3s/base/kafka-topics.txt` | 1 |
| `EVT-KAFKA-0004` | platform.feature.changed | `infra/k3s/base/kafka-topics.txt` | 1 |
| `EVT-KAFKA-0005` | platform.rbac.changed | `infra/k3s/base/kafka-topics.txt` | 1 |
| `EVT-KAFKA-0006` | sample.item.restored | `infra/k3s/base/kafka-topics.txt` | 1 |
| `EVT-KAFKA-0007` | sample.item.deleted | `infra/k3s/base/kafka-topics.txt` | 1 |

## 화면 (`SCR`)

| ID | 이름 | 위치 | 버전 |
|---|---|---|---|
| `SCR-WAPP-0001` | /design | `web/apps/app/app/design/page.tsx` | 1 |
| `SCR-WAPP-0002` | /help | `web/apps/app/app/help/page.tsx` | 1 |
| `SCR-WAPP-0003` | /items/[id] | `web/apps/app/app/items/[id]/page.tsx` | 1 |
| `SCR-WAPP-0004` | /items/new | `web/apps/app/app/items/new/page.tsx` | 1 |
| `SCR-WAPP-0005` | /items | `web/apps/app/app/items/page.tsx` | 1 |
| `SCR-WAPP-0006` | /login | `web/apps/app/app/login/page.tsx` | 1 |
| `SCR-WAPP-0007` | /ops | `web/apps/app/app/ops/page.tsx` | 1 |
| `SCR-WAPP-0008` | / | `web/apps/app/app/page.tsx` | 1 |
| `SCR-WAPP-0009` | /design/dashboard | `web/apps/app/app/design/dashboard/page.tsx` | 1 |
| `SCR-WAPP-0010` | /design/settings | `web/apps/app/app/design/settings/page.tsx` | 1 |
| `SCR-WAPP-0011` | /design/split | `web/apps/app/app/design/split/page.tsx` | 1 |

## UI 컴포넌트 (`CMP`)

| ID | 이름 | 위치 | 버전 |
|---|---|---|---|
| `CMP-UI-0001` | Button | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0002` | Spinner | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0003` | Skeleton | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0004` | Content | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0005` | PageHeader | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0006` | Section | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0007` | Card | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0008` | Badge | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0009` | StatusBadge | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0010` | Stat | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0011` | KeyValue | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0012` | Field | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0013` | TextInput | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0014` | TextArea | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0015` | Select | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0016` | Segmented | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0017` | Switch | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0018` | DataTable | `web/packages/ui/src/components/DataTable.tsx` | 1 |
| `CMP-UI-0019` | Pagination | `web/packages/ui/src/components/DataTable.tsx` | 1 |
| `CMP-UI-0020` | Sparkline | `web/packages/ui/src/components/extras.tsx` | 1 |
| `CMP-UI-0021` | Bars | `web/packages/ui/src/components/extras.tsx` | 1 |
| `CMP-UI-0022` | ShortcutHelp | `web/packages/ui/src/components/extras.tsx` | 1 |
| `CMP-UI-0023` | ThemeToggle | `web/packages/ui/src/components/extras.tsx` | 1 |
| `CMP-UI-0024` | EmptyState | `web/packages/ui/src/components/feedback.tsx` | 1 |
| `CMP-UI-0025` | Forbidden | `web/packages/ui/src/components/feedback.tsx` | 1 |
| `CMP-UI-0026` | ErrorState | `web/packages/ui/src/components/feedback.tsx` | 1 |
| `CMP-UI-0027` | Providers | `web/packages/ui/src/providers.tsx` | 1 |
| `CMP-UI-0028` | ConfirmDialog | `web/packages/ui/src/providers.tsx` | 1 |
| `CMP-UI-0029` | AppShell | `web/packages/ui/src/templates/AppShell.tsx` | 1 |
| `CMP-UI-0030` | RequireAuth | `web/packages/ui/src/templates/AppShell.tsx` | 1 |
| `CMP-UI-0031` | LoginPage | `web/packages/ui/src/templates/pages.tsx` | 1 |
| `CMP-UI-0032` | ListPage | `web/packages/ui/src/templates/pages.tsx` | 1 |
| `CMP-UI-0033` | DetailPage | `web/packages/ui/src/templates/pages.tsx` | 1 |
| `CMP-UI-0034` | FormPage | `web/packages/ui/src/templates/pages.tsx` | 1 |
| `CMP-UI-0035` | AiMark | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0036` | DomainTag | `web/packages/ui/src/components/basic.tsx` | 1 |
| `CMP-UI-0037` | ChartLegend | `web/packages/ui/src/components/extras.tsx` | 1 |
| `CMP-UI-0038` | Sidebar | `web/packages/ui/src/templates/AppShell.tsx` | 1 |
| `CMP-UI-0039` | HeaderSearch | `web/packages/ui/src/components/header.tsx` | 1 |
| `CMP-UI-0040` | NotificationLink | `web/packages/ui/src/components/header.tsx` | 1 |
| `CMP-UI-0041` | TenantSwitcher | `web/packages/ui/src/components/header.tsx` | 1 |
| `CMP-UI-0042` | HeaderUtils | `web/packages/ui/src/components/header.tsx` | 1 |
| `CMP-UI-0043` | DashboardPage | `web/packages/ui/src/templates/DashboardPage.tsx` | 1 |
| `CMP-UI-0044` | AiConfirmCard | `web/packages/ui/src/components/AiConfirmCard.tsx` | 1 |
| `CMP-UI-0045` | FormFields | `web/packages/ui/src/components/form.tsx` | 1 |
| `CMP-UI-0046` | FormDialog | `web/packages/ui/src/components/FormDialog.tsx` | 1 |
| `CMP-UI-0047` | SettingsPage | `web/packages/ui/src/templates/SettingsPage.tsx` | 1 |
| `CMP-UI-0048` | SplitPage | `web/packages/ui/src/templates/SplitPage.tsx` | 1 |
| `CMP-UIKIT-0001` | NovaButton | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0002` | Card | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0003` | Title | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0004` | Muted | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0005` | Badge | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0006` | StatusBadge | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0007` | ScreenHeader | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0008` | NovaTextField | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0009` | Loading | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0010` | EmptyState | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0011` | ErrorState | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0012` | ConfirmDialog | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0013` | SpacerV | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0014` | NovaTheme | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Theme.kt` | 1 |
| `CMP-UIKIT-0015` | AiConfirmCard | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/AiConfirmCard.kt` | 1 |
| `CMP-UIKIT-0016` | AiMark | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0017` | DomainTag | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Components.kt` | 1 |
| `CMP-UIKIT-0018` | FormScreen | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Templates.kt` | 1 |
| `CMP-UIKIT-0019` | LoginScreen | `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/Templates.kt` | 1 |
