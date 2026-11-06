"use client";
/**
 * 앱 골격 — 헤더(브랜드 · 메뉴 · 검색 · 테마 · 알림 · 조직 · 사용자) + 내비(top · side) + 콘텐츠 + 푸터 + 공통 상태(Providers) + 단축키 도움말.
 * 앱마다 다른 것은 이 설정으로만 둔다(ui.md 규칙 10). 메뉴는 게이트웨이 /v1/menu(권한으로 거른 것), 실패하면 fallback.
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React, { useEffect } from "react";
import { logout as logout_, type Menu } from "@nova/sdk";
import { useApi } from "../hooks";
import { Providers, useSession } from "../providers";
import { ShortcutHelp, ThemeToggle, type Shortcut } from "../components/extras";
import { Forbidden } from "../components/feedback";
import { Skeleton } from "../components/basic";
import { HeaderSearch, HeaderUtils, type HeaderConfig } from "../components/header";

export interface NavLink { href: string; label: string; icon?: string | null }

export interface AppConfig {
  id: string;
  brand: string;
  /** 브랜드 옆 작은 글자(앱 이름) */
  product?: string;
  logo?: React.ReactNode;
  menuChannel?: string;
  layout?: "top" | "side";
  footer?: React.ReactNode;
  fallbackLinks?: NavLink[];
  helpHref?: string;
  shortcuts?: Shortcut[];
  /** 옆 메뉴(layout "side") 색 — default 흰 표면 · deep 남색(nav 토큰 — 운영 콘솔형). top 레이아웃에는 영향 없음 */
  navTone?: "default" | "deep";
  /**
   * 헤더 유틸 — 전체 검색(Ctrl+K) · 알림 개수 · 조직(테넌트) 전환. 조직 전환은 앱이 넘긴 onSwitch(서버 재발급)로만 하고
   * 골격은 x-tenant · 저장소를 건드리지 않는다(STD-TENANCY-001). 없으면 지금과 같은 헤더
   */
  header?: HeaderConfig;
}

export function useMenu(channel: string, fallback: NavLink[] = []) {
  const { data } = useApi<Menu>("/menu", { channel });
  const links: NavLink[] = data ? data.items.map((i) => ({ href: i.path, label: i.label, icon: i.icon })) : fallback;
  return { links, features: data?.features ?? {}, maintenance: data?.maintenance ?? [] };
}

function isOn(path: string, href: string) {
  return href === "/" ? path === "/" : path === href || path.startsWith(href + "/");
}

/**
 * 옆 메뉴 — AppShell(layout "side")이 쓰고, 갤러리처럼 따로 보여 줄 때도 같은 부품을 쓴다.
 * `current` 는 지금 경로(그 아래 경로도 활성). `tone` deep 은 bg.nav · text.onNav* · bg.navActive · border.focusOnNav 만 쓴다
 * (남색 바탕에서 brand 활성 · 포커스는 대비 2.55 로 미달 — 계획 REQ_05 §1.1).
 */
export function Sidebar({ links, current, tone = "default" }: { links: NavLink[]; current: string; tone?: "default" | "deep" }) {
  return (
    <aside className={`sidebar${tone === "deep" ? " deep" : ""}`}>
      {links.map((l) => <Link key={l.href} href={l.href} aria-current={isOn(current, l.href) ? "page" : undefined}>{l.label}</Link>)}
    </aside>
  );
}

export function AppShell({ config, children }: { config: AppConfig; children: React.ReactNode }) {
  return (
    <Providers>
      <ShellInner config={config}>{children}</ShellInner>
      <ShortcutHelp extra={[...(config.header?.search ? [{ keys: "Ctrl+K", label: "전체 검색 칸으로 이동" }] : []), ...(config.shortcuts ?? [])]} />
    </Providers>
  );
}

function ShellInner({ config, children }: { config: AppConfig; children: React.ReactNode }) {
  const path = usePathname() || "/";
  const { user, setUser } = useSession();
  const router = useRouter();
  const { links, maintenance } = useMenu(config.menuChannel ?? "web", config.fallbackLinks ?? []);
  const layout = config.layout ?? "top";
  useEffect(() => { window.scrollTo(0, 0); }, [path]);
  // 화면 상태를 먼저 비우고, 서버 쿠키 삭제 요청은 반드시 보낸다(실패해도 sdk logout 이 캐시를 비운다)
  const logout = () => { void logout_().catch(() => {}); setUser(null); router.push("/login"); };
  const nav = (cls: string) => (
    <nav className={cls} aria-label="주 메뉴">
      {links.map((l) => <Link key={l.href} href={l.href} aria-current={isOn(path, l.href) ? "page" : undefined}>{l.label}</Link>)}
    </nav>
  );
  const header = (
    <header className="topbar">
      <div className={`topbar-in${layout === "side" ? " full" : ""}`}>
        <Link href="/" className="brand">{config.logo ?? <span className="mark" aria-hidden="true">{config.brand[0]}</span>}{config.brand}{config.product && <small className="hide-sm product">{config.product}</small>}</Link>
        {layout === "top" ? nav("nav grow") : <div className="grow" />}
        {config.header?.search && <HeaderSearch {...config.header.search} />}
        {config.helpHref && <Link href={config.helpHref} className="iconbtn" aria-label="도움말" title="도움말 (? 키: 단축키)">?</Link>}
        <ThemeToggle />
        {config.header && <HeaderUtils header={config.header} />}
        {user ? (
          <button type="button" className="userchip" onClick={logout} title="로그아웃"><span className="avatar">{user.name?.[0] ?? "?"}</span><span className="hide-sm">{user.name} · 로그아웃</span></button>
        ) : (
          <Link href="/login" className="btn primary sm">로그인</Link>
        )}
      </div>
    </header>
  );
  const banner = maintenance.length > 0 && (
    <div className="banner" role="status">점검 중: {maintenance.map((m) => `${m.label} — ${m.message}`).join(" · ")}</div>
  );
  if (layout === "side") {
    return (
      <>
        {header}{banner}
        <div className="sidebar-layout">
          <Sidebar links={links} current={path} tone={config.navTone} />
          <main id="main">{children}</main>
        </div>
      </>
    );
  }
  return (
    <>
      {header}{banner}
      <main id="main">{children}</main>
      {config.footer !== null && <footer className="footer">{config.footer ?? <span>{config.brand}</span>}</footer>}
    </>
  );
}

/** 로그인 · 역할 게이트 — 화면 단위 보호(서버 권한 검사가 진실, 이것은 안내용) */
export function RequireAuth({ roles, children }: { roles?: string[]; children: React.ReactNode }) {
  const { user, ready } = useSession();
  const router = useRouter();
  useEffect(() => { if (ready && !user) router.replace("/login"); }, [ready, user, router]);
  if (!ready || !user) return <div className="content default"><Skeleton height={120} /></div>;
  const superRole = process.env.NEXT_PUBLIC_SUPER_ROLE || "admin";
  if (roles && !roles.includes(user.role) && user.role !== superRole) {
    return <Forbidden hint={`이 화면은 ${roles.join(", ")} 역할 전용입니다`} />;
  }
  return <>{children}</>;
}
