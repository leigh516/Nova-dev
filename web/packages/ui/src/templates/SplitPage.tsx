"use client";
/**
 * 목록 · 상세 나란히(스플릿) 템플릿 — 왼쪽 목록(DataTable)에서 고르면 오른쪽에 상세. 화면은 columns · detail 만 넘긴다(ui.md §1).
 * - 고른 행은 주소 `?sel=<id>` 에 남는다 — 새로고침 · 공유해도 같은 행(UX H6)
 * - 목록 행에 포커스가 있으면 ↑ ↓ 로 고른 행을 옮긴다(UX H7)
 * - 900px 아래에서는 목록 위 · 상세 아래로 쌓는다
 * - 데이터는 `source`(게이트웨이 경로, 목록 계약 {items,total,page,size} 또는 배열) 또는 `rows`(이미 가진 값) 중 하나
 */
import React, { useRef } from "react";
import { type Page } from "@nova/sdk";
import { useApi, useQueryState } from "../hooks";
import { Content, PageHeader, Skeleton } from "../components/basic";
import { EmptyState, ErrorState } from "../components/feedback";
import { DataTable, type Column } from "../components/DataTable";

export interface SplitPageProps<T> {
  title: string;
  description?: React.ReactNode;
  /** 게이트웨이 경로(예: "/sample/items") — rows 를 주지 않을 때 */
  source?: string;
  /** 이미 가진 행 — 주면 source 를 읽지 않는다(시연 · 다른 화면에서 받은 목록) */
  rows?: T[];
  columns: Column<T>[];
  /** 오른쪽 상세 — 고른 행 하나를 그린다 */
  detail: (row: T) => React.ReactNode;
  /** 목록이 비었을 때 */
  empty?: { title: string; description?: React.ReactNode };
}

export function SplitPage<T extends { id?: string | number }>(p: SplitPageProps<T>) {
  const [sel, setSel] = useQueryState("sel");
  const remote = useApi<Page<T> | T[]>(p.rows === undefined ? p.source ?? null : null);
  const data = p.rows ?? remote.data;
  const rows: T[] = Array.isArray(data) ? data : data?.items ?? [];
  const idx = rows.findIndex((r) => String(r.id) === sel);
  const current = idx >= 0 ? rows[idx] : undefined;
  const list = useRef<HTMLDivElement>(null);

  // ↑ ↓ — 행에 포커스가 있을 때만(입력 칸 · 상세 쪽 키는 건드리지 않는다). 옮긴 행으로 포커스도 따라간다
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const t = e.target as HTMLElement;
    if (t.tagName !== "TR" || rows.length === 0) return;
    e.preventDefault();
    const trs = Array.from(list.current?.querySelectorAll<HTMLTableRowElement>("tbody tr") ?? []);
    const at = trs.indexOf(t as HTMLTableRowElement);
    const next = Math.min(rows.length - 1, Math.max(0, (at < 0 ? idx : at) + (e.key === "ArrowDown" ? 1 : -1)));
    setSel(String(rows[next].id ?? ""));
    trs[next]?.focus();
  };

  let left: React.ReactNode;
  if (data === null || data === undefined) {
    left = remote.error
      ? <ErrorState error={remote.error} onRetry={remote.reload} />
      : <div className="stack p-4" aria-busy="true" aria-label="불러오는 중">{[0, 1, 2, 3].map((i) => <Skeleton key={i} height={20} />)}</div>;
  } else if (rows.length === 0) {
    left = <EmptyState title={p.empty?.title ?? "아직 항목이 없습니다"} description={p.empty?.description} />;
  } else {
    left = (
      <DataTable rows={rows} columns={p.columns} caption={`${p.title} 목록`}
        onRowClick={(r) => setSel(String(r.id ?? ""))} isCurrent={(r) => r === current} />
    );
  }

  return (
    <Content width="wide">
      <PageHeader title={p.title} description={p.description} />
      <div className="split">
        <div ref={list} className="card flush split-list" role="region" aria-label="목록" onKeyDown={onKeyDown}>{left}</div>
        <section className="card split-detail" aria-label="상세" aria-live="polite">
          {current ? p.detail(current) : rows.length > 0 ? (
            <EmptyState icon="👈" title={sel ? "고른 항목을 찾을 수 없습니다" : "왼쪽 목록에서 항목을 고르세요"}
              description={sel ? "지워졌거나 이 목록에 없는 항목입니다. 다른 항목을 고르세요." : "↑ ↓ 로도 옮길 수 있습니다."} />
          ) : null}
        </section>
      </div>
    </Content>
  );
}
