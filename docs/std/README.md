# docs/std — 전사 표준 (STD)

> 한 줄 요약: **무엇을 지켜야 하는가**의 정본. `docs/conventions/` 가 *어떻게 쓰는지*(코드 · 화면 규약)를 다룬다면 여기는 *프로젝트마다 판정해야 하는 아키텍처 조항*을 다룬다. 출처: project-start-guide-05 `docs/std` 를 Nova 의 코드 · 도구에 맞게 다시 썼다([REQ-261103-04](../requirement/requirement_261103_04.md)).

## 왜 기계 게이트가 아니라 "판정 의무"인가
이 표준들은 **프로젝트마다 정답이 다른 선택**(격리 모델 M1/M2/M3, 코어/팩 분리 여부, 자동화 허용 등급)이다. 기계가 하나를 강요하면 맞지 않는 프로젝트가 우회하고, 우회가 습관이 되면 게이트 전체가 죽는다.
대신 Nova 는 **판정 없이는 넘어가지 못하게** 한다:
- 프로젝트는 표준마다 `nova.project.json` 의 `standards` 에 **적용 / 면제 + 이유**를 남긴다 — `docs_index.py --check`(lint)가 판정이 없거나 이유가 비면 실패
- 세부 계획서 §0 영향분석에 **표준 판정** 줄이 있다(테넌시 · 코어/팩 · AX 등급) — 해당 없음이면 이유
- 적용한 표준의 **기계로 검사할 수 있는 부분**은 플랫폼 코드와 lint 가 맡는다(아래 "Nova 가 이미 해 주는 것")

## 표준 목록
| 번호 | 표준 | 언제 적용 | 면제 조건 | Nova 가 이미 해 주는 것 |
|---|---|---|---|---|
| [STD-TENANCY-001](STD-TENANCY-001.md) | 멀티테넌시 5조 | 한 시스템을 둘 이상의 고객 · 조직이 공유 | 단일 조직 전용 | `nova_common.context` 테넌트 전파(게이트웨이 → 헤더 → 서비스 → 이벤트), `tenant_column` · `tenant_filter` · `require_tenant`, 스푸핑 헤더 제거, 교차 테넌트 테스트 예시 |
| [STD-DOMAIN-PACK-001](STD-DOMAIN-PACK-001.md) | 코어 · 도메인 팩 분리 | 같은 제품을 여러 업종 · 고객군에 재출시 | 단일 도메인 제품 | `nova_common.packs` 포트 · 구현, `packs/<팩>/` 골격, `nova.py new-pack`, 의존 방향 검사(`packs.py check`) |
| [STD-AX-001](STD-AX-001.md) | AI 자동화 등급 L0~L3 | AI 가 조회 이상을 함 | AI 기능 없음 | 게이트웨이 `x-actor-type`, `Principal.actor_type` · `require_human()`, 이벤트 봉투 `actor_type`(감사 분리), AI 도 같은 RBAC |

## 판정 기록 형식 (`nova.project.json`)
```json
"standards": {
  "STD-TENANCY-001":     {"decision": "적용", "model": "M1", "reason": "…", "date": "2026-11-04", "by": "이름"},
  "STD-DOMAIN-PACK-001": {"decision": "면제", "reason": "단일 업종 제품 — 두 번째 업종이 보이면 다시 판정", "date": "…", "by": "…"},
  "STD-AX-001":          {"decision": "적용", "default_level": "L1", "reason": "…", "date": "…", "by": "…"}
}
```
- `decision`: `적용` | `면제`. 면제도 결정이므로 이유를 남긴다 — 안 적으면 "몰라서 안 한 것"과 구분되지 않는다
- `new_project.py` 로 만든 프로젝트는 플랫폼 기본 판정을 물려받되 `by: "platform-default"` 로 표시된다 → **첫 계획에서 다시 판정**한다

## 도메인별 사용 — 어떤 표준을 어디에
| 상황 | 표준 | 첫 행동 |
|---|---|---|
| 여러 회사 · 매장이 같은 시스템을 쓴다(SaaS · 프랜차이즈) | TENANCY 적용(M1) | 업무 표에 `tenant_column()`, 조회는 `tenant_filter`, 교차 테넌트 테스트 |
| 규제 · 대형 고객이 데이터 분리를 요구 | TENANCY M2/M3 | 연결 계층에서 테넌트별 스키마/DB — 코드는 그대로(ADR 로 결정) |
| 같은 제품을 다른 업종에(창고 → 의약품 · 신선식품) | DOMAIN-PACK 적용 | 갭 분석(코어로 충분 · 포트로 흡수 · 코어 승격) → `nova.py new-pack` → 용어 오버레이부터 |
| AI 가 요약 · 초안 · 실행을 한다 | AX 적용 | 기능별 등급(L0~L3)을 계획서 §0 에, L2 이상은 승인 경로 · `actor_type` 감사 |
| 사내 단일 조직 도구 | TENANCY · DOMAIN-PACK 면제 | 면제 이유 기록 |

## 번호 규칙
- `STD-{주제}-{3자리}`. 주제는 대문자(`TENANCY` · `DOMAIN-PACK` · `AX`)
- 표준을 바꿀 때는 지우지 않고 맨 위에 `대체됨 → STD-…` 을 적는다(ADR 과 같은 관행). 새 표준을 추가하면 이 목록과 `nova.project.json` 판정에 함께 추가한다(lint 가 판정 누락을 잡는다)

## 관련 문서
- 백엔드 규약: [backend.md](../conventions/backend.md) · UI/UX: [ui.md](../conventions/ui.md) · [ux-heuristics.md](../conventions/ux-heuristics.md)
- 대장(권한 · 이벤트 · DB): [docs/registry](../registry/README.md) · 형식 결정: [ADR-004](../adr/ADR-004-ledger-formats.md)
