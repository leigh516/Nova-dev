# ADR-014 · 웹 인증을 httpOnly 쿠키로 단일화

| 항목 | 내용 |
|---|---|
| 일자 | 2026-11-05 |
| 상태 | 채택(사용자 2026-11-05 "진행해주세요") |
| 대체 | 없음 |
| 요구 | [REQ-261104-12](../requirement/requirement_261104_12.md) R16 · [plan_REQ_04](../plans/plan_REQ_04.md) 8단계 |
| 원천 | [REQ-261104-12](../requirement/requirement_261104_12.md) R16 — task T04-1.02(ADR 본문 초안) · 사용자 채택 2026-11-05 |
| 연결 | 실행 [plan_REQ_04](../plans/plan_REQ_04.md) 8단계 · [tasks_REQ_04](../plans/tasks/tasks_REQ_04.md) · 인용 [plans README](../plans/README.md) · [review_261105_02](../reviews/review_261105_02.md) |

## 배경
웹은 토큰을 localStorage 에 두고 Bearer 헤더로 보낸다. 스크립트 주입(XSS) 한 번이면 토큰이 빠져나간다. 게이트웨이는 이미 쿠키(`nova_token`)를 읽지만 발급 · 로그아웃 · CSRF 방어가 없다(plan_REQ_04 §1).

## 결정
- 로그인 응답이 `nova_token` 쿠키를 심는다: **HttpOnly · SameSite=Lax · Path=/v1 · Max-Age=토큰 수명(7일 유지 — 사용자 결정 2026-11-04) · 운영 Secure**(`GW_COOKIE_SECURE`, 운영 기본 켬)
- **CSRF**: 쿠키로 인증된 쓰기 요청은 Origin 이 허용 목록(`GW_CORS_ORIGINS`)일 때만 — 아니면 403 `csrf_origin`. Bearer 요청은 면제. 쿠키를 심고 지우는 로그인 · 로그아웃 POST 는 인증 여부와 무관하게 `Origin` 이 있으면 허용 목록이어야 한다(아니면 403 `csrf_origin`, `Origin` 이 없는 모바일 · 서버 호출은 통과). 개발 로그인은 JSON 이 아니면 415 `unsupported_media_type`. 같은 출처 배포도 자기 출처를 목록에 넣는다
- 쿠키 모드에서 `GW_CORS_ORIGINS` 에 `*` 가 있으면 **기동 거부**
- `POST /v1/auth/logout` 이 쿠키를 지운다(Max-Age=0, 비로그인 · 깨진 · 만료 쿠키도 204, 허용 밖 Origin 은 403)
- 모바일은 Bearer 그대로(쿠키 저장소가 없다 — 응답 본문 token 유지)
- 전환 순서 **Expand → Migrate → Contract**: 게이트웨이가 쿠키를 함께 내고(Expand) → SDK 가 `credentials:"include"` 로 바꾸고 저장 토큰을 지우고(Migrate) → 웹의 토큰 경로를 없앤다(Contract). 착수는 plan_REQ_04 1~7단계가 녹색인 뒤(사용자 결정)
- 전제: 웹과 게이트웨이는 **같은 사이트**에 배포한다. 다른 사이트면 새 요구

## 검토한 대안
| 대안 | 장점 | 단점 | 버린 이유 |
|---|---|---|---|
| localStorage + Bearer 유지 | 변경 없음 | XSS 한 번에 토큰 유출 | 보안 기준 미달 |
| 쿠키 + CSRF 토큰(이중 제출) | 다른 사이트 배포도 가능 | 구현 · 화면 비용 큼 | 같은 사이트 전제에서 SameSite=Lax + Origin 검사로 충분 |
| BFF(웹 서버가 토큰 보관) | 가장 강함 | 구조 변경이 크다 | 이번 범위를 넘는다 — 필요해지면 새 요구 |

## 결과
- 좋아지는 것: 브라우저 스크립트가 토큰을 읽을 수 없다. 새로고침 · 새 탭에서도 로그인 유지
- 감수하는 것: 같은 사이트 배포 전제 · 배포 설정(`GW_COOKIE_SECURE` · 정확한 `GW_CORS_ORIGINS`) 필요
- 되돌리기: Contract 전까지는 Bearer 경로가 남아 SDK 만 되돌리면 된다. Contract 뒤에는 SDK · 웹을 같은 묶음으로 되돌린다
- 이후 규칙: 보안 검토(security-auditor — T04-8.11) 치명 0 이어야 Contract

보완 2026-11-05 — T04-8.11 보안 검토(로그인 CSRF)
