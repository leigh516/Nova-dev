import type { Metadata, Viewport } from "next";
import "@nova/ui/styles.css";
import Shell from "./shell";

export const metadata: Metadata = { title: "Nova 샘플 앱", description: "Nova 공통개발플랫폼 — 템플릿 · 컴포넌트 · 게이트웨이 연동 예시" };
export const viewport: Viewport = { themeColor: "#141821", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" />
      </head>
      <body>
        <a href="#main" className="sr-only">본문으로 건너뛰기</a>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
