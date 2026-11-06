"use client";
/** @screen 홈 · @status 완료 */
import { Card, Content, PageHeader, Section, useSession } from "@nova/ui";
import { DEV_LOGIN, DEV_PASSWORD } from "../lib/app";

export default function Home() {
  const { user } = useSession();
  return (
    <Content width="default">
      <PageHeader title={user ? `${user.name}님, 반갑습니다` : "Nova 샘플 앱"}
        description="공통개발플랫폼의 템플릿 · 컴포넌트 · 게이트웨이 연동을 보여 주는 앱입니다. 새 앱은 이 폴더를 복사해 시작합니다." />
      <div className="grid">
        <Card><h3>항목</h3><p className="muted small mt-2">목록 · 검색 · 정렬 · 페이지 · 보관/실행 취소 · 삭제 확인 — ListPage 템플릿</p><p className="mt-3"><a href="/items">항목으로 →</a></p></Card>
        <Card><h3>디자인</h3><p className="muted small mt-2">공통 컴포넌트 갤러리 — 토큰 · 버튼 · 배지 · 상태 · 표</p><p className="mt-3"><a href="/design">갤러리로 →</a></p></Card>
        <Card><h3>도움말</h3><p className="muted small mt-2">처음 쓰는 사람을 위한 안내와 단축키(<kbd>?</kbd>)</p><p className="mt-3"><a href="/help">도움말로 →</a></p></Card>
      </div>
      {!user && (
        <Section title="시작하기">
          {DEV_LOGIN
            ? <p className="secondary">오른쪽 위 <b>로그인</b>을 눌러 개발용 계정(비밀번호 <code>{DEV_PASSWORD}</code>)으로 들어가세요. 로그인하지 않아도 공개된 항목 목록은 볼 수 있습니다.</p>
            : <p className="secondary">오른쪽 위 <b>로그인</b>을 눌러 들어가세요. 로그인하지 않아도 공개된 항목 목록은 볼 수 있습니다.</p>}
        </Section>
      )}
    </Content>
  );
}
