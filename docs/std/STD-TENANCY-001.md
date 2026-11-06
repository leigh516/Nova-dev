# STD-TENANCY-001 — 멀티테넌시 표준

> **한 줄 요약:** 멀티테넌트는 "나중에 붙이는 기능"이 아니라 DB · API · 캐시 · 로그 · 파일 · 이벤트 **모든 층의 기본값**이다. **테넌트 필터가 빠진 코드는 버그가 아니라 보안사고**다.

- 상태: 표준(판정 의무) · 출처: project-start-guide-05 STD-TENANCY-001 → Nova 코드 기준으로 다시 씀
- 적용 대상: 한 시스템을 **둘 이상의 고객 · 조직이 공유**하는 프로젝트. 단일 조직 전용이면 **면제**(판정 기록)

## 왜 필요한가
`WHERE tenant_id = ?` 하나가 빠지면 다른 고객의 데이터가 보인다. 개발자 · AI 가 매번 기억해야 하는 구조 자체가 결함이다. 목표는 **기억하지 않아도 되게** — Nova 는 컨텍스트 전파와 헬퍼로 이를 기본값으로 만든다.

## 격리 모델 — 계약 등급별 혼용 가능
| 모델 | 방식 | 적합 | Nova 에서 |
|---|---|---|---|
| **M1 공유 스키마** | 모든 업무 표 `tenant_id` + 행 수준 격리 | 일반 SaaS **기본값** | `tenant_column()` · `tenant_filter()` |
| **M2 스키마 분리** | 테넌트별 스키마 | 규제 · 중견 고객 | `DATABASE_URL_<SVC>` 를 테넌트별로 고르는 연결 계층(ADR 로) |
| **M3 DB/인스턴스 분리** | 테넌트별 DB · 배포 | 공공 · 금융 | 테넌트별 오버레이(k3s) |

**어떤 모델이든 애플리케이션 코드는 같다** — 격리는 연결 계층이 흡수한다. 코드는 `current_tenant()` 만 안다.

## 5조 (필수)

### ① 모든 업무 표에 테넌트 칸
`tenant_id: Mapped[str | None] = tenant_column()` (`nova_common.context`). 예외는 플랫폼 메타 표(테넌트 목록 자체 등)뿐이며 [DB 사전](../registry/db-dictionary.md)에서 확인된다. 공통 표 `outbox` · `processed_event` 는 이벤트 봉투가 테넌트를 싣는다(④).

### ② 조회는 항상 테넌트 범위로
`tenant_filter(select(Model), Model)` — 테넌트가 있으면 그 테넌트 행만, 없으면 `tenant_id IS NULL` 행만(다른 조직 행이 새지 않는다). 단건 조회도 `item.tenant_id != current_tenant()` 이면 **404**(존재 자체를 숨긴다 — 샘플 `_get` 참조). 테넌트가 꼭 필요한 쓰기는 `require_tenant()`(없으면 400).
> RLS(행 수준 보안)를 쓰는 엔진이면 DB 세션 변수와 정책을 추가로 건다. MariaDB 는 네이티브 RLS 가 없어 **앱 레벨 강제(이 헬퍼) + 리뷰 · 테스트**로 대신한다.

### ③ 컨텍스트는 전파하고, 손으로 나르지 않는다
```
JWT 클레임 tenant → 게이트웨이 검증(클라이언트가 보낸 x-tenant 는 지운다) → x-tenant 헤더
→ 서비스 미들웨어가 nova_common.context 에 심음 → clients.call 이 다음 서비스로 자동 전달
→ svc.emit 이 이벤트 봉투 tenant 에 자동 기록 → 소비자가 봉투 tenant 로 다시 심음
```
**함수 파라미터로 `tenant_id` 를 나르지 않는다.** 클라이언트가 보낸 값을 믿지 않는다(게이트웨이 `SPOOFABLE`).

### ④ 네임스페이스는 DB 밖에도
캐시 키 · 파일 경로 · 로그 · 이벤트 · 백업 · 검색 인덱스 — 전부 테넌트를 가진다.
- 이벤트: 봉투 `tenant`(자동). 테넌트별 토픽이 필요하면 토픽 이름이 아니라 키 · 봉투로(토픽 폭증 방지)
- 캐시 · 파일: 키 앞에 `f"{current_tenant()}:"` · 경로 `tenant/<id>/…`
- 로그: 요청 로그에 테넌트를 남긴다(개인정보는 남기지 않는다)

### ⑤ 교차 테넌트 조회는 별도 권한 + 감사
플랫폼 운영자의 교차 조회 · 대리 로그인(impersonation)은 전용 권한키(예: `platform.cross_tenant`)로 분리하고 [권한 대장](../registry/permissions.md)에 등재, 감사 로그(누가 · 언제 · 어느 테넌트)를 남긴다.

## SaaS 플랫폼 코어 체크리스트 (도메인 무관)
- [ ] 테넌트 온보딩 파이프라인(**멱등** — 다시 돌려도 안전)
- [ ] 플랜별 메뉴 · 기능 매트릭스(게이트웨이 `menu.json` · 기능 플래그 → 플래그 서비스)
- [ ] 사용량 계측 → 요금(`nova_business_events_total` 메트릭으로 시작)
- [ ] 테넌트별 설정과 브랜드(디자인 토큰 테마)
- [ ] 관리자 레벨별 권한 · 대리 로그인(감사 동반)
- [ ] 테넌트 생명주기(체험 → 활성 → 제한 → 해지) — 제한 중에도 장애 알림은 보낸다

## 계획서 §0 에서 확인할 것
- [ ] 새 표에 `tenant_column()` 이 있는가(없으면 플랫폼 메타 표인 이유)
- [ ] 조회가 `tenant_filter` · `_get` 404 를 쓰는가 — 테넌트 필터 없는 쿼리 발견 시 **P0**
- [ ] 캐시 키 · 파일 경로 · 로그에 테넌트가 있는가
- [ ] **교차 테넌트 테스트**가 있는가(테넌트 A 로 B 의 데이터를 못 읽는다 — `services/sample/tests/test_items.py::test_tenant_isolation`)

## 면제
단일 조직 시스템 · 내부 도구 · 라이브러리는 면제를 판정으로 남긴다. 나중에 멀티테넌트로 바꾸는 비용은 처음부터 넣는 비용의 수십 배임을 알고 결정한다. Nova 의 `tenant_column` 은 비어 있어도 동작하므로 **칸은 처음부터 두는 것을 권장**한다.

## 관련 문서
[표준 목록](README.md) · [STD-DOMAIN-PACK-001](STD-DOMAIN-PACK-001.md) · [STD-AX-001](STD-AX-001.md) · [backend.md](../conventions/backend.md) · 코드 `packages/common-py/nova_common/context.py`
