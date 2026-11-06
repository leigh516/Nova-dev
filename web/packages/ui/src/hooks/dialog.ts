"use client";
/**
 * 대화상자 포커스 — 모든 모달(확인 대화상자 · 단축키 도움말 …)이 같은 방식으로 움직이게 한다(WCAG 2.1.2 · 2.4.3, UX H3).
 * 1) 연 요소(버튼 등)를 기억한다 → 2) 첫 버튼(또는 initial)에 포커스 → 3) Tab · Shift+Tab 은 대화상자 안에서만 돈다
 * → 4) Esc 로 닫는다 → 5) 닫히면 연 요소로 포커스를 돌려준다(그 요소가 사라졌으면 그대로 둔다).
 * 겹쳐 열리면(폼 모달 위 확인 대화상자) 맨 위 것만 키를 받는다.
 * 사용: `const ref = useDialogFocus<HTMLDivElement>(open, close)` → `<div ref={ref} role="dialog" tabIndex={-1}>`
 * 이 파일은 providers 를 가져오지 않는다(providers → hooks/dialog 단방향, 순환 참조 방지).
 */
import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE = [
  "a[href]", "button:not([disabled])", "input:not([disabled]):not([type=hidden])", "select:not([disabled])",
  "textarea:not([disabled])", "[tabindex]:not([tabindex='-1'])", "[contenteditable='true']",
].join(",");

/**
 * 열린 대화상자 차례 — 폼 모달 위에 확인 대화상자가 겹치면 **맨 위 하나만** Tab 가두기 · Esc 를 맡는다
 * (둘 다 document 에서 듣기 때문에 아래 것이 Esc 를 다시 받거나 포커스를 끌어가면 안 된다).
 */
const stack: symbol[] = [];

function focusables(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => !el.hasAttribute("inert") && el.getClientRects().length > 0);
}

export function useDialogFocus<T extends HTMLElement = HTMLDivElement>(
  open: boolean,
  onClose: () => void,
  opts: { initial?: RefObject<HTMLElement | null> } = {},
): RefObject<T | null> {
  const ref = useRef<T>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose; // 부모가 매번 새 함수를 넘겨도 포커스를 다시 잡지 않게 ref 로 둔다
  const initialRef = opts.initial;

  useEffect(() => {
    if (!open) return;
    const me = Symbol("dialog");
    stack.push(me);
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const root = ref.current;
    if (root) (initialRef?.current ?? focusables(root)[0] ?? root).focus();

    const onKey = (e: KeyboardEvent) => {
      if (stack[stack.length - 1] !== me) return; // 위에 다른 대화상자가 떠 있다 — 그쪽이 맡는다
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation(); // 뒤에 깔린 화면의 Esc 처리(입력 취소 등)까지 가지 않게
        closeRef.current();
        return;
      }
      if (e.key !== "Tab" || !root) return;
      const list = focusables(root);
      if (list.length === 0) { e.preventDefault(); root.focus(); return; }
      const first = list[0], last = list[list.length - 1];
      const active = document.activeElement;
      const outside = !active || !root.contains(active);
      if (e.shiftKey && (active === first || active === root || outside)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && (active === last || outside)) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      stack.splice(stack.indexOf(me), 1);
      if (opener && opener.isConnected) opener.focus(); // 원래 자리로(삭제로 사라진 버튼이면 건너뜀)
    };
  }, [open, initialRef]);

  return ref;
}
