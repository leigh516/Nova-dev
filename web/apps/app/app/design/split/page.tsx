"use client";
/** @screen 디자인 갤러리 — 스플릿 · @status 완료 */
/**
 * SplitPage 시연 — 왼쪽 장비 목록 · 오른쪽 상세, 가짜 데이터(rows 주입 · 서버 호출 없음).
 * 고른 장비는 주소 ?sel= 에 남고(새로고침 · 공유), 목록 행에서 ↑ ↓ 로 옮긴다. 900px 아래에서는 위아래로 쌓인다.
 */
import { Badge, KeyValue, SplitPage, StatusBadge, type Column, type Tone } from "@nova/ui";

interface Device { id: string; name: string; kind: string; site: string; state: string; ip: string; firmware: string; owner: string }

/** 상태 표시 매핑 — 실제 프로젝트는 서버 설정에서 읽는다(enum 하드코딩 금지, ui.md 규칙 6) */
const STATE: Record<string, { label: string; tone: Tone }> = {
  up: { label: "정상", tone: "success" }, warn: { label: "경고", tone: "warning" }, down: { label: "중지", tone: "danger" }, maint: { label: "점검", tone: "neutral" },
};

const ROWS: Device[] = [
  { id: "fw-01", name: "FW-SEOUL-01", kind: "방화벽", site: "서울 관제센터", state: "up", ip: "10.0.1.1", firmware: "7.2.4", owner: "보안운영팀" },
  { id: "fw-02", name: "FW-SEOUL-02", kind: "방화벽", site: "서울 관제센터", state: "warn", ip: "10.0.1.2", firmware: "7.2.4", owner: "보안운영팀" },
  { id: "ips-01", name: "IPS-CORE-01", kind: "침입방지", site: "서울 관제센터", state: "up", ip: "10.0.2.1", firmware: "5.1.0", owner: "보안운영팀" },
  { id: "waf-01", name: "WAF-WEB-01", kind: "웹 방화벽", site: "부산 관제센터", state: "maint", ip: "10.1.3.1", firmware: "3.8.2", owner: "웹서비스팀" },
  { id: "gpu-17", name: "GPU-17", kind: "AI 서버", site: "판교 IDC", state: "down", ip: "10.2.0.17", firmware: "550.54", owner: "AI 인프라팀" },
  { id: "edr-01", name: "EDR-MGR-01", kind: "EDR 관리", site: "판교 IDC", state: "up", ip: "10.2.1.1", firmware: "2.4.1", owner: "보안운영팀" },
];

const columns: Column<Device>[] = [
  { key: "name", title: "이름" },
  { key: "kind", title: "종류" },
  { key: "state", title: "상태", align: "right", render: (r) => <StatusBadge code={r.state} map={STATE} /> },
];

export default function DesignSplit() {
  return (
    <SplitPage<Device>
      title="장비 — 스플릿 시연"
      description="SplitPage — 목록에서 고르면 오른쪽에 상세. 고른 장비는 주소(?sel)에 남고 ↑ ↓ 로 옮깁니다. 가짜 데이터."
      rows={ROWS}
      columns={columns}
      empty={{ title: "등록된 장비가 없습니다" }}
      detail={(d) => (
        <div className="stack">
          <div className="row between">
            <h2>{d.name}</h2>
            <Badge tone={STATE[d.state]?.tone}>{STATE[d.state]?.label ?? d.state}</Badge>
          </div>
          <KeyValue items={[
            { label: "종류", value: d.kind }, { label: "위치", value: d.site }, { label: "관리 주소", value: <span className="num">{d.ip}</span> },
            { label: "펌웨어", value: d.firmware }, { label: "담당", value: d.owner },
          ]} />
        </div>
      )}
    />
  );
}
