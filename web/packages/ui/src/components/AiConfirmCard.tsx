"use client";
/**
 * AI 확인 카드(STD-AX L2) — AI 가 제안한 **실행**을 사람이 읽고 승인한다. 표식(AiMark)만 붙이는 L1 과 다르다.
 * 🔴 승인 API 는 require_human — 카드는 사람이 누르게 할 뿐 서버를 지키지 못한다. onApprove 가 부르는 서버 핸들러는
 *    `Principal.require_human()`(nova_common service.py)으로 AI 주체를 403 으로 막아야 한다(계획 REQ_05 §11 판단 D).
 * 실수 막기(UX H5 · 검토 초점 3):
 * - 렌더만으로 onApprove 를 부르지 않는다 — 효과(useEffect) · 자동 제출 없음, 승인 버튼을 눌렀을 때만
 * - 기본 포커스는 **취소** — Enter 를 그냥 쳐도 실행되지 않는다. 새로고침해도 다시 제안 상태로 그려질 뿐 실행 없음
 * - 대상 · 범위 · 파라미터 · 되돌림을 누르기 전에 모두 보인다(모두 필수 props). 되돌릴 수 없으면 "되돌릴 수 없습니다" + 위험 버튼
 * 상태(계획 §5): 제안 → 승인중(둘 다 잠김) → 완료(성공 토스트 · 버튼 없음) / 실패(서버 문구 · 다시 시도 · 취소). 취소는 onCancel(카드를 닫는 것은 부모)
 */
import React, { useEffect, useId, useRef, useState } from "react";
import { useAction } from "../hooks";
import { AiMark, Badge, Button, KeyValue } from "./basic";

export interface AiConfirmCardProps {
  /** 자동화 등급 — 사람 승인이 필요한 실행은 L2 만 이 카드로 */
  level: "L2";
  title: string;
  /** 무엇에(예: "방화벽 FW-SEOUL-02 외 2대") */
  target: string;
  /** 얼마나 · 어디까지(예: "서울 관제센터 · 외부 접속 차단 30분") */
  scope: string;
  /** 실행 파라미터 — 빠짐없이 보인다 */
  params: { label: string; value: React.ReactNode }[];
  /** 되돌리는 방법 — 없으면 null("되돌릴 수 없습니다" · 위험 버튼) */
  undo: string | null;
  onApprove: () => Promise<unknown>;
  onCancel: () => void;
  /** 승인 버튼 글자(기본 "승인하고 실행") · 성공 토스트(기본 "승인했습니다 — 실행을 요청했습니다") */
  approveLabel?: string;
  success?: string;
}

export function AiConfirmCard({ level, title, target, scope, params, undo, onApprove, onCancel, approveLabel = "승인하고 실행", success = "승인했습니다 — 실행을 요청했습니다" }: AiConfirmCardProps) {
  const id = useId();
  const cancel = useRef<HTMLButtonElement>(null);
  const [done, setDone] = useState(false);
  const approve = useAction(() => onApprove(), { success, then: () => setDone(true) });
  // 처음 그릴 때 취소에 포커스 — 화면은 움직이지 않게(preventScroll). 실행은 여기서 하지 않는다
  useEffect(() => { cancel.current?.focus({ preventScroll: true }); }, []);
  const irreversible = undo === null;
  return (
    <section className={`card ai-confirm${irreversible ? " irreversible" : ""}`} role="region" aria-labelledby={`${id}-t`} aria-describedby={`${id}-why`} data-level={level}>
      <div className="ai-confirm-head">
        <AiMark text="AI 제안" label="AI 제안" />
        <h3 id={`${id}-t`}>{title}</h3>
        <Badge tone="info">{level} · 사람 승인 필요</Badge>
      </div>
      <p id={`${id}-why`} className="small secondary">
        AI 가 만든 실행안입니다. 사람이 읽고 승인해야 실행되며, 서버도 사람의 승인만 받습니다.
      </p>
      <KeyValue items={[
        { label: "대상", value: target },
        { label: "범위", value: scope },
        ...params.map((x) => ({ label: x.label, value: x.value })),
        { label: "되돌림", value: irreversible ? <strong className="ai-confirm-noundo">되돌릴 수 없습니다</strong> : undo },
      ]} />
      {approve.error && !approve.running && (
        <p className="ai-confirm-err small" role="alert">실행하지 못했습니다 — {approve.error.message}</p>
      )}
      {done ? (
        <p className="small secondary" role="status">승인했습니다. 실행 결과는 작업 기록에서 확인하세요.</p>
      ) : (
        <div className="actions">
          {/* 포커스를 잡아야 해서 원시 버튼(Button 은 ref 를 넘기지 않는다) — ConfirmDialog 와 같은 방식 */}
          <button ref={cancel} type="button" className="btn secondary" disabled={approve.running} onClick={onCancel}>취소</button>
          <Button variant={irreversible ? "danger" : "primary"} loading={approve.running} onClick={() => void approve.run()}>
            {approve.error ? "다시 시도" : approveLabel}
          </Button>
        </div>
      )}
    </section>
  );
}
