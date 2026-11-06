/**
 * @nova/sdk — 게이트웨이(/v1) 타입드 클라이언트. 모든 웹 앱이 공유한다.
 * - 오류는 ApiError 하나로 통일(서버 봉투 {error:{code,message}} → message 는 사람이 읽는 문장, UX H9)
 * - 인증은 httpOnly 쿠키(credentials:"include") — 토큰을 저장 · 전송하지 않는다(ADR-014)
 * - 표시용 사용자 캐시만 localStorage(<접두어>_user), 접두어는 NEXT_PUBLIC_STORAGE_PREFIX(기본 nova)
 * - 게이트웨이 주소는 NEXT_PUBLIC_API_BASE(기본 http://localhost:8080/v1)
 * 업무 타입(주문 · 상품 …)은 여기 넣지 않고 각 앱의 lib/ 에 둔다.
 */
import { LOCALE as META_LOCALE, TIMEZONE as META_TIMEZONE } from "./project.gen";
import { EMAIL_MAX, EMAIL_PATTERN } from "./validate.gen";

export interface User { id: string; name: string; role: string; tenant?: string | null; email?: string }
export interface MenuItem { key: string; label: string; icon?: string | null; path: string }
export interface Menu { channel: string; items: MenuItem[]; maintenance: { key: string; label: string; message: string }[]; features: Record<string, boolean> }
/** 목록 API 계약(docs/conventions/ui.md §4) */
export interface Page<T> { items: T[]; total: number; page: number; size: number }
export type Query = Record<string, string | number | boolean | undefined | null>;

/** 칸별 입력 오류 — 422 {error:{code:"invalid_input", message, fields:[{loc:["body","name"], msg}]}} */
export interface FieldError { loc: (string | number)[]; msg: string; type?: string }

export class ApiError extends Error {
  /** 칸별 입력 오류(서버가 보내지 않았으면 빈 배열) */
  public fields: FieldError[];
  constructor(public status: number, public code: string, message: string, public body?: unknown) {
    super(message);
    this.fields = parseFields((body as { error?: { fields?: unknown } } | null | undefined)?.error?.fields);
  }
  /** 서버가 함께 보낸 추가 정보(perm · feature · retry_after …) */
  get detail(): Record<string, unknown> { return ((this.body as { error?: Record<string, unknown> })?.error) ?? {}; }
  /** 칸 이름 → 오류 문구. 칸 이름은 loc 의 마지막 문자열 조각(["body","name"] → "name"). 같은 칸이 여럿이면 처음 것 */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    for (const f of this.fields) {
      const key = [...f.loc].reverse().find((x): x is string => typeof x === "string");
      if (key && !(key in out)) out[key] = f.msg;
    }
    return out;
  }
}

function parseFields(raw: unknown): FieldError[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((f) => {
    const loc = (f as { loc?: unknown })?.loc;
    const msg = (f as { msg?: unknown })?.msg;
    if (!Array.isArray(loc)) return [];
    const type = (f as { type?: unknown }).type;
    return [{ loc: loc.filter((x): x is string | number => typeof x === "string" || typeof x === "number"), msg: typeof msg === "string" ? msg : "", type: typeof type === "string" ? type : undefined }];
  });
}

// Next 는 `process.env.NEXT_PUBLIC_…` 를 글자 그대로 적은 곳만 빌드 때 값으로 바꾼다 — `process.env[k]` 처럼 동적으로 읽으면
// 브라우저 번들에서 비어 늘 기본값(localhost:8080 · "nova")으로 간다(2026-11-04 T04-9.09 — 운영 웹이 8080 으로 요청하던 결함)
const PREFIX = process.env.NEXT_PUBLIC_STORAGE_PREFIX || "nova";
const LEGACY_TOKEN_KEY = `${PREFIX}_token`;
const USER_KEY = `${PREFIX}_user`;
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8080/v1";

export function apiBase(): string {
  return API_BASE.replace(/\/$/, "");
}

// 옛 방식(localStorage 토큰)이 남긴 키를 처음 쓰일 때 한 번 지운다. 이 정리 코드는 다음 판본(Contract)에서 걷어낸다(ADR-014)
let legacyCleaned = false;
function cleanLegacyToken() {
  if (legacyCleaned || typeof localStorage === "undefined") return;
  legacyCleaned = true;
  try { localStorage.removeItem(LEGACY_TOKEN_KEY); } catch { /* noop */ }
}

/** 세션 — 토큰은 httpOnly 쿠키라 자바스크립트가 읽지 못한다. 여기는 화면 깜빡임을 막는 표시용 사용자 캐시뿐 */
export const session = {
  user(): User | null {
    cleanLegacyToken();
    try { const u = localStorage.getItem(USER_KEY); return u ? (JSON.parse(u) as User) : null; } catch { return null; }
  },
  /** 사용자 캐시 저장 — 같은 사용자일 때만 기존 캐시와 합쳐 /me 응답에 없는 값(이메일)이 사라지지 않게 한다 */
  set(user: User) {
    cleanLegacyToken();
    // id 가 다르면 새 값으로 덮는다 — 공용 PC 에서 앞 사용자의 이메일 등이 다음 사용자 화면에 붙지 않게(개인정보 노출 방지)
    const prev = session.user();
    const next = prev && prev.id === user.id ? { ...prev, ...user } : user;
    try { localStorage.setItem(USER_KEY, JSON.stringify(next)); } catch { /* 사파리 프라이빗 등 */ }
  },
  clear() { cleanLegacyToken(); try { localStorage.removeItem(USER_KEY); } catch { /* noop */ } },
};

export function toQueryString(q?: Query): string {
  if (!q) return "";
  const s = new URLSearchParams(Object.entries(q).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => [k, String(v)])).toString();
  return s ? "?" + s : "";
}

export async function api<T = unknown>(path: string, init: { method?: string; body?: unknown; query?: Query; signal?: AbortSignal } = {}): Promise<T> {
  const headers: Record<string, string> = { accept: "application/json" };
  if (init.body !== undefined) headers["content-type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(apiBase() + path + toQueryString(init.query), {
      method: init.method || "GET", headers, signal: init.signal, cache: "no-store", credentials: "include", // 인증은 httpOnly 쿠키
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "network", "서버에 연결할 수 없습니다. 인터넷 연결을 확인하고 잠시 후 다시 시도하세요");
  }
  const text = await res.text();
  let data: unknown = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string } } | null)?.error ?? {};
    if (res.status === 401 && err.code === "invalid_token") session.clear();
    throw new ApiError(res.status, err.code ?? "error", err.message ?? defaultMessage(res.status), data);
  }
  return data as T;
}

/** 서버가 문구를 주지 않았을 때의 사람 말(UX H9 — 상태 코드만 보여 주지 않는다) */
export function defaultMessage(status: number): string {
  if (status === 401) return "로그인이 필요합니다";
  if (status === 403) return "이 기능을 쓸 권한이 없습니다";
  if (status === 404) return "찾는 항목이 없습니다. 이미 삭제되었을 수 있습니다";
  if (status === 409) return "다른 변경과 충돌했습니다. 새로고침 후 다시 시도하세요";
  if (status === 429) return "요청이 너무 많습니다. 잠시 후 다시 시도하세요";
  if (status >= 500) return "서버에 문제가 생겼습니다. 잠시 후 다시 시도하세요";
  return "요청을 처리하지 못했습니다";
}

export async function login(email: string, password: string): Promise<User> {
  // 응답 본문의 token 은 모바일용이다 — 웹은 쓰지 않고 서버가 심은 쿠키만 쓴다
  const r = await api<{ user: User }>("/auth/login", { method: "POST", body: { email, password } });
  session.set(r.user);
  return r.user;
}

/** 지금 로그인 사용자를 서버(쿠키)로 확인해 캐시를 갱신한다. 401 이면 호출한 쪽이 캐시를 비운다 */
export async function fetchMe(): Promise<User> {
  const u = await api<User>("/me");
  session.set(u);
  return session.user() ?? u;
}

/** 로그아웃 — 서버가 쿠키를 지운다. 요청이 실패해도 화면의 캐시는 반드시 비운다 */
export async function logout(): Promise<void> {
  try { await api<null>("/auth/logout", { method: "POST" }); } finally { session.clear(); }
}

/* ------------------------------------------------------------------ 입력 검사 (서버 계약과 같은 규칙 — plan_REQ_04 P9) */
export { EMAIL_MAX, EMAIL_PATTERN };
const EMAIL_RE = new RegExp(EMAIL_PATTERN);
/** 이메일 칸 오류 문구 — 형식이 맞으면 null. 빈 값은 '필수' 검사가 따로 알리므로 여기서는 null. 앞뒤 공백은 서버처럼 떼고 본다 */
export function emailError(v: string): string | null {
  const s = v.trim();
  if (!s) return null;
  return s.length <= EMAIL_MAX && EMAIL_RE.test(s) ? null : "이메일 형식이 아닙니다. 예: name@example.com";
}

/* ------------------------------------------------------------------ 표시 형식 (UX H2 — 사용자 지역 기준) */
// 기본값은 nova.project.json 에서 생성(project.gen.ts) — 값을 여기 다시 적지 않는다(R10). 참조는 글자 그대로(T04-9.09)
const LOCALE = process.env.NEXT_PUBLIC_LOCALE || META_LOCALE;
const TZ = process.env.NEXT_PUBLIC_TIMEZONE || META_TIMEZONE;

/** 서버 시각(UTC ISO, Z 없으면 UTC 로 간주) → 지역 시각 "2026-11-03 14:05" */
export function fmtAt(iso: string | null | undefined, opts: { tz?: string; seconds?: boolean } = {}): string {
  if (!iso) return "";
  const d = new Date(/(?:[zZ]|[+-]\d\d:\d\d)$/.test(iso) ? iso : iso + "Z");
  if (Number.isNaN(d.getTime())) return iso;
  const p = new Intl.DateTimeFormat("en-CA", { timeZone: opts.tz ?? TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: opts.seconds ? "2-digit" : undefined, hour12: false }).formatToParts(d);
  const g = (t: string) => p.find((x) => x.type === t)?.value ?? "";
  return `${g("year")}-${g("month")}-${g("day")} ${g("hour")}:${g("minute")}${opts.seconds ? ":" + g("second") : ""}`;
}

/** 상대 시각 "3분 전" */
export function fmtAgo(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "";
  const d = new Date(/(?:[zZ]|[+-]\d\d:\d\d)$/.test(iso) ? iso : iso + "Z").getTime();
  const s = Math.round((now - d) / 1000);
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
  if (Math.abs(s) < 60) return rtf.format(-s, "second");
  if (Math.abs(s) < 3600) return rtf.format(-Math.round(s / 60), "minute");
  if (Math.abs(s) < 86400) return rtf.format(-Math.round(s / 3600), "hour");
  return rtf.format(-Math.round(s / 86400), "day");
}

export const fmtNumber = (n: number | null | undefined, digits = 0) =>
  (n ?? 0).toLocaleString(LOCALE, { maximumFractionDigits: digits, minimumFractionDigits: digits });

export const fmtMoney = (n: number | null | undefined, currency = process.env.NEXT_PUBLIC_CURRENCY || "KRW") =>
  new Intl.NumberFormat(LOCALE, { style: "currency", currency, maximumFractionDigits: currency === "KRW" ? 0 : 2 }).format(n ?? 0);
