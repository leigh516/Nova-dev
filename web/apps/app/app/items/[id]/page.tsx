"use client";
/** @screen 항목 상세 · @status 완료 */
import { useParams } from "next/navigation";
import { api } from "@nova/sdk";
import { Button, Card, DetailPage, KeyValue, Section, StatusBadge, fmtAt, useAction } from "@nova/ui";
import { ACTIVITY_LABEL, ITEM_STATUS, type Item } from "../../../lib/app";

function Actions({ item, reload }: { item: Item; reload: () => void }) {
  const archive = useAction(() => api(`/sample/items/${item.id}/archive`, { method: "POST" }), {
    success: "보관했습니다",
    undo: () => api(`/sample/items/${item.id}/restore`, { method: "POST" }),
    then: reload,
  });
  const restore = useAction(() => api(`/sample/items/${item.id}/restore`, { method: "POST" }), { success: "보관을 풀었습니다", then: reload });
  return item.status === "active"
    ? <Button variant="secondary" loading={archive.running} onClick={() => archive.run()}>보관</Button>
    : <Button variant="secondary" loading={restore.running} onClick={() => restore.run()}>보관 풀기</Button>;
}

export default function ItemDetail() {
  const { id } = useParams<{ id: string }>();
  return (
    <DetailPage<Item>
      source={`/sample/items/${id}`}
      title={(d) => d.name}
      crumbs={[{ href: "/items", label: "항목" }]}
      actions={(d, reload) => <Actions item={d} reload={reload} />}
    >
      {(d) => (
        <>
          <Card>
            <KeyValue items={[
              { label: "상태", value: <StatusBadge code={d.status} map={ITEM_STATUS} /> },
              { label: "메모", value: d.memo },
              { label: "만든 때", value: fmtAt(d.created_at) },
              { label: "고친 때", value: fmtAt(d.updated_at) },
              { label: "ID", value: <code>{d.id}</code> },
            ]} />
          </Card>
          <Section title="활동 기록">
            <Card>
              {/* 서버가 최신 50건만 준다(ACTIVITY_LIMIT) — 잘렸으면 알린다(UX H1 · plan_REQ_04 T04-6.04). 전체 보기 화면은 만들지 않는다(비목표) */}
              {d.activity_truncated && <p className="muted small list-note" role="status">최근 50건만 보입니다. 그 전 기록은 서버에 남아 있습니다.</p>}
              {d.activity && d.activity.length > 0 ? (
                <ul className="stack list">
                  {d.activity.map((a, i) => <li key={i}>{ACTIVITY_LABEL[a.kind] ?? a.kind} <span className="muted small">· {fmtAt(a.recorded_at)}</span></li>)}
                </ul>
              ) : <p className="muted small">아직 기록이 없습니다. 이벤트가 처리되면 여기에 나타납니다.</p>}
            </Card>
          </Section>
        </>
      )}
    </DetailPage>
  );
}
