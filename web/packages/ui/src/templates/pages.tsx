"use client";
/**
 * 화면 템플릿 — 화면은 템플릿 호출 + 데이터 정의만(ui.md §1). 로딩 · 빈 상태 · 오류는 템플릿이 그린다(규칙 5).
 *   LoginPage · ListPage · DetailPage · FormPage
 */
import { useRouter } from "next/navigation";
import React, { useEffect, useRef, useState } from "react";
import { ApiError, EMAIL_MAX, api, emailError, login, type Page, type Query, type User } from "@nova/sdk";
import { useApi, useAction, useQueryState, useShortcut } from "../hooks";
import { useSession } from "../providers";
import { Button, Card, Content, Field, PageHeader, Skeleton, TextInput } from "../components/basic";
import { EmptyState, ErrorState } from "../components/feedback";
import { DataTable, Pagination, toCsv, type Column } from "../components/DataTable";
import { FormFields, useFormModel, type FormField, type FormValues } from "../components/form";

/* ------------------------------------------------------------------ 로그인 */
/** 아이디 저장 열쇠 — 이메일만 담는다(비밀번호는 어디에도 저장하지 않는다) */
const LOGIN_ID_KEY = `${process.env.NEXT_PUBLIC_STORAGE_PREFIX || "nova"}_login_id`;

/** 저장소 읽기 · 쓰기 — 사생활 모드 · 저장소 차단에서는 예외가 난다. 편의 기능이 로그인을 막으면 안 되므로 저장 없이 넘어간다(계획 REQ_05 §6 '열림') */
function readLoginId(): string | null {
  try { return localStorage.getItem(LOGIN_ID_KEY); } catch { return null; /* 저장소 막힘 — 저장된 아이디 없음으로 본다 */ }
}
function writeLoginId(email: string | null) {
  try { if (email) localStorage.setItem(LOGIN_ID_KEY, email); else localStorage.removeItem(LOGIN_ID_KEY); }
  catch { /* 저장소 막힘 — 이번 로그인은 저장 없이 진행한다(위 주석) */ }
}

export function LoginPage({ title, subtitle, brand, demo = [], demoPassword, after = "/", rememberId, links }: {
  title: string; subtitle?: string; brand: string; demo?: { label: string; email: string }[]; demoPassword?: string; after?: string;
  /** '아이디 저장' 체크 — 로그인에 성공하면 이메일만 이 브라우저에 남기고, 끄고 로그인하면 지운다 */
  rememberId?: boolean;
  /** 로그인 아래 링크(아이디 · 비밀번호 찾기 · 다른 로그인으로 전환 등) */
  links?: { label: string; href: string }[];
}) {
  const [email, setEmail] = useState(demo[0]?.email ?? "");
  const [pw, setPw] = useState(demoPassword ?? "");
  const [remember, setRemember] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [emailErr, setEmailErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { setUser } = useSession();
  const router = useRouter();
  // 저장한 아이디는 하이드레이션 뒤에 채운다(서버 HTML 과 첫 화면을 같게 — React #418 방지)
  useEffect(() => {
    if (!rememberId) return;
    const saved = readLoginId();
    if (saved) { setEmail(saved); setRemember(true); }
  }, [rememberId]);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return; // 진행 중 재제출 막기 — 버튼은 포커스를 지키려고 disabled 대신 aria-disabled(감사 A-F1)
    if (!email || !pw) { setErr("이메일과 비밀번호를 입력하세요"); return; }
    // 형식은 서버와 같은 규칙(EMAIL_PATTERN)으로 먼저 본다 — 틀린 형식을 보내 '계정 없음'으로 오해하지 않게(UX H5 · H9)
    const fe = emailError(email);
    if (fe) { setEmailErr(fe); setErr(null); return; }
    setBusy(true); setErr(null); setEmailErr(null);
    try {
      const u: User = await login(email, pw);
      if (rememberId) writeLoginId(remember ? email : null); // 성공한 아이디만 저장한다
      setUser(u); router.push(after);
    }
    catch (x) { setErr((x as ApiError).message); }
    finally { setBusy(false); }
  };
  return (
    <div className="login-wrap">
      <form className="card stack login-card" onSubmit={submit} noValidate>
        <div className="brand"><span className="mark" aria-hidden="true">{brand[0]}</span>{brand}</div>
        <div><h2>{title}</h2>{subtitle && <p className="muted small mt-1">{subtitle}</p>}</div>
        <Field label="이메일" required error={emailErr}>{(p) => <TextInput {...p} type="email" value={email} maxLength={EMAIL_MAX} onChange={(e) => { setEmail(e.target.value); setEmailErr(null); }} autoComplete="username" />}</Field>
        <Field label="비밀번호" required error={err}>{(p) => <TextInput {...p} type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" />}</Field>
        {rememberId && (
          <div className="row between small">
            <label className="check"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />아이디 저장</label>
            <span className="xs muted">이메일만 저장 · 비밀번호는 저장하지 않습니다</span>
          </div>
        )}
        <Button type="submit" size="lg" block loading={busy}>{busy ? "확인 중…" : "로그인"}</Button>
        {links && links.length > 0 && (
          <nav className="row small login-links" aria-label="로그인 도움">
            {links.map((l) => <a key={l.href + l.label} href={l.href}>{l.label}</a>)}
          </nav>
        )}
        {demo.length > 0 && (
          <div className="row small muted gap-2">
            개발용 계정:
            {demo.map((d) => <button type="button" key={d.email} className="btn secondary sm" onClick={() => setEmail(d.email)}>{d.label}</button>)}
          </div>
        )}
      </form>
    </div>
  );
}

/* ------------------------------------------------------------------ 목록 */
export interface ListPageProps<T> {
  title: string;
  description?: React.ReactNode;
  /** 게이트웨이 경로(예: "/sample/items") — 목록 계약 {items,total,page,size} 또는 배열 */
  source: string;
  columns: Column<T>[];
  rowActions?: (row: T, reload: () => void) => React.ReactNode;
  onRowClick?: (row: T) => void;
  /** 주 행동(새로 만들기) — 화면당 하나(UX H8). `n` 단축키로도 */
  primary?: { label: string; href?: string; onClick?: () => void };
  /** 추가 쿼리(필터 등) */
  query?: Query;
  filters?: React.ReactNode;
  searchPlaceholder?: string;
  empty?: { title: string; description?: React.ReactNode };
  pageSize?: number;
  /**
   * 내보내기(CSV) — 같은 검색 · 정렬 · query 로 size=100 쪽을 차례로 읽어 한 파일로(엑셀용 BOM).
   * `pii` 열은 **** 로 가리고 수식으로 시작하는 값은 무력화한다(toCsv). 도중에 403 · 오류면 파일을 만들지 않는다.
   * `max`(기본 5000)를 넘으면 앞 max 건만 담고 그렇게 알린다 — 더 많으면 서버 쪽 내보내기(다음 요구)
   */
  export?: { label?: string; filename: string; max?: number };
}

const EXPORT_PAGE = 100;

/** 파일 내리기 — BOM 을 붙여 엑셀이 UTF-8 한글을 바로 읽게 한다 */
function downloadCsv(csv: string, filename: string) {
  const name = filename.toLowerCase().endsWith(".csv") ? filename : `${filename}.csv`;
  const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000); // 바로 풀면 일부 브라우저가 내려받기 전에 주소를 잃는다
}

export function ListPage<T extends { id?: string | number }>(p: ListPageProps<T>) {
  const router = useRouter();
  const [q, setQ] = useQueryState("q");
  const [sort, setSort] = useQueryState("sort");
  const [pageStr, setPage] = useQueryState("page", "1");
  const page = Math.max(1, Number(pageStr) || 1);
  const size = p.pageSize ?? 20;
  const [draft, setDraft] = useState(q);
  const search = useRef<HTMLInputElement>(null);
  const { data, error, loading, reload } = useApi<Page<T> | T[]>(p.source, { q, sort, page, size, ...p.query });
  useShortcut("/", () => search.current?.focus());
  useShortcut("n", () => { if (p.primary?.href) router.push(p.primary.href); else p.primary?.onClick?.(); }, !!p.primary);
  const rows: T[] = Array.isArray(data) ? data : data?.items ?? [];
  const total = Array.isArray(data) ? data.length : data?.total ?? 0;
  const primary = p.primary && (p.primary.href
    ? <a className="btn primary" href={p.primary.href}>{p.primary.label}</a>
    : <Button onClick={p.primary.onClick}>{p.primary.label}</Button>);

  // 내보내기 — 진행(n / 전체)을 보이고(UX H1), 모두 읽은 뒤에만 파일을 만든다(일부만 담긴 파일 금지, 계획 §6 '닫힘')
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const max = p.export?.max ?? 5000;
  const exporter = useAction(async () => {
    setProgress({ done: 0, total: 0 });
    try {
      const all: T[] = [];
      let total = 0;
      for (let n = 1; ; n++) {
        const res = await api<Page<T> | T[]>(p.source, { query: { q, sort, ...p.query, page: n, size: EXPORT_PAGE } });
        if (Array.isArray(res)) { all.push(...res); total = all.length; break; } // 쪽 나눔이 없는 목록 — 한 번에 전부
        total = res.total;
        all.push(...res.items);
        setProgress({ done: Math.min(all.length, max), total });
        if (res.items.length === 0 || all.length >= total || all.length >= max) break;
      }
      const rows = all.slice(0, max);
      downloadCsv(toCsv(rows, p.columns), p.export!.filename);
      return { count: rows.length, total };
    } finally {
      setProgress(null);
    }
  }, {
    success: (r) => r.total > r.count
      ? `앞 ${r.count.toLocaleString()}건만 내보냈습니다 — 전체 ${r.total.toLocaleString()}건 중(한 번에 ${max.toLocaleString()}건까지)`
      : `${r.count.toLocaleString()}건을 내보냈습니다`,
  });
  const piiCols = p.columns.filter((c) => c.pii && c.exportable !== false).map((c) => c.title);

  return (
    <Content width="default">
      <PageHeader title={p.title} description={p.description} actions={primary} />
      <form className="row mb-3" role="search" onSubmit={(e) => { e.preventDefault(); setQ(draft.trim()); }}>
        <label htmlFor="list-q" className="sr-only">검색</label>
        <input id="list-q" ref={search} className="input search-input" placeholder={p.searchPlaceholder ?? "검색 ( / )"} value={draft} onChange={(e) => setDraft(e.target.value)} />
        <Button type="submit" variant="secondary">검색</Button>
        {q && <Button variant="ghost" onClick={() => { setDraft(""); setQ(""); }}>조건 지우기</Button>}
        {p.filters}
        {p.export && (
          <>
            <div className="grow" />
            <span id="list-export-note" className="xs muted" aria-live="polite">
              {progress
                ? `${progress.done.toLocaleString()} / ${progress.total ? progress.total.toLocaleString() : "?"}행 내보내는 중…`
                : piiCols.length > 0 ? `개인정보 열(${piiCols.join(" · ")})은 파일에서 **** 로 가립니다` : `한 번에 ${max.toLocaleString()}건까지`}
            </span>
            <Button variant="secondary" loading={exporter.running} aria-describedby="list-export-note"
              disabled={!exporter.running && !loading && rows.length === 0} onClick={() => exporter.run()}>
              {p.export.label ?? "내보내기(CSV)"}
            </Button>
          </>
        )}
      </form>
      <Card flush>
        {loading && !data ? (
          <div className="stack p-4" aria-busy="true" aria-label="불러오는 중">{[0, 1, 2, 3].map((i) => <Skeleton key={i} height={20} />)}</div>
        ) : error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : rows.length === 0 ? (
          q ? <EmptyState icon="🔍" title={`'${q}' 검색 결과가 없습니다`} description="다른 낱말로 찾거나 조건을 지워 보세요." action={<Button variant="secondary" onClick={() => { setDraft(""); setQ(""); }}>조건 지우기</Button>} />
            : <EmptyState title={p.empty?.title ?? "아직 항목이 없습니다"} description={p.empty?.description} action={primary} />
        ) : (
          <>
            <DataTable rows={rows} columns={p.columns} sort={sort} onSort={setSort} onRowClick={p.onRowClick}
              rowActions={p.rowActions ? (r) => p.rowActions!(r, reload) : undefined} caption={p.title} />
            {!Array.isArray(data) && <Pagination page={page} size={size} total={total} onPage={(n) => setPage(String(n))} />}
          </>
        )}
      </Card>
    </Content>
  );
}

/* ------------------------------------------------------------------ 상세 */
export function DetailPage<T>({ source, title, crumbs, actions, children }: {
  source: string;
  title: (d: T) => string;
  crumbs?: { href: string; label: string }[];
  actions?: (d: T, reload: () => void) => React.ReactNode;
  children: (d: T, reload: () => void) => React.ReactNode;
}) {
  const { data, error, loading, reload } = useApi<T>(source);
  return (
    <Content width="default">
      {loading && !data ? (
        <div className="stack" aria-busy="true"><Skeleton height={32} width={240} /><Skeleton height={160} /></div>
      ) : error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : data ? (
        <>
          <PageHeader title={title(data)} crumbs={crumbs} actions={actions?.(data, reload)} />
          {children(data, reload)}
        </>
      ) : null}
    </Content>
  );
}

/* ------------------------------------------------------------------ 입력 */
/** 필드 렌더 · 검사 · 서버 칸 오류는 FormDialog 와 공유한다(components/form.tsx) */
export type { FormField, FormValue, FormValues, FormOption } from "../components/form";

/** V 는 onSubmit 값의 모양(기본 FormValues — 글 · 선택 · 날짜는 string, 스위치 · 체크박스는 boolean) */
export function FormPage<V extends FormValues = FormValues>({ title, description, fields, initial = {}, submitLabel = "저장", onSubmit, success = "저장했습니다", cancelHref, crumbs }: {
  title: string; description?: React.ReactNode; fields: FormField[]; initial?: Partial<V>;
  submitLabel?: string; onSubmit: (v: V) => Promise<unknown>; success?: string; cancelHref?: string;
  crumbs?: { href: string; label: string }[];
}) {
  const router = useRouter();
  const form = useFormModel<V>({ fields, initial, onSubmit, success, then: () => { if (cancelHref) router.push(cancelHref); } });
  return (
    <Content width="narrow">
      <PageHeader title={title} description={description} crumbs={crumbs} />
      <Card>
        <form className="stack gap-4" onSubmit={form.submit} noValidate>
          <FormFields fields={fields} form={form} />
          <div className="row justify-end">
            {cancelHref && <a className="btn ghost" href={cancelHref}>취소</a>}
            <Button type="submit" loading={form.running}>{submitLabel}</Button>
          </div>
        </form>
      </Card>
    </Content>
  );
}
