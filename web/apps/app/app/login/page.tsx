"use client";
/** @screen 로그인 · @status 완료 */
import { LoginPage } from "@nova/ui";
import { APP, DEV_ACCOUNTS, DEV_LOGIN, DEV_PASSWORD } from "../../lib/app";

const LINKS = [{ label: "아이디 · 비밀번호 찾기", href: "/help" }];

/** 개발용 계정 버튼 · 비밀번호 미리 채우기는 DEV_LOGIN 일 때만(운영 빌드 제외 — lib/app.ts). 아이디 저장은 이메일만 */
export default function Login() {
  return DEV_LOGIN
    ? <LoginPage brand={APP.brand} title="로그인" subtitle="개발용 계정으로 바로 들어갈 수 있습니다." demo={DEV_ACCOUNTS} demoPassword={DEV_PASSWORD} after="/items" rememberId links={LINKS} />
    : <LoginPage brand={APP.brand} title="로그인" subtitle="이메일과 비밀번호를 입력하세요." after="/items" rememberId links={LINKS} />;
}
