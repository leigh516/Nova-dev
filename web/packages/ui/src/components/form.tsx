"use client";
/**
 * 입력 칸 묶음 — FormPage(화면) · FormDialog(모달)가 **같은** 필드 렌더 · 칸 검사 · 서버 칸 오류 처리를 쓴다
 * (복제하면 한쪽만 고쳐져 두 입력 화면이 다르게 움직인다 — 계획 REQ_05 §8).
 *   const form = useFormModel({ fields, initial, onSubmit, success, then })
 *   <form onSubmit={form.submit}><FormFields fields={fields} form={form} />…</form>
 *
 * 입력 종류(type): text(기본) · textarea · email · number · select · date → 값은 문자열,
 *                  switch · checkbox → 값은 boolean (plan_REQ_07 T07-3.01).
 * select · date 는 고를 수 있는 값만 받는다(UX H5) — 목록 밖 값 · min/max 밖 날짜는 칸 오류.
 */
import React, { useState } from "react";
import { ApiError } from "@nova/sdk";
import { useAction } from "../hooks";
import { Field } from "./basic";

/** 칸 하나의 값 — 글 · 선택 · 날짜(YYYY-MM-DD)는 문자열, 스위치 · 체크박스는 boolean */
export type FormValue = string | boolean;
export type FormValues = Record<string, FormValue>;
export interface FormOption { value: string; label: string }

interface FormFieldBase {
  key: string;
  label: string;
  required?: boolean;
  help?: string;
}
/** 글 칸 — type 을 빼면 text(지금까지의 문자열 칸 그대로) */
export interface TextFormField extends FormFieldBase {
  type?: "text" | "textarea" | "email" | "number";
  maxLength?: number;
  placeholder?: string;
  validate?: (v: string) => string | null;
}
/** 목록에서 고르기 — 값은 options 의 value 중 하나(빈 문자열 = 고르지 않음) */
export interface SelectFormField extends FormFieldBase {
  type: "select";
  options: FormOption[];
  /** 고르지 않았을 때 보이는 첫 줄(기본 "선택하세요"). 필수 칸이면 다시 고를 수 없게 막는다 */
  placeholder?: string;
  validate?: (v: string) => string | null;
}
/** 날짜 — 값은 YYYY-MM-DD. min · max 도 같은 형식(그 날 포함) */
export interface DateFormField extends FormFieldBase {
  type: "date";
  min?: string;
  max?: string;
  validate?: (v: string) => string | null;
}
/** 켜고 끄기 — switch(설정 켜기) · checkbox(동의 · 확인). required 면 켜야 제출된다 */
export interface ToggleFormField extends FormFieldBase {
  type: "switch" | "checkbox";
  validate?: (v: boolean) => string | null;
}
export type FormField = TextFormField | SelectFormField | DateFormField | ToggleFormField;

const isToggle = (f: FormField): f is ToggleFormField => f.type === "switch" || f.type === "checkbox";

/** 처음 값 — 스위치 · 체크박스는 false, 나머지는 빈 문자열. 서버가 "true" 문자열로 준 값도 켜짐으로 읽는다 */
function normalize(f: FormField, v: FormValue | undefined): FormValue {
  if (isToggle(f)) return v === true || v === "true";
  return typeof v === "string" ? v : v === undefined ? "" : String(v);
}

/** 달력에 있는 날짜인가(2026-02-30 같은 값은 아니다) */
function isDate(s: string): boolean {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return false;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return d.getUTCFullYear() === +m[1] && d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[3];
}

/** 칸 검사 — 오류 문구 또는 null */
export function checkField(f: FormField, value: FormValue): string | null {
  if (isToggle(f)) {
    const on = value === true;
    // 라벨이 문장('…확인했습니다')인 경우가 많아 라벨을 문구에 넣지 않는다 — 오류는 바로 그 칸 밑에 붙는다
    if (f.required && !on) return "이 항목을 선택해야 진행할 수 있습니다";
    return f.validate?.(on) ?? null;
  }
  const v = typeof value === "string" ? value : "";
  if (f.type === "select") {
    if (!v) return f.required ? `${f.label}을(를) 고르세요` : f.validate?.(v) ?? null;
    if (!f.options.some((o) => o.value === v)) return "목록에 있는 값을 고르세요";
    return f.validate?.(v) ?? null;
  }
  if (f.type === "date") {
    if (!v) return f.required ? `${f.label}을(를) 고르세요` : f.validate?.(v) ?? null;
    if (!isDate(v)) return "날짜를 YYYY-MM-DD 형식으로 고르세요";
    // YYYY-MM-DD 는 글자 순서가 곧 날짜 순서다
    if ((f.min && v < f.min) || (f.max && v > f.max)) {
      return f.min && f.max ? `${f.min} ~ ${f.max} 사이 날짜를 고르세요`
        : f.min ? `${f.min} 또는 그 뒤 날짜를 고르세요` : `${f.max} 또는 그 앞 날짜를 고르세요`;
    }
    return f.validate?.(v) ?? null;
  }
  if (f.required && !v.trim()) return `${f.label}을(를) 입력하세요`;
  if (f.maxLength && v.length > f.maxLength) return `${f.maxLength}자 이하로 입력하세요 (지금 ${v.length}자)`;
  return f.validate?.(v) ?? null;
}

/**
 * V — onSubmit 이 받는 값의 모양. 주지 않으면 FormValues(칸마다 string | boolean).
 * 지금까지처럼 `(v: Record<string, string>) => …` 로 적은 화면도 그대로 컴파일된다(문자열 칸만 쓰는 화면).
 */
export function useFormModel<V extends FormValues = FormValues>({ fields, initial = {}, onSubmit, success, then, idPrefix = "f" }: {
  fields: FormField[];
  initial?: Partial<V>;
  onSubmit: (v: V) => Promise<unknown>;
  success?: string;
  then?: () => void | Promise<void>;
  /** 칸 id 접두어 — 같은 화면에 폼 화면과 폼 모달이 함께 있어도 id 가 겹치지 않게 */
  idPrefix?: string;
}) {
  const init = initial as Partial<FormValues>;
  const [values, setValues] = useState<FormValues>(() => Object.fromEntries(fields.map((f) => [f.key, normalize(f, init[f.key])])));
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [serverErr, setServerErr] = useState<Record<string, string>>({});
  const fieldId = (key: string) => `${idPrefix}-${key}`;
  const focusField = (key: string) => document.getElementById(fieldId(key))?.focus();
  // 고치기 시작하면 그 칸의 서버 오류는 지운다(다시 제출할 때 서버가 다시 판단)
  const change = (key: string, value: FormValue) => {
    setValues((v) => ({ ...v, [key]: value }));
    setServerErr((s) => { if (!(key in s)) return s; const n = { ...s }; delete n[key]; return n; });
  };
  const touch = (key: string) => setTouched((t) => ({ ...t, [key]: true }));
  const errors: Record<string, string | null> = Object.fromEntries(fields.map((f) => [f.key, serverErr[f.key] ?? checkField(f, values[f.key] ?? normalize(f, undefined))]));
  const action = useAction(async (v: FormValues) => {
    try {
      return await onSubmit(v as V);
    } catch (e) {
      // 서버 칸별 오류(422 invalid_input · fields[].loc 의 마지막 조각 = 칸 key)를 칸 옆에 보인다(UX H9).
      // 이 폼에 없는 칸의 오류는 버리고, 일반 문구는 useAction 이 오류 토스트로 띄운다
      if (e instanceof ApiError) {
        const fe = e.fieldErrors();
        const mine = Object.fromEntries(fields.filter((f) => f.key in fe).map((f) => [f.key, fe[f.key] || "입력값을 확인하세요"]));
        if (Object.keys(mine).length) {
          setServerErr(mine);
          const first = fields.find((f) => f.key in mine);
          if (first) focusField(first.key);
        }
      }
      throw e;
    }
  }, { success, then: then ? () => then() : undefined });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (action.running) return; // 진행 중 재제출 막기(useAction 도 막지만 검증 · 상태 갱신까지 건너뛴다)
    setTouched(Object.fromEntries(fields.map((f) => [f.key, true])));
    const first = fields.find((f) => errors[f.key]);
    if (first) { focusField(first.key); return; } // 첫 오류 칸으로(UX H5 · H9)
    setServerErr({});
    await action.run(values); // 실패하면 useAction 이 오류 토스트를 띄우고 입력은 그대로 남는다(UX H9)
  };
  /** 처음 값과 달라졌는가 — 모달을 닫을 때 확인을 물을지 정한다 */
  const dirty = fields.some((f) => (values[f.key] ?? normalize(f, undefined)) !== normalize(f, init[f.key]));
  return { values, errors, touched, change, touch, fieldId, submit, running: action.running, dirty };
}

export type FormModel = ReturnType<typeof useFormModel>;

/** 필드 렌더 — 라벨 · 필수 · 도움말 · 오류(만진 칸만)를 Field 로 잇는다 */
export function FormFields({ fields, form }: { fields: FormField[]; form: FormModel }) {
  return (
    <>
      {fields.map((f) => (
        <Field key={f.key} id={form.fieldId(f.key)} label={f.label} required={f.required} help={f.help}
          error={form.touched[f.key] ? form.errors[f.key] : null} inline={isToggle(f)}>
          {(p) => <Control f={f} form={form} p={p} />}
        </Field>
      ))}
    </>
  );
}

type ControlProps = Parameters<Parameters<typeof Field>[0]["children"]>[0];

function Control({ f, form, p }: { f: FormField; form: FormModel; p: ControlProps }) {
  const raw = form.values[f.key];
  const onBlur = () => form.touch(f.key);
  if (isToggle(f)) {
    const on = raw === true;
    // 스위치 · 체크박스는 바꾸는 순간이 곧 '만짐'이다 — 필수 체크를 풀면 바로 오류가 보인다
    const set = (v: boolean) => { form.change(f.key, v); form.touch(f.key); };
    return f.type === "switch"
      // 라벨(label for)이 버튼 이름 · 눌러 바꾸기를 함께 맡는다. Space · Enter 는 버튼 기본 동작
      ? <button type="button" role="switch" className="switch" {...p} aria-labelledby={`${p.id}-label`} aria-checked={on} onClick={() => set(!on)} onBlur={onBlur} />
      : <input type="checkbox" className="checkbox" {...p} checked={on} onChange={(e) => set(e.target.checked)} onBlur={onBlur} />;
  }
  const value = typeof raw === "string" ? raw : "";
  const onChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => form.change(f.key, e.target.value);
  if (f.type === "select") {
    return (
      <select className="select" {...p} value={value} onChange={onChange} onBlur={onBlur}>
        {/* 필수 칸은 고른 뒤 다시 '고르지 않음'으로 돌아갈 수 없다(UX H5) */}
        <option value="" disabled={f.required}>{f.placeholder ?? "선택하세요"}</option>
        {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    );
  }
  if (f.type === "date") {
    return <input className="input" type="date" {...p} value={value} min={f.min} max={f.max} onChange={onChange} onBlur={onBlur} />;
  }
  const common = { ...p, value, placeholder: f.placeholder, onBlur };
  return f.type === "textarea"
    ? <textarea className="textarea" {...common} onChange={onChange} />
    : <input className="input" type={f.type ?? "text"} {...common} onChange={onChange} />;
}
