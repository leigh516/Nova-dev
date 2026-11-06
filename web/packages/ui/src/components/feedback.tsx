"use client";
/**
 * 상태 컴포넌트 — 빈 상태 · 오류 · 권한 없음. 템플릿이 자동으로 그린다(화면에서 따로 만들지 않는다, ui.md 규칙 5).
 * 오류 문구 3요소(UX H9): 무엇이 안 됐나 · 왜 · 무엇을 하면 되나. 상태 코드만 보여 주지 않는다.
 */
import React from "react";
import type { ApiError } from "@nova/sdk";
import { Button } from "./basic";

export function EmptyState({ icon = "📭", title, description, action }: { icon?: string; title: string; description?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="state">
      <div className="ic" aria-hidden="true">{icon}</div>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action && <div className="actions">{action}</div>}
    </div>
  );
}

export function Forbidden({ error, hint }: { error?: ApiError | null; hint?: string }) {
  const perm = error?.detail?.perm as string | undefined;
  const desc = error?.code === "forbidden_user" ? "이용이 제한된 계정입니다. 관리자에게 문의하세요."
    : hint ?? "이 계정의 역할로는 열 수 없습니다. 필요하면 관리자에게 권한을 요청하세요.";
  return (
    <div className="state" role="alert">
      <div className="ic" aria-hidden="true">🔒</div>
      <h3>이 화면을 볼 권한이 없습니다</h3>
      <p>{desc}</p>
      {perm && <p className="code">필요한 권한 <code>{perm}</code></p>}
    </div>
  );
}

export function ErrorState({ error, onRetry, loginHref = "/login" }: { error: ApiError | null; onRetry?: () => void; loginHref?: string }) {
  if (!error) return null;
  if (error.code === "maintenance") {
    return <EmptyState icon="🛠" title="점검 중입니다" description={`${error.message} 점검이 끝나면 자동으로 다시 열립니다.`} action={onRetry && <Button variant="secondary" onClick={onRetry}>다시 확인</Button>} />;
  }
  // 권한 원천 일시 장애 — 게이트웨이는 503 + Retry-After 로 낸다(ADR-012 P10). 상태 코드보다 먼저 오류 코드로 가른다.
  // '권한 없음'이 아니라 잠시 뒤 풀리는 장애이므로 다시 시도를 준다(T03-6.08 Expand · 6.10 에서 Forbidden 의 옛 분기 제거)
  if (error.code === "rbac_unavailable") {
    return (
      <div role="alert">
        <EmptyState icon="⏳" title="권한 정보를 잠시 확인할 수 없습니다" description="잠시 후 다시 시도하세요. 계속되면 관리자에게 알려 주세요."
          action={onRetry && <Button variant="secondary" onClick={onRetry}>다시 시도</Button>} />
        <p className="state code">오류 코드 {error.code}</p>
      </div>
    );
  }
  if (error.status === 403) return <Forbidden error={error} />;
  if (error.status === 401) {
    return <EmptyState icon="🔑" title="로그인이 필요합니다" description={error.message} action={<a className="btn primary" href={loginHref}>로그인하기</a>} />;
  }
  const title = error.status === 0 ? "서버에 연결할 수 없습니다" : error.status === 404 ? "찾는 항목이 없습니다" : "불러오지 못했습니다";
  return (
    <div role="alert">
      <EmptyState icon="⚠️" title={title} description={error.message}
        action={onRetry && <Button variant="secondary" onClick={onRetry}>다시 시도</Button>} />
      <p className="state code">오류 코드 {error.code}</p>
    </div>
  );
}
