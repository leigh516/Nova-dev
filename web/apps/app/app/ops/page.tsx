"use client";
/** @screen 운영 모니터링 · @status 완료 */
/**
 * 운영 — 게이트웨이 모니터링 개요(ops.read 권한). DashboardPage 템플릿 호출 + 데이터 정의만(ui.md 규칙 1 · 5):
 * 로딩(스켈레톤) · 오류(다시 시도) · 5초 갱신 · 마지막 갱신 시각은 템플릿이 그린다. 상태 → 라벨 · 색은 lib/app.ts 매핑(규칙 6).
 */
import { DashboardPage, DataTable, RequireAuth, StatusBadge, fmtNumber } from "@nova/ui";
import { ALERT_SEVERITY, OPS_HEALTH, SERVICE_UP } from "../../lib/app";

interface Svc { service: string; up: boolean; rps: number; error_rate: number; p95_ms: number | null; outbox_pending: number }
interface Alert { name: string; severity: string; service: string; summary: string }
interface Overview { source: string; services: Svc[]; alerts: Alert[]; summary: { services_up: number; services_total: number; rps: number; health: string } }

export default function Ops() {
  return (
    <RequireAuth>
      <DashboardPage<Overview>
        title="운영 모니터링"
        description="서비스 상태 · 지연 · 아웃박스. 5초마다 자동으로 새로 고칩니다."
        source="/ops/monitoring/overview"
        refreshMs={5000}
        stats={(d) => [
          { label: "가동 서비스", value: `${d.summary.services_up} / ${d.summary.services_total}` },
          { label: "전체 RPS", value: fmtNumber(d.summary.rps, 2) },
          { label: "상태", value: <StatusBadge code={d.summary.health} map={OPS_HEALTH} />,
            delta: `수집: ${d.source === "prometheus" ? "Prometheus" : "직접"}` },
        ]}
        blocks={(d) => [
          ...(d.alerts.length > 0 ? [{
            id: "alerts", title: "알림", wide: true,
            body: (
              <ul className="stack list">
                {d.alerts.map((a, i) => <li key={`${a.name}-${a.service}-${i}`}><StatusBadge code={a.severity} map={ALERT_SEVERITY} /> <strong>{a.name}</strong> {a.service} — {a.summary}</li>)}
              </ul>
            ),
          }] : []),
          {
            id: "services", title: "서비스 상태", wide: true,
            body: (
              <DataTable<Svc & { id: string }> rows={d.services.map((x) => ({ ...x, id: x.service }))} caption="서비스 상태"
                columns={[
                  { key: "service", title: "서비스" },
                  { key: "up", title: "상태", render: (r) => <StatusBadge code={String(r.up)} map={SERVICE_UP} /> },
                  { key: "rps", title: "RPS", align: "right", render: (r) => fmtNumber(r.rps, 2) },
                  { key: "error_rate", title: "5xx", align: "right", render: (r) => `${fmtNumber(r.error_rate * 100, 1)}%` },
                  { key: "p95_ms", title: "p95", align: "right", render: (r) => (r.p95_ms == null ? "—" : `${fmtNumber(r.p95_ms)}ms`) },
                  { key: "outbox_pending", title: "미발행", align: "right" },
                ]} />
            ),
          },
        ]}
      />
    </RequireAuth>
  );
}
