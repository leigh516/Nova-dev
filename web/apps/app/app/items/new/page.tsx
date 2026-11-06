"use client";
/** @screen 항목 만들기 · @status 완료 */
import { api } from "@nova/sdk";
import { FormPage, RequireAuth } from "@nova/ui";
import { LIMITS } from "../../../lib/contract.gen";

// 상한은 서버 요청 스키마(sample ItemIn)에서 생성 — 화면에 숫자를 쓰지 않는다(plan_REQ_04 P9)
const LIM = LIMITS.ItemIn;

export default function NewItem() {
  return (
    <RequireAuth>
      <FormPage
        title="새 항목"
        description="이름은 목록에 보이는 이름입니다. 메모는 나만 참고하는 내용입니다."
        crumbs={[{ href: "/items", label: "항목" }]}
        fields={[
          { key: "name", label: "이름", required: true, maxLength: LIM.name.maxLength, placeholder: "예: 회의실 예약 규칙" },
          { key: "memo", label: "메모", type: "textarea", maxLength: LIM.memo.maxLength, help: `선택 — ${LIM.memo.maxLength}자까지` },
        ]}
        submitLabel="만들기"
        success="항목을 만들었습니다"
        cancelHref="/items"
        onSubmit={(v) => api("/sample/items", { method: "POST", body: { name: v.name, memo: v.memo || null } })}
      />
    </RequireAuth>
  );
}
