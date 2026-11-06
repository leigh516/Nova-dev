"use client";
/**
 * 앱 공통 상태 — 세션 · 토스트(실행 취소 포함) · 확인 대화상자.
 * AppShell 이 감싸므로 화면은 useSession · useToast · useConfirm 만 쓴다.
 * UX: H1(결과를 토스트로 보인다) · H3(실행 취소 · 취소 버튼 · ESC) · H9(오류 문구는 사람 말)
 */
import React, { createContext, useCallback, useContext, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ApiError, fetchMe, session, type User } from "@nova/sdk";
import { useDialogFocus } from "./hooks/dialog";

/* ------------------------------------------------------------------ 세션
 * useSyncExternalStore — 하이드레이션 중에는 서버 값(비로그인 · ready=false)을 쓰고, 끝난 뒤 실제 값으로 바뀐다.
 * (useState + useEffect 로 하면 Suspense 안 화면이 늦게 하이드레이션될 때 서버 HTML 과 달라져 React #418 이 난다)
 */
const listeners = new Set<() => void>();
let cache: { raw: string | null; user: User | null } = { raw: null, user: null };

function readUser(): User | null {
  let raw: string | null = null;
  try { raw = JSON.stringify(session.user()); } catch { raw = null; }
  if (raw !== cache.raw) cache = { raw, user: raw ? (JSON.parse(raw) as User | null) : null };
  return cache.user;
}
function subscribe(fn: () => void) {
  listeners.add(fn);
  const onStorage = () => fn(); // 다른 탭에서 로그인 · 로그아웃
  window.addEventListener("storage", onStorage);
  return () => { listeners.delete(fn); window.removeEventListener("storage", onStorage); };
}
const noop = () => () => {};

// 시작 시 /me 로 쿠키 세션을 한 번 확인한다(앱 수명 동안 한 번). 캐시는 표시용일 뿐 진실은 서버다(ADR-014)
let meChecked = false;
function verifyOnce() {
  if (meChecked) return;
  meChecked = true;
  fetchMe().then(
    () => listeners.forEach((l) => l()),
    (e) => {
      // 401 이면 캐시를 비워 로그인으로 보낸다. 네트워크 오류(status 0) · 그 밖은 캐시를 건드리지 않는다(오프라인 로그아웃 방지)
      if (e instanceof ApiError && e.status === 401) { session.clear(); listeners.forEach((l) => l()); }
    },
  );
}

/** 로그인 사용자 · 하이드레이션 완료 여부 · 사용자 바꾸기(로그인 직후 · 로그아웃) */
export function useSession() {
  const user = useSyncExternalStore(subscribe, readUser, () => null);
  const ready = useSyncExternalStore(noop, () => true, () => false);
  useEffect(() => { verifyOnce(); }, []); // effect 안 — 하이드레이션 중 서버 HTML 과 달라지지 않게
  const setUser = useCallback((u: User | null) => {
    if (!u) session.clear();
    listeners.forEach((l) => l());
  }, []);
  return { user, ready, setUser };
}

/* ------------------------------------------------------------------ 토스트 */
export interface ToastOptions { error?: boolean; undo?: () => void | Promise<void>; undoLabel?: string; ms?: number }
type ToastFn = (message: string, opts?: ToastOptions) => void;
const Toast = createContext<ToastFn>(() => {});
export const useToast = () => useContext(Toast);

/* ------------------------------------------------------------------ 확인 대화상자 */
export interface ConfirmOptions { title: string; message?: string; confirmLabel?: string; cancelLabel?: string; danger?: boolean }
type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>;
const Confirm = createContext<ConfirmFn>(async () => false);
/** window.confirm 대신 — `if (await confirm({title: "삭제할까요?", danger: true})) ...` */
export const useConfirm = () => useContext(Confirm);

interface ToastItem extends ToastOptions { id: number; message: string }

/** 되돌리기 실패 문구 — 서버 문구가 있으면 그대로, 없으면 사람 말(UX H9) */
function undoErrorMessage(e: unknown): string {
  if (e instanceof ApiError && e.message) return e.message;
  return "되돌리지 못했습니다. 잠시 후 다시 시도하세요";
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [dialog, setDialog] = useState<(ConfirmOptions & { resolve: (v: boolean) => void }) | null>(null);
  const seq = useRef(0);

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  // 사라지는 시각은 ToastView 가 센다 — 마우스 · 포커스가 올라가 있으면 멈춘다(WCAG 2.2.1, UX H3)
  const toast = useCallback<ToastFn>((message, opts = {}) => {
    const id = ++seq.current;
    setToasts((t) => [...t.slice(-2), { id, message, ...opts }]);
  }, []);

  const undo = useCallback(async (t: ToastItem) => {
    dismiss(t.id); // 두 번 누르지 않게 먼저 닫는다
    try {
      await t.undo?.();
      toast("되돌렸습니다");
    } catch (e) {
      toast(undoErrorMessage(e), { error: true }); // 실패를 조용히 넘기지 않는다(UX H1 · H9)
    }
  }, [dismiss, toast]);

  const confirm = useCallback<ConfirmFn>((opts) => new Promise<boolean>((resolve) => setDialog({ ...opts, resolve })), []);
  const close = (v: boolean) => { dialog?.resolve(v); setDialog(null); };

  const view = (t: ToastItem) => <ToastView key={t.id} item={t} onDone={dismiss} onUndo={undo} />;
  return (
    <>
      <Toast.Provider value={toast}>
        <Confirm.Provider value={confirm}>
          {children}
          {/* 알림 영역은 처음부터 있어야 스크린리더가 새 토스트를 읽는다 — 일반은 polite, 오류는 alert(assertive) */}
          <div className="toasts">
            <div className="toast-region" role="status" aria-live="polite">{toasts.filter((t) => !t.error).map(view)}</div>
            <div className="toast-region" role="alert">{toasts.filter((t) => t.error).map(view)}</div>
          </div>
          {dialog && <ConfirmDialog {...dialog} onClose={close} />}
        </Confirm.Provider>
      </Toast.Provider>
    </>
  );
}

/** 토스트 하나 — 기본 3초(실행 취소가 있으면 6초). 마우스가 올라가 있거나 포커스가 안에 있으면 멈추고, 떠나면 남은 시간부터 다시 센다 */
function ToastView({ item, onDone, onUndo }: { item: ToastItem; onDone: (id: number) => void; onUndo: (t: ToastItem) => void }) {
  const remaining = useRef(item.ms ?? (item.undo ? 6000 : 3000));
  const [hover, setHover] = useState(false);
  const [focused, setFocused] = useState(false);
  const paused = hover || focused;
  const done = useRef(onDone);
  done.current = onDone;
  useEffect(() => {
    if (paused) return;
    const ms = Math.max(remaining.current, 1500); // 다시 셀 때 바로 사라지지 않게 최소 1.5초
    const start = Date.now();
    const timer = setTimeout(() => done.current(item.id), ms);
    return () => { clearTimeout(timer); remaining.current = ms - (Date.now() - start); };
  }, [paused, item.id]);
  return (
    <div
      className={`toast ${item.error ? "error" : ""}`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocus={() => setFocused(true)}
      onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setFocused(false); }}
    >
      <span>{item.message}</span>
      {item.undo && (
        <button type="button" onClick={() => onUndo(item)}>
          {item.undoLabel ?? "실행 취소"}
        </button>
      )}
    </div>
  );
}

export function ConfirmDialog({ title, message, confirmLabel = "확인", cancelLabel = "취소", danger, onClose }: ConfirmOptions & { onClose: (v: boolean) => void }) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  // 위험한 쪽이 기본 선택이 되지 않게 취소에 포커스(UX H5) · Tab 가두기 · Esc 닫기 · 닫으면 연 버튼으로 복귀
  const ref = useDialogFocus<HTMLDivElement>(true, () => onClose(false), { initial: cancelRef });
  return (
    <div className="dialog-backdrop" onClick={() => onClose(false)}>
      <div ref={ref} tabIndex={-1} className="dialog" role="alertdialog" aria-modal="true" aria-labelledby="dlg-title" aria-describedby={message ? "dlg-msg" : undefined} onClick={(e) => e.stopPropagation()}>
        <h2 id="dlg-title">{title}</h2>
        {message && <p id="dlg-msg">{message}</p>}
        <div className="actions">
          <button ref={cancelRef} type="button" className="btn secondary" onClick={() => onClose(false)}>{cancelLabel}</button>
          <button type="button" className={`btn ${danger ? "danger" : "primary"}`} onClick={() => onClose(true)}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
