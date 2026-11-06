"use client";
/** @screen 디자인 갤러리 · @status 완료 */
/** 디자인 갤러리 — 공통 컴포넌트를 한 화면에서 보고 비교한다(디자인 시스템 모범 사례 9). 새 컴포넌트를 만들면 여기에 추가한다. */
import { useState } from "react";
import {
  AiConfirmCard, AiMark, Badge, Bars, Button, Card, ChartLegend, Content, DataTable, DomainTag, EmptyState, ErrorState, Field, FormDialog,
  HeaderUtils, PageHeader, Section, Segmented, Select, Sidebar, Skeleton, Sparkline, Stat, Switch, TextInput, toCsv, useConfirm, useToast,
  type Column, type DomainSlot, type FormField,
} from "@nova/ui";
import { ApiError } from "@nova/sdk";

const SWATCHES = ["bg-canvas", "bg-surface", "bg-subtle", "bg-inverse", "text-primary", "text-secondary", "text-muted", "text-brand",
  "action-primary", "action-accent", "action-danger", "status-success-fg", "status-warning-fg", "status-danger-fg", "status-info-fg", "border-control"];

/** 도메인 → 번호 슬롯 매핑 예시 — 실제 프로젝트는 팩 · 서버 설정 데이터에서 읽는다(코어는 업종 이름을 모른다) */
const DOMAINS: Record<string, { label: string; slot: DomainSlot }> = {
  monitor: { label: "관제", slot: 1 }, asset: { label: "자산", slot: 2 }, contract: { label: "계약", slot: 3 },
  incident: { label: "장애", slot: 4 }, aiserver: { label: "AI 서버", slot: 5 }, report: { label: "보고", slot: 6 },
};
const NAV_PREVIEW = [
  { href: "#nav-dashboard", label: "대시보드" }, { href: "#nav-alerts", label: "경보" },
  { href: "#nav-devices", label: "장비" }, { href: "#nav-reports", label: "보고서" },
];
const TENANTS = [{ id: "seoul", label: "누리 관제센터" }, { id: "busan", label: "부산 관제센터" }, { id: "fail", label: "전환 실패 예시" }];
const SERIES = ["계열 1", "계열 2", "계열 3", "계열 4", "계열 5", "계열 6"];
const CONTACT_FIELDS: FormField[] = [
  { key: "name", label: "이름", required: true, maxLength: 40 },
  { key: "email", label: "이메일", type: "email", help: "알림을 받을 주소", validate: (v) => (v && !/^[^@\s]+@[^@\s]+$/.test(v) ? "이메일 형식이 아닙니다" : null) },
  { key: "memo", label: "메모", type: "textarea", maxLength: 200 },
];
/** 입력 종류 시연 — 선택 · 날짜 · 스위치 · 체크박스(T07-3.01). 날짜는 고를 수 있는 범위만(UX H5) */
const CHECK_FIELDS: FormField[] = [
  { key: "kind", label: "점검 종류", type: "select", required: true,
    options: [{ value: "regular", label: "정기 점검" }, { value: "urgent", label: "긴급 점검" }, { value: "patch", label: "보안 패치" }] },
  { key: "date", label: "점검일", type: "date", required: true, min: "2026-01-01", max: "2026-12-31", help: "2026년 안에서 고르세요" },
  { key: "notify", label: "끝나면 알림 받기", type: "switch" },
  { key: "agree", label: "점검 중 서비스가 멈출 수 있음을 확인했습니다", type: "checkbox", required: true },
];
const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
/** 내보내기 시연 — 엑셀에서 깨지기 쉬운 값(수식 첫 글자 · 쉼표 · 줄바꿈 · 따옴표)과 개인정보 열을 일부러 담았다 */
type ExportRow = { id: string; name: string; memo: string | null };
const EXPORT_ROWS: ExportRow[] = [
  { id: "e1", name: "=SUM(A1:A3)", memo: "010-1234-5678 홍길동" },
  { id: "e2", name: "쉼표, 포함", memo: null },
  { id: "e3", name: "줄\n바꿈 \"따옴표\"", memo: "hong@example.com" },
  { id: "e4", name: "-2 빼기", memo: null },
];
const EXPORT_COLUMNS: Column<ExportRow>[] = [
  { key: "name", title: "이름" },
  { key: "memo", title: "메모", pii: true },
  { key: "act", title: "동작", exportable: false, render: () => <Button variant="ghost" size="sm">보관</Button> },
];

export default function Design() {
  const toast = useToast();
  const confirm = useConfirm();
  const [seg, setSeg] = useState<"a" | "b" | "c">("a");
  const [on, setOn] = useState(true);
  const [tenant, setTenant] = useState("seoul");
  const [contactOpen, setContactOpen] = useState(false);
  const [checkOpen, setCheckOpen] = useState(false);
  const [checkSaved, setCheckSaved] = useState<string | null>(null);
  // AI 확인 카드 시연 — 승인 횟수를 화면에 보여 '렌더 · Enter · 새로고침만으로는 실행되지 않음'을 확인할 수 있게 한다
  const [aiUndo, setAiUndo] = useState<"yes" | "no">("yes");
  const [aiOpen, setAiOpen] = useState(true);
  const [approved, setApproved] = useState(0);
  // 조직 전환 시연 — 실제 앱은 서버가 토큰을 다시 내준 뒤 current 를 바꾼다. 부품은 저장소 · x-tenant 를 건드리지 않는다
  const switchTenant = async (id: string) => {
    await new Promise((r) => setTimeout(r, 300));
    if (id === "fail") throw new ApiError(503, "tenant_switch_failed", "조직을 바꾸지 못했습니다. 지금 조직 그대로입니다. 잠시 후 다시 시도하세요");
    setTenant(id);
  };
  return (
    <Content width="wide">
      <PageHeader title="디자인 갤러리" description="토큰 → 컴포넌트 → 템플릿. 색 · 간격은 design/tokens/brand.tokens.json 에서만 바꾼다."
        actions={<>
          <a className="btn secondary sm" href="/design/dashboard">대시보드 시연</a>
          <a className="btn secondary sm" href="/design/split">스플릿 시연</a>
          <a className="btn secondary sm" href="/design/settings">설정 시연</a>
        </>} />
      <Section title="색 토큰 (의미)">
        <div className="grid cols-xs">
          {SWATCHES.map((s) => (
            <div key={s} className="card p-3">
              <div className="swatch" style={{ background: `var(--color-${s})` }} />
              <code className="xs">--color-{s}</code>
            </div>
          ))}
        </div>
      </Section>
      <Section title="버튼 (variant · size · loading)">
        <Card><div className="row">
          <Button>주 행동</Button><Button variant="secondary">보조</Button><Button variant="ghost">고스트</Button><Button variant="danger">위험</Button>
          <Button size="sm">작게</Button><Button size="lg">크게</Button><Button loading>저장 중</Button><Button disabled>비활성</Button>
        </div></Card>
      </Section>
      <Section title="배지 · 지표 · 입력">
        <div className="grid">
          <Card><div className="row"><Badge>중립</Badge><Badge tone="info">정보</Badge><Badge tone="success">성공</Badge><Badge tone="warning">주의</Badge><Badge tone="danger">위험</Badge><Badge tone="link">링크</Badge></div></Card>
          <Card><div className="row gap-6"><Stat label="오늘 요청" value="12,480" delta="어제보다 +8%" /><Sparkline values={[3, 5, 4, 8, 6, 9, 12]} label="최근 7일 추이" /></div></Card>
          <Card><div className="stack">
            <Field label="이름" required help="목록에 보이는 이름">{(p) => <TextInput {...p} placeholder="예: 회의실" />}</Field>
            <Field label="분류" error="분류를 고르세요">{(p) => <Select {...p} placeholder="고르세요" options={[{ value: "a", label: "가" }, { value: "b", label: "나" }]} />}</Field>
            <div className="row"><Segmented label="보기" value={seg} onChange={setSeg} options={[{ value: "a", label: "전체" }, { value: "b", label: "사용 중" }, { value: "c", label: "보관" }]} /><Switch label="알림 받기" checked={on} onChange={setOn} /></div>
          </div></Card>
        </div>
      </Section>
      <Section title="피드백 — 토스트 · 실행 취소 · 확인 대화상자">
        <Card><div className="row">
          <Button variant="secondary" onClick={() => toast("저장했습니다")}>성공 토스트</Button>
          <Button variant="secondary" onClick={() => toast("보관했습니다", { undo: () => toast("되돌렸습니다") })}>실행 취소 토스트</Button>
          <Button variant="secondary" onClick={() => toast("서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요", { error: true })}>오류 토스트</Button>
          <Button variant="danger" onClick={async () => { if (await confirm({ title: "삭제할까요?", message: "되돌릴 수 없습니다.", confirmLabel: "삭제", danger: true })) toast("삭제했습니다"); }}>확인 대화상자</Button>
        </div></Card>
      </Section>
      <Section title="상태 — 로딩 · 빈 · 오류">
        <div className="grid">
          <Card><div className="stack"><Skeleton height={20} /><Skeleton height={20} width="70%" /><Skeleton height={20} width="40%" /></div></Card>
          <Card><EmptyState title="아직 항목이 없습니다" description="첫 항목을 만들어 보세요." action={<Button>새 항목</Button>} /></Card>
          <Card><ErrorState error={new ApiError(0, "network", "서버에 연결할 수 없습니다. 인터넷 연결을 확인하세요")} onRetry={() => toast("다시 시도")} /></Card>
        </div>
      </Section>
      <Section title="표 · 막대">
        <div className="grid">
          <Card flush><DataTable rows={[{ id: 1, name: "가", n: 3 }, { id: 2, name: "나", n: 12 }]} columns={[{ key: "name", title: "이름", sortable: true }, { key: "n", title: "수", align: "right" }]} sort="name" onSort={() => undefined} /></Card>
          <Card><Bars data={[{ label: "월", value: 4 }, { label: "화", value: 7 }, { label: "수", value: 2 }, { label: "목", value: 9 }]} /></Card>
        </div>
      </Section>
      <Section title="솔리드 상태 배지" actions={<span className="xs muted">Badge · StatusBadge 의 solid — 경보 강조에만, 화면당 한 곳 권장</span>}>
        <Card><div className="row">
          <Badge tone="danger" solid>위험</Badge><Badge tone="warning" solid>경고</Badge><Badge tone="success" solid>정상</Badge>
          <Badge tone="info" solid>정보</Badge><Badge tone="neutral" solid>중지</Badge>
          <span className="small muted">기본(옅은) 배지와 비교 →</span>
          <Badge tone="danger">위험</Badge><Badge tone="warning">경고</Badge><Badge tone="success">정상</Badge>
        </div></Card>
      </Section>
      <Section title="AI 표식" actions={<span className="xs muted">AI 가 만든 초안 · 요약에 AiMark — 실행 제안(L2)은 AI 확인 카드로</span>}>
        <Card><div className="stack">
          <div className="row"><AiMark /><span className="small">경보 요약 초안 — 사람이 확인 전</span></div>
          <p className="small secondary">지난 1시간 동안 방화벽 3대에서 같은 출발지의 접속 시도가 몰렸습니다.</p>
          <div className="row"><Badge>초안</Badge><span className="xs muted">L1 — 표식만, 실행 없음</span></div>
        </div></Card>
      </Section>
      <Section title="도메인 식별 태그" actions={<span className="xs muted">DomainTag — 모듈 → 슬롯 1~6 매핑은 데이터(map), 상태색과 섞지 않는다</span>}>
        <Card><div className="stack">
          <div className="row">{Object.keys(DOMAINS).map((c) => <DomainTag key={c} code={c} map={DOMAINS} />)}</div>
          <div className="row"><span className="xs muted">상태는 옆에 배지로 따로:</span><DomainTag code="monitor" map={DOMAINS} /><Badge tone="danger">위험</Badge></div>
        </div></Card>
      </Section>
      <Section title="차트 색" actions={<span className="xs muted">chartColor(i) — 계열 순서대로 chart.1~6, 다크는 밝은 단계</span>}>
        <div className="grid cols-lg">
          <Card><div className="stack">
            <ChartLegend items={SERIES.map((label) => ({ label }))} />
            <Bars height={150} data={[7, 4.5, 9, 3, 6, 5].map((value, i) => ({ label: String(i + 1), value, series: i }))} />
          </div></Card>
          <Card><div className="stack">
            <span className="small secondary">Sparkline 계열 색</span>
            <div className="row"><Sparkline series={0} width={220} height={48} values={[3, 4, 3.5, 6, 5.5, 7, 6.5]} label="계열 1 추이" /><Sparkline series={1} width={220} height={48} values={[1.5, 2, 2.8, 2.5, 4, 3.8, 4.5]} label="계열 2 추이" /><Sparkline series={2} width={220} height={48} values={[6, 5, 6.5, 4.5, 5, 3, 3.5]} label="계열 3 추이" /></div>
          </div></Card>
        </div>
      </Section>
      <Section title="딥 사이드바 미리보기" actions={<span className="xs muted">AppShell navTone: "deep" — 같은 Sidebar 부품에 tone 만, 활성 · 포커스는 nav 전용 토큰</span>}>
        <div className="grid">
          <Card flush><Sidebar tone="deep" links={NAV_PREVIEW} current="#nav-dashboard" /></Card>
          <Card flush><Sidebar links={NAV_PREVIEW} current="#nav-dashboard" /></Card>
        </div>
      </Section>
      <Section title="헤더 유틸" actions={<span className="xs muted">AppShell header — 알림 개수 · 조직 전환(앱이 준 onSwitch 로만, 실패하면 지금 조직 그대로). 전체 검색은 위 머리띠의 Ctrl+K</span>}>
        <div className="topbar preview"><div className="topbar-in full">
          <span className="brand"><span className="mark" aria-hidden="true">N</span>Nova</span><div className="grow" />
          <HeaderUtils header={{ notifications: { count: 5, href: "/design#notifications" }, tenants: { current: tenant, items: TENANTS, onSwitch: switchTenant } }} />
        </div></div>
      </Section>
      <Section title="폼 모달" actions={<span className="xs muted">FormDialog — FormPage 와 같은 칸 · 검사. Esc · 바깥 · 취소로 닫고, 입력 중이면 버릴지 묻는다</span>}>
        <Card><div className="row">
          <Button variant="secondary" onClick={() => setContactOpen(true)}>연락처 추가</Button>
          <span className="small muted">닫히면 이 버튼으로 포커스가 돌아옵니다</span>
        </div></Card>
        <FormDialog open={contactOpen} title="연락처 추가" size="md" fields={CONTACT_FIELDS} submitLabel="저장" success="연락처를 추가했습니다"
          onSubmit={() => wait(300)} onClose={() => setContactOpen(false)} />
      </Section>
      <Section title="폼 입력 종류" actions={<span className="xs muted">FormField type — select · date(min · max) · switch · checkbox. 값은 글 · 선택 · 날짜는 문자열, 스위치 · 체크박스는 참 · 거짓</span>}>
        <Card><div className="stack">
          <div className="row">
            <Button variant="secondary" onClick={() => setCheckOpen(true)}>점검 일정 추가</Button>
            <span className="small muted">빈 채로 저장하면 칸마다 오류가 붙고 첫 오류 칸으로 갑니다</span>
          </div>
          {/* 서버로 갈 값 그대로 — 스위치 · 체크박스가 참 · 거짓으로 가는지 눈으로 확인 */}
          <pre aria-label="저장한 값" className="xs code-preview">{checkSaved ?? "아직 저장하지 않았습니다"}</pre>
        </div></Card>
        <FormDialog open={checkOpen} title="점검 일정 추가" size="md" fields={CHECK_FIELDS} submitLabel="저장" success="점검 일정을 추가했습니다"
          onSubmit={async (v) => { await wait(300); setCheckSaved(JSON.stringify(v)); }} onClose={() => setCheckOpen(false)} />
      </Section>
      <Section title="목록 내보내기" actions={<span className="xs muted">ListPage export: {"{ filename }"} — 열의 pii 는 파일에서 ****, exportable: false 는 뺀다. 같은 검색 · 정렬로 전부 읽은 뒤에만 파일</span>}>
        <div className="grid cols-lg">
          <Card flush><DataTable rows={EXPORT_ROWS} columns={EXPORT_COLUMNS} caption="화면에 보이는 값" /></Card>
          <Card><div className="stack">
            <div className="row"><span className="small secondary">파일에 담기는 값(toCsv)</span><div className="grow" />
              <a className="btn secondary sm" href="/items">목록에서 내려받아 보기</a></div>
            <pre aria-label="내보낼 CSV 미리보기" className="xs code-preview">{toCsv(EXPORT_ROWS, EXPORT_COLUMNS)}</pre>
            <span className="xs muted">수식으로 시작하는 값은 앞에 ' · 개인정보는 **** · 빈 값은 빈 채로 · 내려받을 때 엑셀용 BOM</span>
          </div></Card>
        </div>
      </Section>
      <Section title="AI 확인 카드" actions={<span className="xs muted">AiConfirmCard(L2) — 승인 API 는 서버에서 require_human. 기본 포커스는 취소</span>}>
        <div className="stack">
          <div className="row">
            <Segmented label="되돌림" value={aiUndo} onChange={(v) => { setAiUndo(v); setAiOpen(true); }}
              options={[{ value: "yes", label: "되돌림 있음" }, { value: "no", label: "되돌림 없음" }]} />
            <span className="small muted num">승인 실행 {approved}회</span>
          </div>
          {aiOpen ? (
            <AiConfirmCard key={aiUndo} level="L2" title="방화벽 3대 외부 접속 차단"
              target="FW-SEOUL-01 · FW-SEOUL-02 · FW-BUSAN-01" scope="외부 → 내부 새 접속 · 30분"
              params={[{ label: "출발지", value: "203.0.113.0/24" }, { label: "동작", value: "차단(drop)" }, { label: "만료", value: "30분 뒤 자동 해제" }]}
              undo={aiUndo === "yes" ? "차단 규칙을 지우면 바로 풀립니다(30분 뒤 자동 해제)" : null}
              onApprove={async () => { await wait(400); setApproved((n) => n + 1); }}
              onCancel={() => setAiOpen(false)} />
          ) : (
            <Card><div className="row"><span className="small secondary">제안을 닫았습니다 — 실행하지 않았습니다.</span>
              <Button variant="ghost" size="sm" onClick={() => setAiOpen(true)}>다시 보기</Button></div></Card>
          )}
        </div>
      </Section>
    </Content>
  );
}
