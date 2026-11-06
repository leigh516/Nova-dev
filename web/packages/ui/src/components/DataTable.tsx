"use client";
/**
 * 선언형 표 — columns(키 · 제목 · 정렬 · 렌더러) + rowActions 만 넘긴다(ui.md 규칙 3).
 * 정렬은 헤더 버튼(키보드로도), 행 클릭은 Enter 로도 된다(UX H7 · 접근성).
 */
import React from "react";

export interface Column<T> {
  key: string;
  title: string;
  render?: (row: T) => React.ReactNode;
  sortable?: boolean;
  align?: "left" | "right";
  width?: number | string;
  /** 개인정보 열 — 화면에는 그대로, 내보내기(CSV) 파일에는 **** 로 가린다(빈 값은 빈 채로) */
  pii?: boolean;
  /** false 면 내보내기에서 뺀다(행 동작 · 그림만 있는 열 등). 기본 true */
  exportable?: boolean;
}

/* ------------------------------------------------------------------ CSV 직렬화(내보내기) */
/** 엑셀이 수식으로 읽는 첫 글자 — 앞에 ' 를 붙여 글자로 만든다(CSV 수식 주입 방지, 계획 REQ_05 §6) */
const FORMULA_HEAD = /^[=+\-@\t\r]/;
const PII_MASK = "****";

function csvCell(raw: string): string {
  // 쉼표 · 따옴표 · 줄바꿈이 있으면 따옴표로 감싸고 안의 따옴표는 두 번 쓴다(RFC 4180)
  return /[",\r\n]/.test(raw) ? `"${raw.replace(/"/g, '""')}"` : raw;
}

function csvValue(v: unknown, pii: boolean | undefined): string {
  if (v === null || v === undefined || v === "") return ""; // 빈 값은 가림 표시 없이 빈 채로(가린 것과 없는 것을 구별)
  if (pii) return PII_MASK;
  if (typeof v === "number" || typeof v === "boolean" || typeof v === "bigint") return String(v); // 숫자 -5 는 수식이 아니다
  const s = typeof v === "string" ? v : v instanceof Date ? v.toISOString() : JSON.stringify(v);
  return FORMULA_HEAD.test(s) ? `'${s}` : s;
}

/**
 * 행 → CSV 문자열(BOM 없음 — 파일로 내릴 때 붙인다). 화면 렌더(render)가 아니라 **원래 값**(row[key])을 쓴다.
 * `exportable: false` 열은 빼고, `pii` 열의 값은 **** 로 가린다. 줄 끝은 CRLF.
 */
export function toCsv<T>(rows: T[], columns: Column<T>[]): string {
  const cols = columns.filter((c) => c.exportable !== false);
  const head = cols.map((c) => csvCell(c.title)).join(",");
  const body = rows.map((r) => cols.map((c) => csvCell(csvValue((r as Record<string, unknown>)[c.key], c.pii))).join(","));
  return [head, ...body].join("\r\n") + "\r\n";
}

export function DataTable<T extends { id?: string | number }>({ rows, columns, rowKey, onRowClick, rowActions, sort, onSort, caption, isCurrent }: {
  rows: T[];
  columns: Column<T>[];
  rowKey?: (row: T) => string | number;
  onRowClick?: (row: T) => void;
  rowActions?: (row: T) => React.ReactNode;
  /** "name" 오름차순 · "-name" 내림차순 */
  sort?: string;
  onSort?: (sort: string) => void;
  caption?: string;
  /** 지금 고른 행(SplitPage 등) — aria-current 와 강조. 없으면 표시 없음 */
  isCurrent?: (row: T) => boolean;
}) {
  const key = (r: T, i: number) => (rowKey ? rowKey(r) : r.id ?? i);
  const sortKey = sort?.replace(/^-/, "");
  const desc = sort?.startsWith("-");
  return (
    <div className="table-wrap">
      <table className="table">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.align === "right" ? "right" : ""} style={{ width: c.width }}
                aria-sort={sortKey === c.key ? (desc ? "descending" : "ascending") : undefined}>
                {c.sortable && onSort ? (
                  <button type="button" onClick={() => onSort(sortKey === c.key && !desc ? `-${c.key}` : c.key)}>
                    {c.title}<span aria-hidden="true">{sortKey === c.key ? (desc ? "▼" : "▲") : "↕"}</span>
                  </button>
                ) : c.title}
              </th>
            ))}
            {rowActions && <th className="right"><span className="sr-only">동작</span></th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={key(r, i)} data-clickable={onRowClick ? "true" : undefined} aria-current={isCurrent?.(r) ? "true" : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
              // 행 자체에 포커스가 있을 때만 Enter 로 연다 — 행 안 버튼(보관 · 삭제)의 Enter 가 올라와 이동하면 안 된다(T04-9.05)
              onKeyDown={onRowClick ? (e) => { if (e.key === "Enter" && e.target === e.currentTarget) onRowClick(r); } : undefined}>
              {columns.map((c) => (
                <td key={c.key} className={c.align === "right" ? "right num" : ""}>
                  {c.render ? c.render(r) : String((r as Record<string, unknown>)[c.key] ?? "—")}
                </td>
              ))}
              {rowActions && <td className="right" onClick={(e) => e.stopPropagation()}><div className="row" style={{ justifyContent: "flex-end" }}>{rowActions(r)}</div></td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ page, size, total, onPage }: { page: number; size: number; total: number; onPage: (p: number) => void }) {
  const last = Math.max(1, Math.ceil(total / size));
  const from = total === 0 ? 0 : (page - 1) * size + 1;
  const to = Math.min(total, page * size);
  return (
    <nav className="pagination" aria-label="페이지">
      <span>전체 {total.toLocaleString()}건 중 {from}–{to}</span>
      <div className="row">
        <button type="button" className="btn secondary sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>이전</button>
        <span className="num">{page} / {last}</span>
        <button type="button" className="btn secondary sm" disabled={page >= last} onClick={() => onPage(page + 1)}>다음</button>
      </div>
    </nav>
  );
}
