"use client";
/** @screen 도움말 · @status 완료 */
/** 도움말(UX H10) — 작업 중심("~하려면"), 짧게. 화면이 바뀌면 같은 계획의 task 로 함께 고친다. */
import { Fragment } from "react";
import { Card, Content, DEFAULT_SHORTCUTS, PageHeader, Section } from "@nova/ui";

const HOWTO = [
  { q: "항목을 만들려면", a: "항목 화면에서 '새 항목'을 누르거나 키보드 n 을 누릅니다. 이름만 쓰면 됩니다." },
  { q: "잠시 숨기려면", a: "'보관'을 누릅니다. 실수했다면 바로 뜨는 알림의 '실행 취소'를 누르세요." },
  { q: "완전히 지우려면", a: "'삭제'를 누르고 확인합니다. 삭제는 되돌릴 수 없으니 확실하지 않으면 보관을 쓰세요." },
  { q: "찾으려면", a: "목록 위 검색 칸(키보드 /)에 이름 일부를 쓰고 Enter. 조건은 주소에 남아 다시 와도 그대로입니다." },
  { q: "권한이 없다고 나오면", a: "화면에 나온 '필요한 권한'을 관리자에게 알려 주세요." },
];

export default function Help() {
  return (
    <Content width="narrow">
      <PageHeader title="도움말" description="자주 하는 일과 단축키입니다. 어느 화면에서나 ? 키로 단축키를 볼 수 있습니다." />
      <Section title="이럴 때는">
        <div className="stack">{HOWTO.map((h) => <Card key={h.q}><h3>{h.q}</h3><p className="secondary small mt-2">{h.a}</p></Card>)}</div>
      </Section>
      <Section title="단축키">
        <Card><dl className="kv">{DEFAULT_SHORTCUTS.map((s) => <Fragment key={s.keys}><dt><kbd>{s.keys}</kbd></dt><dd>{s.label}</dd></Fragment>)}</dl></Card>
      </Section>
      <Section title="더 도움이 필요하면">
        <p className="secondary small">관리자에게 문의하거나, 화면 아래 오류 코드와 함께 알려 주세요.</p>
      </Section>
    </Content>
  );
}
