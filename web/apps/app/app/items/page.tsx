"use client";
/** @screen 항목 목록 · @status 완료 */
/** 항목 목록 — ListPage 템플릿 + 이 화면만의 데이터 정의(컬럼 · 행 동작). 로딩 · 빈 · 오류 · 검색 · 정렬 · 페이지는 템플릿이 한다. */
import { useRouter } from "next/navigation";
import { api } from "@nova/sdk";
import { Button, ListPage, StatusBadge, fmtAgo, useAction, type Column } from "@nova/ui";
import { ITEM_STATUS, type Item } from "../../lib/app";

const columns: Column<Item>[] = [
  { key: "name", title: "이름", sortable: true },
  { key: "status", title: "상태", render: (r) => <StatusBadge code={r.status} map={ITEM_STATUS} /> },
  { key: "created_at", title: "만든 때", sortable: true, render: (r) => <span title={r.created_at}>{fmtAgo(r.created_at)}</span> },
  // 메모는 개인정보가 들어갈 수 있는 자유 입력 — 화면에는 보이되 내보내기 파일에서는 가린다(pii)
  { key: "memo", title: "메모", pii: true, render: (r) => r.memo || "—" },
];

function RowActions({ row, reload }: { row: Item; reload: () => void }) {
  // 보관 = 되돌릴 수 있음 → 실행 취소 토스트(UX H3) · 삭제 = 되돌릴 수 없음 → 확인 대화상자(UX H5)
  const archive = useAction(() => api(`/sample/items/${row.id}/archive`, { method: "POST" }), {
    success: `'${row.name}' 을(를) 보관했습니다`,
    undo: () => api(`/sample/items/${row.id}/restore`, { method: "POST" }),
    then: reload,
  });
  const remove = useAction(() => api(`/sample/items/${row.id}`, { method: "DELETE" }), {
    confirm: { title: `'${row.name}' 을(를) 삭제할까요?`, message: "삭제하면 되돌릴 수 없습니다. 잠시 숨기려면 '보관'을 쓰세요.", confirmLabel: "삭제", danger: true },
    success: "삭제했습니다",
    then: reload,
  });
  return (
    <>
      {row.status === "active" && <Button size="sm" variant="secondary" loading={archive.running} onClick={() => archive.run()}>보관</Button>}
      <Button size="sm" variant="ghost" loading={remove.running} onClick={() => remove.run()} aria-label={`${row.name} 삭제`}>삭제</Button>
    </>
  );
}

export default function Items() {
  const router = useRouter();
  return (
    <ListPage<Item>
      title="항목"
      description="sample 서비스의 항목입니다. 보관하면 목록에 남고, 삭제하면 사라집니다."
      source="/sample/items"
      columns={columns}
      onRowClick={(r) => router.push(`/items/${r.id}`)}
      rowActions={(r, reload) => <RowActions row={r} reload={reload} />}
      primary={{ label: "새 항목", href: "/items/new" }}
      searchPlaceholder="이름으로 검색 ( / )"
      export={{ filename: "항목" }}
      empty={{ title: "아직 항목이 없습니다", description: "첫 항목을 만들어 보세요. 단축키 n 으로도 만들 수 있습니다." }}
    />
  );
}
