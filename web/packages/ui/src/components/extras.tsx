"use client";
/** 차트 · 단축키 도움말(UX H7 · H10) · 테마 전환. */
import React, { useEffect, useId, useState } from "react";
import { useDialogFocus, useShortcut } from "../hooks";

/**
 * 차트 계열 색 — i 번째 계열(0부터)의 색 토큰 chart.1~6 을 돌려 쓴다(일곱째는 다시 1). 다크는 토큰이 밝은 단계로 바뀐다.
 * 상태(위험 · 경고)를 뜻하는 색이 아니다 — 경보 수치는 상태 토큰 · 배지로.
 */
export function chartColor(i: number): string {
  return `var(--color-chart-${(((Math.trunc(i) % 6) + 6) % 6) + 1})`;
}

/** 차트 범례 — 계열 이름과 chartColor 견본. `series` 를 주지 않으면 순서대로 0, 1, 2 … */
export function ChartLegend({ items, label = "차트 범례" }: { items: { label: string; series?: number }[]; label?: string }) {
  return (
    <ul className="legend" role="list" aria-label={label}>
      {items.map((it, i) => <li key={it.label}><i aria-hidden="true" style={{ background: chartColor(it.series ?? i) }} />{it.label}</li>)}
    </ul>
  );
}

/** 작은 추이 선 — `series` 를 주면 그 계열 색(chartColor), 아니면 `color`(기본 주 행동 색 — 지금과 같다) */
export function Sparkline({ values, width = 120, height = 32, color = "var(--color-action-primary)", series, label }: { values: number[]; width?: number; height?: number; color?: string; series?: number; label?: string }) {
  const id = useId().replace(/:/g, "");
  const c = series === undefined ? color : chartColor(series);
  if (values.length < 2) return <svg className="spark" width={width} height={height} role="img" aria-label={label ?? "데이터 없음"} />;
  const max = Math.max(...values, 1e-9), min = Math.min(...values, 0);
  const pts = values.map((v, i) => [(i / (values.length - 1)) * width, height - 2 - ((v - min) / (max - min || 1)) * (height - 4)]);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  return (
    <svg className="spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label ?? `최근 값 ${values[values.length - 1]}`}>
      {/* 색은 style 로 — SVG 속성(stroke="var(…)")은 CSS 변수를 풀지 못하는 브라우저가 있다 */}
      <defs><linearGradient id={id} x1="0" x2="0" y1="0" y2="1"><stop offset="0" style={{ stopColor: c }} stopOpacity=".28" /><stop offset="1" style={{ stopColor: c }} stopOpacity="0" /></linearGradient></defs>
      <path d={`${d} L${width},${height} L0,${height} Z`} fill={`url(#${id})`} />
      <path d={d} fill="none" style={{ stroke: c }} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/** 막대 — 항목마다 `series` 를 주면 그 계열 색(chartColor), 없으면 주 행동 색(지금과 같다) */
export function Bars({ data, height = 140, format = (v: number) => String(v) }: { data: { label: string; value: number; series?: number }[]; height?: number; format?: (v: number) => string }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="bars" style={{ height }} role="img" aria-label={data.map((d) => `${d.label} ${format(d.value)}`).join(", ")}>
      {data.map((d) => (
        <div key={d.label} className="b" title={format(d.value)}>
          <span className="xs muted num">{d.value ? format(d.value) : ""}</span>
          <i style={{ height: `${Math.max(2, (d.value / max) * (height - 40))}px`, opacity: d.value ? 1 : 0.25, ...(d.series === undefined ? {} : { background: chartColor(d.series) }) }} />
          <span className="xs muted">{d.label}</span>
        </div>
      ))}
    </div>
  );
}

export interface Shortcut { keys: string; label: string }
export const DEFAULT_SHORTCUTS: Shortcut[] = [
  { keys: "?", label: "단축키 도움말 열기" },
  { keys: "/", label: "검색 칸으로 이동" },
  { keys: "n", label: "새로 만들기(목록 화면)" },
  { keys: "Esc", label: "대화상자 닫기 · 입력 취소" },
];

/** `?` 키로 여는 단축키 도움말 — AppShell 이 넣는다 */
export function ShortcutHelp({ extra = [] }: { extra?: Shortcut[] }) {
  const [open, setOpen] = useState(false);
  useShortcut("?", () => setOpen((v) => !v));
  // 열리면 '닫기' 버튼으로 포커스 · Tab 가두기 · Esc 닫기 · 닫으면 원래 자리로(WCAG 2.4.3)
  const ref = useDialogFocus<HTMLDivElement>(open, () => setOpen(false));
  if (!open) return null;
  return (
    <div className="dialog-backdrop" onClick={() => setOpen(false)}>
      <div ref={ref} tabIndex={-1} className="dialog" role="dialog" aria-modal="true" aria-labelledby="sc-title" onClick={(e) => e.stopPropagation()}>
        <h2 id="sc-title">단축키</h2>
        <dl className="kv mt-4">
          {[...DEFAULT_SHORTCUTS, ...extra].map((s) => <React.Fragment key={s.keys}><dt><kbd>{s.keys}</kbd></dt><dd>{s.label}</dd></React.Fragment>)}
        </dl>
        <div className="actions"><button type="button" className="btn secondary" onClick={() => setOpen(false)}>닫기</button></div>
      </div>
    </div>
  );
}

const THEME_KEY = `${process.env.NEXT_PUBLIC_STORAGE_PREFIX || "nova"}_theme`;

export function ThemeToggle() {
  const [t, setT] = useState<string | null>(null);
  useEffect(() => {
    let v: string | null = null;
    try { v = localStorage.getItem(THEME_KEY); } catch { /* noop */ }
    setT(v);
    if (v) document.documentElement.dataset.theme = v;
  }, []);
  const flip = () => {
    const dark = t ? t === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    const n = dark ? "light" : "dark";
    document.documentElement.dataset.theme = n;
    try { localStorage.setItem(THEME_KEY, n); } catch { /* noop */ }
    setT(n);
  };
  return <button type="button" className="iconbtn" onClick={flip} aria-label="라이트 · 다크 테마 전환" title="테마 전환">◐</button>;
}
