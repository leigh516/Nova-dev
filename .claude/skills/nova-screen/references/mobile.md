# 모바일 화면 — kr.nova.uikit

정본: `apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/`(부품 · `rememberAction` · 테마), 색은 생성 토큰(`DesignTokens.kt`, 손으로 고치지 않는다).

## 웹 ↔ 모바일 대응 (같은 개념은 같은 이름 — ui.md §2)
| 웹 `@nova/ui` | 모바일 `kr.nova.uikit` |
|---|---|
| `PageHeader` | `ScreenHeader` |
| `Button` | `NovaButton` |
| `TextInput` · `Field` | `NovaTextField` |
| `Card` · `Badge` · `StatusBadge` | `Card` · `Badge` · `StatusBadge` |
| `EmptyState` · `ErrorState` | `EmptyState` · `ErrorState` |
| `ConfirmDialog` · `useConfirm` | `ConfirmDialog` |
| `useAction` | `rememberAction` |
| `AppShell` 메뉴 | 하단 탭 — 서버 메뉴(`/v1/menu`)에서 온다 |

## 판단
1. **반응형인가 전용인가** — 웹 화면을 좁게 보는 것으로 충분하면 모바일 화면을 따로 만들지 않는다. 현장 작업(한 손 · 이동 중 · 오프라인)이 있을 때만 전용
2. **하단의 되돌리기 어려운 행위는 화면당 하나** — 엄지 영역에 여러 개를 두면 잘못 누른다
3. **서명 · 사진 같은 입력에는 대체 경로** — 못 하는 사람이 막히지 않게
4. **PIN 과 OTP 는 다른 부품** — 하나로 합치지 않는다
5. **오프라인은 오류가 아니다** — 상태로 보여 주고, 다시 이어지면 보낸다
6. **시각은 현지 시간대로** — 서버의 UTC 를 그대로 보여 주지 않는다

## 확인
`python nova.py kmp-test` · `kmp-build`, 화면 PNG 는 게이트웨이를 켜고 `kmp-snapshots`(다크 포함) → PNG 를 직접 연다.
