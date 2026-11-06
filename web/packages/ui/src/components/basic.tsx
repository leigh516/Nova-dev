"use client";
/** 기본 컴포넌트 — 화면은 원시 <button> · <input> 대신 이것을 쓴다(ui.md §6). 웹 · 모바일 같은 이름. */
import React, { useId } from "react";

export type Variant = "primary" | "secondary" | "ghost" | "danger";
export type Size = "sm" | "md" | "lg";
export type Tone = "neutral" | "info" | "success" | "warning" | "danger" | "link";

export function Button({ variant = "primary", size = "md", loading, block, children, className = "", disabled, type = "button", onClick, ...rest }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean; block?: boolean }) {
  // 진행 중(loading)에는 native disabled 를 쓰지 않는다 — disabled 가 되면 포커스가 문서 처음으로 빠져
  // 키보드 · 화면 읽기 사용자가 자리를 잃는다(감사 A-F1 · UX-H1). aria-disabled 로 알리고 클릭 · Enter · Space 를
  // 여기서 막는다(submit 버튼이면 preventDefault 가 폼 제출 · 암묵 제출까지 막는다). 모양은 styles.css 의
  // .btn[aria-disabled="true"] 가 disabled 와 같게 그린다. 진행 중 알림은 aria-busy.
  const busy = Boolean(loading) && !disabled;
  return (
    <button type={type} className={`btn ${variant} ${size === "md" ? "" : size} ${block ? "block" : ""} ${className}`}
      disabled={disabled} aria-busy={loading || undefined} {...rest} aria-disabled={busy ? true : rest["aria-disabled"]}
      onClick={(e) => { if (busy) { e.preventDefault(); return; } onClick?.(e); }}>
      {loading && <span className="spinner" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Spinner({ label = "불러오는 중" }: { label?: string }) {
  return <span className="spinner" role="status" aria-label={label} />;
}

export function Skeleton({ height = 16, width = "100%" }: { height?: number; width?: number | string }) {
  return <div className="skeleton" style={{ height, width }} aria-hidden="true" />;
}

export function Content({ width = "default", children }: { width?: "narrow" | "default" | "wide" | "full"; children: React.ReactNode }) {
  return <div className={`content ${width === "full" ? "" : width}`}>{children}</div>;
}

export function PageHeader({ title, description, actions, crumbs }: { title: string; description?: React.ReactNode; actions?: React.ReactNode; crumbs?: { href: string; label: string }[] }) {
  return (
    <div className="page-header">
      <div>
        {crumbs && crumbs.length > 0 && (
          <nav className="crumbs" aria-label="현재 위치">{crumbs.map((c, i) => <span key={c.href}>{i > 0 && "› "}<a href={c.href}>{c.label}</a></span>)}</nav>
        )}
        <h1>{title}</h1>
        {description && <p className="desc">{description}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}

export function Section({ title, actions, children }: { title: string; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="section">
      <div className="section-head"><h3>{title}</h3>{actions}</div>
      {children}
    </section>
  );
}

export function Card({ children, flush, className = "" }: { children: React.ReactNode; flush?: boolean; className?: string }) {
  return <div className={`card ${flush ? "flush" : ""} ${className}`}>{children}</div>;
}

/**
 * 배지 — 기본은 옅은 바탕(status.*Bg · *Fg). `solid` 는 진한 바탕(status.*Solid · onSolid)으로 경보를 강조할 때만 쓴다
 * (화면당 한 곳 권장 — 남발하면 강조가 사라진다, UX H8). link 는 솔리드 토큰이 없어 옅은 배지로 그린다.
 */
export function Badge({ tone = "neutral", solid, children }: { tone?: Tone; solid?: boolean; children: React.ReactNode }) {
  return <span className={`badge ${tone}${solid && tone !== "link" ? " solid" : ""}`}>{children}</span>;
}

/** 상태 배지 — 라벨 · 색은 서버 설정에서 읽은 매핑을 넘긴다(enum · 색 하드코딩 금지, ui.md 규칙 6) */
export function StatusBadge({ code, map, solid }: { code: string; map: Record<string, { label: string; tone?: Tone }>; solid?: boolean }) {
  const m = map[code];
  return <Badge tone={m?.tone ?? "neutral"} solid={solid}>{m?.label ?? code}</Badge>;
}

/**
 * AI 표식 — AI 가 만든 초안 · 요약에 붙인다(STD-AX L1). 색은 ai.* 토큰만. 글자 "AI" 를 함께 써서 색만으로 뜻을 전하지 않는다.
 * 화면 읽기는 `label`(기본 "AI 생성")을 읽는다. 실행 제안(L2)은 표식이 아니라 AI 확인 카드로 한다.
 */
export function AiMark({ text = "AI", label = "AI 생성" }: { text?: string; label?: string }) {
  return <span className="ai-mark" role="img" aria-label={label}><span aria-hidden="true">✦</span>{text}</span>;
}

export type DomainSlot = 1 | 2 | 3 | 4 | 5 | 6;

/**
 * 도메인(업무 모듈) 식별 태그 — 모듈 → 번호 슬롯(1~6) 매핑은 데이터로 받는다(코어는 업종 이름을 모른다, STD-DOMAIN-PACK).
 * 색은 domain.N.mark(점) · domain.N.text(글자)만 — 상태색과 섞지 않는다(상태는 옆에 StatusBadge 로 따로).
 * 매핑에 없는 코드는 색 없이 코드 그대로 보인다.
 */
export function DomainTag({ code, map }: { code: string; map: Record<string, { label: string; slot: DomainSlot }> }) {
  const m = map[code];
  return <span className={`domain-tag${m ? ` d${m.slot}` : ""}`} data-slot={m?.slot}>{m?.label ?? code}</span>;
}

export function Stat({ label, value, delta }: { label: string; value: React.ReactNode; delta?: React.ReactNode }) {
  return <div className="stat"><span className="k">{label}</span><span className="v">{value}</span>{delta && <span className="d">{delta}</span>}</div>;
}

export function KeyValue({ items }: { items: { label: string; value: React.ReactNode }[] }) {
  return <dl className="kv">{items.map((i) => <React.Fragment key={i.label}><dt>{i.label}</dt><dd>{i.value ?? "—"}</dd></React.Fragment>)}</dl>;
}

/** 입력 칸 래퍼 — 라벨 · 필수 표시 · 도움말 · 오류(UX H5 · H9 · 접근성 라벨 연결) */
/** inline — 칸 옆에 라벨(스위치 · 체크박스). 라벨 id 는 `${id}-label`(aria-labelledby 로 쓸 수 있다) */
export function Field({ label, required, help, error, id: givenId, inline, children }: { label: string; required?: boolean; help?: string; error?: string | null; id?: string; inline?: boolean; children: (props: { id: string; "aria-invalid"?: boolean; "aria-describedby"?: string; "aria-required"?: boolean }) => React.ReactNode }) {
  const auto = useId();
  const id = givenId ?? auto; // 라벨 · 오류 · 도움말이 같은 id 로 이어져야 스크린리더가 읽는다
  const desc = error ? `${id}-err` : help ? `${id}-help` : undefined;
  const lab = <label id={`${id}-label`} htmlFor={id}>{label}{required && <span className="req" aria-hidden="true">*</span>}</label>;
  const control = children({ id, "aria-invalid": error ? true : undefined, "aria-describedby": desc, "aria-required": required || undefined });
  return (
    <div className={inline ? "field inline" : "field"}>
      {inline ? <div className="field-row">{control}{lab}</div> : <>{lab}{control}</>}
      {error ? <span id={`${id}-err`} className="err" role="alert">{error}</span> : help ? <span id={`${id}-help`} className="help">{help}</span> : null}
    </div>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className="input" {...props} />;
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className="textarea" {...props} />;
}

export function Select({ options, placeholder, ...rest }: React.SelectHTMLAttributes<HTMLSelectElement> & { options: { value: string; label: string }[]; placeholder?: string }) {
  return (
    <select className="select" {...rest}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label?: string }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>{o.label}</button>)}
    </div>
  );
}

export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return <button type="button" role="switch" className="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={() => onChange(!checked)} />;
}
