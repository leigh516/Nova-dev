/** @type {import('next').NextConfig} */
export default {
  transpilePackages: ["@nova/ui", "@nova/sdk"],
  reactStrictMode: true,
  poweredByHeader: false,
  output: "standalone",
  // 늘 정의해 두어 빌드 때 문자열로 박히게 한다 — 꺼진 운영 빌드에서 개발 비밀번호가 죽은 코드로 빠진다(lib/app.ts DEV_LOGIN)
  env: { NEXT_PUBLIC_DEV_LOGIN: process.env.NEXT_PUBLIC_DEV_LOGIN ?? "" },
};
