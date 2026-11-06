/** 이 앱만의 정의 — 앱 설정(AppShell) · 업무 타입 · 상태 매핑. 화면은 이것과 @nova/ui 템플릿만 쓴다. */
import type { AppConfig, Tone } from "@nova/ui";

export const APP: AppConfig = {
  id: "app",
  brand: "Nova",
  product: "샘플 앱",
  menuChannel: "web",
  layout: "top",
  helpHref: "/help",
  fallbackLinks: [{ href: "/items", label: "항목" }, { href: "/design", label: "디자인" }],
  footer: "Nova 공통개발플랫폼 샘플 — 이 앱을 복사해 새 화면을 만든다",
  // 헤더 전체 검색(Ctrl+K) — 샘플은 항목 목록 검색으로 보낸다. 알림 · 조직 전환은 서버 API 가 생기면 여기에 잇는다
  header: { search: { placeholder: "항목 이름으로 찾기", onSearch: (q) => window.location.assign(`/items?q=${encodeURIComponent(q)}`) } },
};

/** sample 서비스 항목 */
export interface Item {
  id: string;
  name: string;
  memo: string | null;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
  /** 활동 기록 — 최신부터 최대 50건(서버 ACTIVITY_LIMIT). 키는 DB 칸 이름 그대로 recorded_at(plan_REQ_04 T04-2.04) */
  activity?: { kind: string; recorded_at: string }[];
  /** 활동이 상한(50건)보다 많아 잘렸으면 참 — 화면은 "최근 50건만 보입니다"를 보인다(T04-6.04) */
  activity_truncated?: boolean;
}

/** 상태 표시 매핑 — 실제 프로젝트는 서버 설정 API 에서 읽는다(enum 하드코딩 금지, ui.md 규칙 6) */
export const ITEM_STATUS: Record<string, { label: string; tone: Tone }> = {
  active: { label: "사용 중", tone: "success" },
  archived: { label: "보관됨", tone: "neutral" },
};

export const ACTIVITY_LABEL: Record<string, string> = { created: "만듦", archived: "보관함", restored: "보관 풂", updated: "고침" };

/**
 * 운영 모니터링 상태 매핑(GET /ops/monitoring/overview) — 라벨 · 색(tone)을 한 곳에. 화면은 StatusBadge 에 넘기기만 한다
 * (삼항식으로 색을 고르지 않는다 — ui.md 규칙 6 · plan_REQ_04 T04-5.07). 매핑에 없는 코드는 StatusBadge 가 코드 그대로 · neutral 로 보인다
 */
export const OPS_HEALTH: Record<string, { label: string; tone: Tone }> = {
  ok: { label: "정상", tone: "success" },
  warning: { label: "주의", tone: "warning" },
  critical: { label: "위험", tone: "danger" },
};
/** 서비스 가동 여부(up: boolean → "true" · "false") */
export const SERVICE_UP: Record<string, { label: string; tone: Tone }> = {
  true: { label: "가동", tone: "success" },
  false: { label: "중단", tone: "danger" },
};
/** 알림 심각도(Prometheus 규칙 labels.severity) */
export const ALERT_SEVERITY: Record<string, { label: string; tone: Tone }> = {
  critical: { label: "위험", tone: "danger" },
  warning: { label: "주의", tone: "warning" },
  info: { label: "알림", tone: "info" },
};

/**
 * 개발용 로그인 안내(계정 버튼 · 비밀번호 미리 채우기 · 홈 안내 문구) — 운영 빌드에는 넣지 않는다.
 * - `next dev`(NODE_ENV=development): 기본으로 켠다. 끄려면 NEXT_PUBLIC_DEV_LOGIN=0
 * - `next build`(운영): NEXT_PUBLIC_DEV_LOGIN=1 로 빌드했을 때만 켠다(브라우저 스모크용 빌드 등)
 * 값은 빌드할 때 박힌다(next.config.mjs 가 늘 정의해 두므로 꺼진 빌드에서는 비밀번호 문자열이 번들에서 빠진다).
 * 게이트웨이 개발 로그인(GW_DEV_LOGIN)은 운영 기동을 따로 거부한다.
 */
export const DEV_LOGIN =
  process.env.NEXT_PUBLIC_DEV_LOGIN === "1" ||
  (process.env.NEXT_PUBLIC_DEV_LOGIN !== "0" && process.env.NODE_ENV !== "production");
/** 개발 계정 공통 비밀번호(services/gateway dev_users.json) — DEV_LOGIN 이 꺼지면 undefined */
export const DEV_PASSWORD: string | undefined = DEV_LOGIN ? "nova1234" : undefined;

export const DEV_ACCOUNTS = [
  { label: "사용자", email: "user@nova.dev" },
  { label: "책임자", email: "manager@nova.dev" },
  { label: "관리자", email: "admin@nova.dev" },
];
