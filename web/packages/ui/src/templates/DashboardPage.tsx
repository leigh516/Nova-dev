"use client";
/**
 * 대시보드 템플릿 — 지표 줄(Stat) + 블록 격자. 화면은 데이터 정의(stats · blocks)만 넘긴다(ui.md §1).
 * - 데이터는 `source`(게이트웨이 경로, refreshMs 마다 다시 읽음) 또는 `data`(이미 가진 값) 중 하나
 * - 한 블록이 실패해도(블록의 `error` · 그리기 예외) 그 블록만 ErrorState — 관제 화면이 통째로 사라지면 더 위험하다(계획 REQ_05 §6)
 * - 마지막 갱신 시각 · 갱신 중 표시(UX H1). 솔리드 지표는 경보 강조에만(화면당 한 곳 권장, UX H8)
 */
import React, { useEffect, useMemo, useState } from "react";
import { ApiError } from "@nova/sdk";
import { useApi } from "../hooks";
import { Button, Card, Content, PageHeader, Skeleton, Stat, type Tone } from "../components/basic";
import { EmptyState, ErrorState } from "../components/feedback";

export interface DashboardStat { label: string; value: React.ReactNode; delta?: React.ReactNode; tone?: Tone; solid?: boolean }
/**
 * 블록 하나 — `error` 를 주면 body 대신 그 블록만 ErrorState. 다시 시도는 `onRetry`(없으면 source 를 다시 읽는다).
 * `actions` 는 제목 옆 작은 행동(전체 보기 링크 · 범례 등)
 */
export interface DashboardBlock { id: string; title: string; wide?: boolean; body: React.ReactNode; error?: unknown; onRetry?: () => void; actions?: React.ReactNode }

export interface DashboardPageProps<D> {
  title: string;
  description?: React.ReactNode;
  /** 게이트웨이 경로(예: "/ops/monitoring/overview") — data 를 주지 않을 때 */
  source?: string;
  /** 이미 가진 값 — 주면 source 를 읽지 않는다 */
  data?: D;
  /** source 를 다시 읽는 주기(ms). 없으면 한 번만 */
  refreshMs?: number;
  stats: (d: D) => DashboardStat[];
  blocks: (d: D) => DashboardBlock[];
}

function toApiError(e: unknown): ApiError {
  if (e instanceof ApiError) return e;
  return new ApiError(0, "client", e instanceof Error ? e.message : String(e));
}

/** 블록 그리기 예외를 그 블록 안에 가둔다 — 다른 블록 · 화면은 그대로 */
class BlockBoundary extends React.Component<{ children: React.ReactNode }, { error: unknown }> {
  state = { error: null as unknown };
  static getDerivedStateFromError(error: unknown) { return { error }; }
  render() {
    if (this.state.error) return <ErrorState error={toApiError(this.state.error)} onRetry={() => this.setState({ error: null })} />;
    return this.props.children;
  }
}

/** 24시간 HH:MM:SS — 로케일 표기(오후 3시 …)는 관제 화면에서 읽기 느리다 */
function fmtClock(d: Date) {
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, "0")).join(":");
}

export function DashboardPage<D>(p: DashboardPageProps<D>) {
  // 자동 갱신 멈춤(WCAG 2.2.2 — 스스로 바뀌는 내용은 멈출 수 있어야 한다, T04-1.08 평가 심각도 3)
  const [paused, setPaused] = useState(false);
  const remote = useApi<D>(p.data === undefined ? p.source ?? null : null, undefined, { poll: p.data === undefined && !paused ? p.refreshMs : undefined });
  const d = p.data !== undefined ? p.data : remote.data ?? undefined;
  // 마지막으로 값을 받은 시각 — data 가 바뀌거나 source 응답이 올 때. setState 를 쓰지 않는다(화면이 data 를 인라인 객체로
  // 넘겨도 렌더 → 갱신 → 렌더 고리가 생기지 않게). 시각 글자는 하이드레이션 뒤에만 그린다(서버 HTML 과 달라 React #418)
  const at = useMemo(() => (d === undefined ? null : new Date()), [d]);
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);
  const live = p.data === undefined && !!p.source;
  const meta = (
    // 시각 글자는 알림 영역 밖에 둔다 — 갱신마다 화면 읽기 프로그램이 시각을 읽어 끼어들지 않게. 알리는 것은 실패 문구뿐
    <div className="row small muted">
      {mounted && at && <span>마지막 갱신 <span className="num">{fmtClock(at)}</span>{live && p.refreshMs ? (paused ? " · 자동 갱신 멈춤" : ` · ${Math.round(p.refreshMs / 1000)}초마다`) : ""}</span>}
      {live && remote.error && d !== undefined && <span role="status">새로 고치지 못해 이전 값을 보여 줍니다</span>}
      {live && p.refreshMs ? <Button size="sm" variant="ghost" aria-pressed={paused} onClick={() => setPaused((v) => !v)}>{paused ? "자동 갱신 다시 켜기" : "자동 갱신 멈춤"}</Button> : null}
      {live && <Button size="sm" variant="secondary" loading={remote.loading && d !== undefined} onClick={remote.reload}>지금 새로 고침</Button>}
    </div>
  );
  let body: React.ReactNode;
  if (d === undefined) {
    body = remote.error ? <Card><ErrorState error={remote.error} onRetry={remote.reload} /></Card> : (
      <div className="stack" aria-busy="true" aria-label="불러오는 중">
        <div className="dash-stats">{[0, 1, 2, 3].map((i) => <Skeleton key={i} height={96} />)}</div>
        <Skeleton height={240} />
      </div>
    );
  } else {
    const stats = p.stats(d);
    const blocks = p.blocks(d);
    body = (
      <div className="stack gap-4">
        {stats.length > 0 && (
          <section className="dash-stats" aria-label="주요 지표">
            {stats.map((s) => (
              <div key={s.label} className={`card stat-card${s.tone ? ` ${s.tone}` : ""}${s.solid && s.tone && s.tone !== "link" ? " solid" : ""}`}>
                <Stat label={s.label} value={s.value} delta={s.delta} />
              </div>
            ))}
          </section>
        )}
        {blocks.length === 0 ? <Card><EmptyState title="보여 줄 블록이 없습니다" /></Card> : (
          <section className="dash-grid" aria-label="블록">
            {blocks.map((b) => (
              <section key={b.id} className={`card dash-block${b.wide ? " wide" : ""}`} aria-labelledby={`blk-${b.id}`}>
                <div className="section-head"><h3 id={`blk-${b.id}`}>{b.title}</h3>{b.actions}</div>
                {b.error ? <ErrorState error={toApiError(b.error)} onRetry={b.onRetry ?? (live ? remote.reload : undefined)} /> : <BlockBoundary>{b.body}</BlockBoundary>}
              </section>
            ))}
          </section>
        )}
      </div>
    );
  }
  return (
    <Content width="wide">
      <PageHeader title={p.title} description={p.description} actions={meta} />
      {body}
    </Content>
  );
}
