"use client";
/**
 * 데이터 · 액션 훅.
 * - useApi: 조회(로딩 · 오류 · 다시 불러오기 · 주기 갱신)
 * - useAction: 서버 호출 버튼의 유일한 방식(진행 중 비활성 · 성공/오류 토스트 · 확인 · 실행 취소 · 후속 새로고침) — ui.md 규칙 4
 * - useQueryState: 검색 · 필터 · 페이지 상태를 URL 에 남긴다(UX H6 — 돌아와도 유지)
 * - useShortcut: 단축키(UX H7)
 * - useDialogFocus: 대화상자 포커스 가두기 · 복귀(hooks/dialog.ts)
 */
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, type Query } from "@nova/sdk";
import { useConfirm, useToast, type ConfirmOptions } from "../providers";

export { useDialogFocus } from "./dialog";

export function useApi<T>(path: string | null, query?: Query, opts: { poll?: number } = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(!!path);
  const key = path ? path + JSON.stringify(query ?? {}) : null;
  const alive = useRef(true);
  const load = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try {
      const d = await api<T>(path, { query });
      if (alive.current) { setData(d); setError(null); }
    } catch (e) {
      if (alive.current) setError(e instanceof ApiError ? e : new ApiError(0, "client", String(e)));
    } finally {
      if (alive.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => {
    alive.current = true;
    load();
    if (!opts.poll) return () => { alive.current = false; };
    const t = setInterval(load, opts.poll);
    return () => { alive.current = false; clearInterval(t); };
  }, [load, opts.poll]);
  return { data, error, loading, reload: load, setData };
}

export interface ActionOptions<A extends unknown[], R> {
  /** 성공 토스트 문구(없으면 토스트 없음). 함수면 결과로 만든다 */
  success?: string | ((r: R, ...args: A) => string);
  /** 되돌릴 수 없는 액션 — 확인 대화상자를 먼저 띄운다 */
  confirm?: ConfirmOptions | ((...args: A) => ConfirmOptions);
  /** 되돌릴 수 있는 액션 — 성공 토스트에 '실행 취소' 버튼 */
  undo?: (r: R, ...args: A) => void | Promise<void>;
  /** 성공 뒤 할 일(목록 새로고침 · 이동) */
  then?: (r: R, ...args: A) => void | Promise<void>;
}

/** 서버 호출 버튼 — `const save = useAction(fn, {success: "저장했습니다", then: reload})` → `<Button loading={save.running} onClick={() => save.run(x)}>` */
export function useAction<A extends unknown[], R>(fn: (...args: A) => Promise<R>, opts: ActionOptions<A, R> = {}) {
  const toast = useToast();
  const confirm = useConfirm();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const busy = useRef(false);
  const run = useCallback(async (...args: A): Promise<R | undefined> => {
    if (busy.current) return undefined; // 중복 제출 방지(UX H5)
    if (opts.confirm) {
      const c = typeof opts.confirm === "function" ? opts.confirm(...args) : opts.confirm;
      if (!(await confirm(c))) return undefined;
    }
    busy.current = true;
    setRunning(true);
    setError(null);
    try {
      const r = await fn(...args);
      const msg = typeof opts.success === "function" ? opts.success(r, ...args) : opts.success;
      if (msg) toast(msg, opts.undo ? {
        // 되돌리기 실패는 Providers 가 오류 토스트로 알린다(여기서 삼키지 않는다). 성공 뒤 새로고침 실패만 따로 알린다
        undo: async () => {
          await opts.undo?.(r, ...args);
          try { await opts.then?.(r, ...args); }
          catch (e) { toast(e instanceof ApiError ? e.message : "되돌렸지만 화면을 새로 고치지 못했습니다. 새로고침하세요", { error: true }); }
        },
      } : undefined);
      await opts.then?.(r, ...args);
      return r;
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(0, "client", String(e));
      setError(err);
      toast(err.message, { error: true });
      return undefined;
    } finally {
      busy.current = false;
      setRunning(false);
    }
  }, [fn, opts, toast, confirm]);
  return { run, running, error };
}

/** URL 쿼리와 묶인 상태 — `const [q, setQ] = useQueryState("q", "")` */
export function useQueryState(key: string, initial = ""): [string, (v: string) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const value = params?.get(key) ?? initial;
  const set = useCallback((v: string) => {
    const next = new URLSearchParams(params?.toString() ?? "");
    if (v && v !== initial) next.set(key, v); else next.delete(key);
    if (key !== "page") next.delete("page"); // 조건이 바뀌면 1쪽부터
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [router, pathname, params, key, initial]);
  return [value, set];
}

/** 단축키 — 입력 칸에 글을 쓰는 중에는 동작하지 않는다(Escape 제외). key 예: "/", "?", "n", "Escape" */
export function useShortcut(key: string, handler: (e: KeyboardEvent) => void, enabled = true) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      const typing = !!t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
      if (typing && key !== "Escape") return;
      if (e.key === key && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); ref.current(e); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [key, enabled]);
}
