"use client";
/**
 * 폼 모달 — 화면을 떠나지 않고 짧은 입력을 받는다. 필드 렌더 · 검사 · 서버 칸 오류는 FormPage 와 같은 것(components/form.tsx).
 * - 포커스: 열면 첫 칸, Tab 은 안에서만 돌고, 닫히면 연 버튼으로 돌아간다(useDialogFocus — WCAG 2.1.2 · 2.4.3)
 * - 닫기: Esc · 바깥 누름 · 취소. 입력한 것이 있으면 버릴지 먼저 묻는다(useConfirm, UX H3 · H5)
 * - 저장: useAction(진행 중 잠금 · 성공 토스트 · 실패 시 입력 유지) → 성공하면 onClose
 * 사용: `<FormDialog open={open} title="연락처 추가" fields={…} onSubmit={(v) => api(…)} onClose={() => setOpen(false)} />`
 */
import React, { useId, useRef } from "react";
import { useDialogFocus } from "../hooks";
import { useConfirm } from "../providers";
import { Button } from "./basic";
import { FormFields, useFormModel, type FormField, type FormValues } from "./form";

/** V 는 onSubmit 값의 모양(기본 FormValues — 글 · 선택 · 날짜는 string, 스위치 · 체크박스는 boolean) */
export interface FormDialogProps<V extends FormValues = FormValues> {
  open: boolean;
  title: string;
  /** 폭 — sm(짧은 한두 칸) · md(기본) · lg(긴 글 칸) */
  size?: "sm" | "md" | "lg";
  fields: FormField[];
  initial?: Partial<V>;
  submitLabel?: string;
  /** 성공 토스트 문구(기본 "저장했습니다") */
  success?: string;
  description?: React.ReactNode;
  onSubmit: (v: V) => Promise<unknown>;
  onClose: () => void;
}

export function FormDialog<V extends FormValues = FormValues>(p: FormDialogProps<V>) {
  // 닫혀 있으면 그리지 않는다 — 다시 열 때마다 initial 로 새로 시작한다(지난 입력이 남지 않게)
  if (!p.open) return null;
  return <FormDialogBody<V> {...p} />;
}

function FormDialogBody<V extends FormValues>({ title, size = "md", fields, initial, submitLabel = "저장", success = "저장했습니다", description, onSubmit, onClose }: FormDialogProps<V>) {
  const confirm = useConfirm();
  const asking = useRef(false);
  const titleId = useId();
  const form = useFormModel<V>({ fields, initial, onSubmit, success, then: onClose, idPrefix: `fd${titleId.replace(/[^a-zA-Z0-9]/g, "")}` });
  const requestClose = async () => {
    if (form.running || asking.current) return; // 저장 중에는 닫지 않는다(결과를 모른 채 사라지면 안 된다)
    if (form.dirty) {
      asking.current = true;
      const ok = await confirm({
        title: "입력한 내용을 버리고 닫을까요?", message: "닫으면 이 창에 입력한 내용이 사라집니다.",
        confirmLabel: "버리고 닫기", cancelLabel: "계속 입력", danger: true,
      });
      asking.current = false;
      if (!ok) return;
    }
    onClose();
  };
  const ref = useDialogFocus<HTMLDivElement>(true, requestClose);
  return (
    // 바깥 누름은 mousedown 으로 본다 — 칸 안에서 끌다가 바깥에서 놓았을 때 닫히지 않게
    <div className="dialog-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) void requestClose(); }}>
      <div ref={ref} tabIndex={-1} className={`dialog form-dialog ${size}`} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <form className="stack gap-4" onSubmit={form.submit} noValidate>
          <div>
            <h2 id={titleId}>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <FormFields fields={fields} form={form} />
          <div className="actions">
            <Button variant="secondary" onClick={() => void requestClose()}>취소</Button>
            <Button type="submit" loading={form.running}>{submitLabel}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
