"use client";
/**
 * 헤더 유틸 — 전체 검색(Ctrl+K) · 알림 · 조직(테넌트) 전환. AppShell 이 `config.header` 로 넣고, 갤러리처럼 따로 보여 줄 때도 같은 부품을 쓴다.
 * 조직 전환은 표시 · 요청 자리만 둔다: 실제 전환은 앱이 넘긴 onSwitch(서버가 토큰을 다시 내줌)로만 하고,
 * 이 부품은 x-tenant 헤더 · 브라우저 저장소를 건드리지 않는다(STD-TENANCY-001 §③ — 테넌트는 서버가 정한다).
 */
import Link from "next/link";
import React, { useEffect, useRef, useState } from "react";
import { useAction } from "../hooks";

export interface HeaderSearchConfig { placeholder?: string; onSearch: (q: string) => void }
export interface HeaderNotifications { count: number; href: string }
export interface HeaderTenants { current: string; items: { id: string; label: string }[]; onSwitch: (id: string) => Promise<void> }
export interface HeaderConfig { search?: HeaderSearchConfig; notifications?: HeaderNotifications; tenants?: HeaderTenants }

/**
 * 전체 검색 칸 — Ctrl+K(맥은 ⌘K)로 어디서든 이 칸으로 온다. 목록 검색 `/` · 새로 만들기 `n` 과 겹치지 않게 Ctrl 조합을 쓴다(UX H7).
 * 이 칸에 글을 쓰는 동안 `/` · `n` 은 글자일 뿐이다(useShortcut 이 입력 칸을 건너뛴다). Esc 는 칸을 떠난다.
 */
export function HeaderSearch({ placeholder = "전체 검색", onSearch }: HeaderSearchConfig) {
  const ref = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // 입력 칸 안에서도 동작한다 — 조합 키라 글자 입력과 부딪히지 않는다
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "k") {
        e.preventDefault(); // 브라우저 주소창 검색으로 가지 않게
        ref.current?.focus();
        ref.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <form className="hsearch" role="search" onSubmit={(e) => { e.preventDefault(); const v = q.trim(); if (v) onSearch(v); }}>
      <label htmlFor="header-q" className="sr-only">전체 검색</label>
      <input id="header-q" ref={ref} type="search" className="hsearch-input" placeholder={placeholder} value={q} autoComplete="off"
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.currentTarget.blur(); } }} />
      <span className="hide-sm hsearch-keys" aria-hidden="true"><kbd>Ctrl</kbd><kbd>K</kbd></span>
    </form>
  );
}

/** 알림 — 개수만 받고(실시간 푸시 · 알림 API 는 앱 몫) 누르면 앱의 알림 화면으로 간다. 0 이면 숫자를 숨긴다 */
export function NotificationLink({ count, href }: HeaderNotifications) {
  const shown = count > 99 ? "99+" : String(count);
  return (
    <Link href={href} className="iconbtn notif" aria-label={count > 0 ? `알림 ${count}건` : "알림 없음"} title="알림">
      <span aria-hidden="true">🔔</span>{count > 0 && <span className="count" aria-hidden="true">{shown}</span>}
    </Link>
  );
}

/**
 * 조직(테넌트) 전환 — 지금 조직을 보이고, 고르면 onSwitch 를 부른다. 실패하면 지금 조직 그대로 · 오류 토스트(반쯤 바뀐 상태 금지).
 * 표시는 늘 앱이 준 `current` — 이 부품은 전환 결과를 혼자 기억하지 않는다.
 */
export function TenantSwitcher({ current, items, onSwitch }: HeaderTenants) {
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const label = (id: string) => items.find((i) => i.id === id)?.label ?? id;
  const sw = useAction((id: string) => onSwitch(id), { success: (_r, id) => `${label(id)}(으)로 전환했습니다` });
  const close = (focus = true) => { setOpen(false); if (focus) btn.current?.focus(); };
  useEffect(() => {
    if (!open) return;
    const list = () => Array.from(menu.current?.querySelectorAll<HTMLButtonElement>("[role=menuitemradio]") ?? []);
    (list().find((b) => b.getAttribute("aria-checked") === "true") ?? list()[0])?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); return; }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const l = list(); const i = l.indexOf(document.activeElement as HTMLButtonElement);
        l[(i + (e.key === "ArrowDown" ? 1 : -1) + l.length) % l.length]?.focus();
      }
    };
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!menu.current?.contains(t) && !btn.current?.contains(t)) close(false);
    };
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("mousedown", onDown);
    return () => { document.removeEventListener("keydown", onKey, true); document.removeEventListener("mousedown", onDown); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  const pick = async (id: string) => {
    close();
    if (id === current) return;
    await sw.run(id); // 실패는 useAction 이 오류 토스트로 — current 는 앱이 바꾸지 않았으므로 그대로
  };
  return (
    <div className="tenant-wrap">
      <button ref={btn} type="button" className="tenant" aria-haspopup="menu" aria-expanded={open} aria-label={`조직 전환 — 지금 ${label(current)}`}
        aria-busy={sw.running || undefined} onClick={() => (open ? close() : setOpen(true))} title={`지금 조직: ${label(current)}`}>
        {sw.running && <span className="spinner" aria-hidden="true" />}
        <span>{label(current)}</span><small className="hide-sm">(전환)</small>
      </button>
      {open && (
        <div ref={menu} className="menu" role="menu" aria-label="조직 전환">
          {items.map((i) => (
            <button key={i.id} type="button" role="menuitemradio" aria-checked={i.id === current} onClick={() => pick(i.id)}>
              {i.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** 헤더 오른쪽 유틸 묶음 — 알림 · 조직 전환(검색은 브랜드 옆에 따로 둔다) */
export function HeaderUtils({ header }: { header: HeaderConfig }) {
  return (
    <>
      {header.notifications && <NotificationLink {...header.notifications} />}
      {header.tenants && <TenantSwitcher {...header.tenants} />}
    </>
  );
}
