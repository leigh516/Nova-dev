/**
 * @nova/ui — 웹 공통 UI. 3층: 토큰(tokens.css, 생성물) → 컴포넌트 → 템플릿. 화면은 템플릿 + 데이터 정의만.
 * 규약: docs/conventions/ui.md · UX: docs/conventions/ux-heuristics.md
 */
export { Providers, ConfirmDialog, useSession, useToast, useConfirm, type ToastOptions, type ConfirmOptions } from "./providers";
export { useApi, useAction, useQueryState, useShortcut, useDialogFocus, type ActionOptions } from "./hooks";
export {
  Button, Spinner, Skeleton, Content, PageHeader, Section, Card, Badge, StatusBadge, AiMark, DomainTag, Stat, KeyValue,
  Field, TextInput, TextArea, Select, Segmented, Switch, type Variant, type Size, type Tone, type DomainSlot,
} from "./components/basic";
export { EmptyState, ErrorState, Forbidden } from "./components/feedback";
export { DataTable, Pagination, toCsv, type Column } from "./components/DataTable";
export { Sparkline, Bars, ChartLegend, chartColor, ShortcutHelp, ThemeToggle, DEFAULT_SHORTCUTS, type Shortcut } from "./components/extras";
export {
  HeaderSearch, NotificationLink, TenantSwitcher, HeaderUtils,
  type HeaderConfig, type HeaderSearchConfig, type HeaderNotifications, type HeaderTenants,
} from "./components/header";
export { AppShell, Sidebar, RequireAuth, useMenu, type AppConfig, type NavLink } from "./templates/AppShell";
export { LoginPage, ListPage, DetailPage, FormPage, type ListPageProps, type FormField, type FormValue, type FormValues, type FormOption } from "./templates/pages";
export { DashboardPage, type DashboardPageProps, type DashboardStat, type DashboardBlock } from "./templates/DashboardPage";
export { SplitPage, type SplitPageProps } from "./templates/SplitPage";
export { SettingsPage, type SettingsPageProps, type SettingsSection } from "./templates/SettingsPage";
export { FormDialog, type FormDialogProps } from "./components/FormDialog";
export { AiConfirmCard, type AiConfirmCardProps } from "./components/AiConfirmCard";
export { fmtAt, fmtAgo, fmtNumber, fmtMoney } from "@nova/sdk";
