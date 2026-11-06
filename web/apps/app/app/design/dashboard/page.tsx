"use client";
/** @screen 디자인 갤러리 — 대시보드 · @status 완료 */
/**
 * DashboardPage 시연 — 지표 줄 + 블록 격자, 가짜 데이터(data 주입 · 서버 호출 없음).
 * '장비 가용률' 블록은 일부러 실패시켜 한 블록 오류가 다른 블록을 지우지 않음을 보인다(계획 REQ_05 §6).
 */
import {
  AiMark, Badge, Bars, Button, ChartLegend, DashboardPage, DataTable, DomainTag, Sparkline, useToast, type DomainSlot, type Tone,
} from "@nova/ui";
import { ApiError } from "@nova/sdk";

/** 도메인 → 번호 슬롯 매핑 예시 — 실제 프로젝트는 팩 · 서버 설정 데이터에서 읽는다 */
const DOMAINS: Record<string, { label: string; slot: DomainSlot }> = {
  monitor: { label: "관제", slot: 1 }, asset: { label: "자산", slot: 2 }, contract: { label: "계약", slot: 3 },
  incident: { label: "장애", slot: 4 }, aiserver: { label: "AI 서버", slot: 5 },
};
const LEVEL: Record<string, { label: string; tone: Tone }> = {
  critical: { label: "위험", tone: "danger" }, warning: { label: "경고", tone: "warning" }, info: { label: "정보", tone: "info" },
};

interface Overview {
  alerts: { critical: number; warning: number };
  gpu: { up: number; total: number; maint: number };
  latencyMs: number;
  trend: { label: string; values: number[] }[];
  throughput: { module: string; value: number }[];
  recent: { id: string; module: string; summary: string; level: string }[];
}

/** 모듈 수준 상수 — data 는 바뀔 때만 새 값으로 넘긴다 */
const DATA: Overview = {
  alerts: { critical: 3, warning: 12 },
  gpu: { up: 46, total: 48, maint: 2 },
  latencyMs: 182,
  trend: [
    { label: "방화벽", values: [4, 5, 4.5, 6, 5.5, 7, 7.5, 8, 7.8] },
    { label: "IPS", values: [2, 2.2, 2.5, 2.3, 3, 2.9, 3.4, 3.3, 3.6] },
    { label: "웹 방화벽", values: [6, 5.4, 6.2, 5, 5.2, 4.2, 4.4, 3.8, 4] },
    { label: "EDR", values: [1.5, 1.6, 1.4, 1.8, 1.7, 2, 1.9, 2.2, 2.1] },
    { label: "AI 서버", values: [7, 6.8, 7.2, 6.6, 6.9, 6.4, 6.7, 6.2, 6.5] },
    { label: "기타", values: [1, 1.1, 1, 1.2, 1.1, 1.3, 1.2, 1.4, 1.3] },
  ],
  throughput: [
    { module: "관제", value: 9 }, { module: "자산", value: 6 }, { module: "계약", value: 4 }, { module: "장애", value: 7 }, { module: "AI 서버", value: 10 },
  ],
  recent: [
    { id: "a1", module: "monitor", summary: "FW-SEOUL-02 외부 접속 폭주", level: "critical" },
    { id: "a2", module: "aiserver", summary: "GPU-17 온도 상한 근접", level: "warning" },
    { id: "a3", module: "asset", summary: "장비 2대 점검 일정 도래", level: "info" },
  ],
};

export default function DesignDashboard() {
  const toast = useToast();
  return (
    <DashboardPage<Overview>
      title="관제 대시보드"
      description="DashboardPage 시연 — 지표 줄 + 블록 격자. 가짜 데이터(data 주입)."
      data={DATA}
      stats={(d) => [
        { label: "위험 경보", value: d.alerts.critical, delta: "지난 1시간 +2", tone: "danger", solid: true },
        { label: "경고", value: d.alerts.warning, delta: "지난 1시간 −1" },
        { label: "가동 GPU 서버", value: `${d.gpu.up} / ${d.gpu.total}`, delta: `${d.gpu.maint}대 점검 중` },
        { label: "처리 지연(중앙값)", value: `${d.latencyMs}ms`, delta: "어제보다 −14ms" },
      ]}
      blocks={(d) => [
        {
          id: "trend", title: "경보 추이 — 지난 24시간", wide: true,
          actions: <ChartLegend items={d.trend.map((t) => ({ label: t.label }))} />,
          body: (
            <div className="grid cols-sm">
              {d.trend.map((t, i) => <Sparkline key={t.label} series={i} width={180} height={56} values={t.values} label={`${t.label} 추이`} />)}
            </div>
          ),
        },
        {
          id: "throughput", title: "모듈별 처리량", actions: <span className="xs muted">건 / 분</span>,
          body: <Bars height={180} data={d.throughput.map((t, i) => ({ label: t.module, value: t.value, series: i }))} />,
        },
        {
          id: "recent", title: "최근 경보", actions: <a className="small" href="/design">전체 보기</a>,
          body: (
            <DataTable rows={d.recent} caption="최근 경보" columns={[
              { key: "module", title: "모듈", render: (r) => <DomainTag code={r.module} map={DOMAINS} /> },
              { key: "summary", title: "내용" },
              { key: "level", title: "수준", align: "right", render: (r) => <Badge tone={LEVEL[r.level]?.tone}>{LEVEL[r.level]?.label ?? r.level}</Badge> },
            ]} />
          ),
        },
        {
          id: "ai", title: "AI 제안", actions: <AiMark />,
          body: (
            <div className="stack">
              <p className="small secondary">방화벽 3대 격리를 제안했습니다. 실행하려면 확인 카드에서 승인이 필요합니다(L2).</p>
              <div><Button variant="secondary" size="sm" onClick={() => toast("AI 확인 카드는 갤러리의 'AI 확인 카드' 절에서 봅니다")}>제안 열어 보기</Button></div>
            </div>
          ),
        },
        {
          id: "availability", title: "장비 가용률",
          body: null,
          error: new ApiError(504, "upstream_timeout", "장비 수집기가 응답하지 않습니다. 다른 블록은 그대로 보입니다. 잠시 뒤 다시 시도하세요."),
          onRetry: () => toast("다시 시도했습니다 — 시연 데이터라 같은 오류가 납니다"),
        },
      ]}
    />
  );
}
