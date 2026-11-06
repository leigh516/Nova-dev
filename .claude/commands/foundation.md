---
description: 기반 설계 — 언어 · 프레임워크 / 아키텍처 · 배포 / DB / 횡단관심사 채택 매트릭스(+ 표준 판정)를 4단계 질의로 정해 spec.json foundation · ADR 로 남긴다. /prd 뒤, /spec 앞
argument-hint: (선택) 초점 영역 또는 추가 맥락
---

# /foundation — 기반 설계 (4단계 질의)

이 프로젝트를 **어떤 기술과 구조로 지을지**를 기능 설계 전에 먼저 정한다. 아키텍처 스타일이 서비스 지도와 배포 형상을 좌우하므로 `/spec`(서비스 · 데이터 · API)보다 앞에 둔다.
참조: project-start-guide-05 `/foundation` 을 Nova 에 맞게 고쳤다. Nova 는 기본 스택과 공통 자산이 이미 있으므로, 질의는 **"Nova 기본을 쓸지, 어디서 벗어날지"** 를 묻는다.

## 입력 게이트
- `docs/product/prd.json` 이 `status: "승인"` 이다. 아니면 `/prd` 먼저
- **생략 가능**: 기반이 이미 정해진 저장소(spec.json `foundation` 이 채워짐)에 기능 하나를 더하는 경우 → 바로 `/spec`. 기존 결정을 바꾸려면 이 명령을 다시 돌리고, ADR 은 새 번호로 대체(supersede)한다

## 절차 — `AskUserQuestion` 4번(한 번에 최대 4문항). 질문마다 추천을 첫 보기로(Recommended), 판단 기준을 설명에 적는다
선택지 · 근거 조사가 넓으면 `architect` 에이전트에 맡긴다(ADR 은 본문 초안만 — 번호는 `docs_new.py adr`). PRD(사용자 수 · 기기 · 비기능 · 제약 · 일정)와 **요구 체크리스트 완료본의 '기술 결정' 답**을 먼저 읽는다. 체크리스트 md 의 `## 기술 결정 (/foundation 입력)` 절에 `feeds`(예: `foundation.stack.frontend`)별 답이 있다. 이미 답한 것은 다시 묻지 않고 확인만 한다("체크리스트에서 Next.js 를 고르셨는데 그대로 갈까요?"). 결정마다 **이유 한 줄**을 남긴다.

1. **언어 · 프레임워크**(프런트 / 백엔드 / 모바일)
   - Nova 기본:
     - 웹: Next.js 15 + React 19 + TypeScript(`@nova/ui` · `@nova/sdk`)
     - 백엔드: Python 3.12 + FastAPI(`nova_common`, uv)
     - 모바일: Kotlin Multiplatform + Compose(`kr.nova.uikit`)
   - 묻는 것: 각 층을 기본으로 쓸지, 쓰지 않을지(예: 모바일 없음), 다른 것을 쓸지
   - 판단 기준: 팀 숙련도 · 유지보수 · 채용 · 생태계 · 고객 지정
   - 기본에서 벗어나면 그 층은 Nova 공통 자산 없이 직접 만든다는 비용을 알린다
2. **아키텍처 스타일 + 배포 형상**
   - **모듈러 모놀리스**(추천 출발점 — 팀 1~10명 · 초기): 서비스 1~2개 안에 모듈로 경계를 긋는다. 나중에 `python nova.py new-service` 로 떼어 낸다
   - **MSA**: 도메인마다 서비스 · 자기 DB · 이벤트(Nova 의 게이트웨이 + `services.json` 구조 그대로). 운영 성숙도가 있을 때
   - **모놀리식**: 경계를 최소로 둔 단일 서비스
   - 배포: k3s(dev/prod 오버레이 · Helm, Nova 생성기) / docker-compose 단일 서버 / 기타
3. **DB · 영속성**
   - 엔진: MariaDB 11(Nova 기본 — 서비스별 DB, `local_db_setup.py`) / PostgreSQL / 기타
   - 마이그레이션: 개발 `create_all` → 운영 Alembic(Nova 기본) / 처음부터 Alembic
   - 기존 DB(`inbound/db-sql`)가 있으면 재사용 · 이전 · 병행 중 하나를 고른다
   - 스키마 자체는 `/spec` 이 정하고 여기서는 **엔진 · 전략만** 정한다
4. **횡단관심사 채택 매트릭스 + 표준 판정**
   - 관심사마다 **[내장 채택 / 직접 구현 / 미사용(이유)]** 을 고른다. 내장 채택이면 아래 Nova 자산을 쓴다(재발명 금지)

     | 관심사 | Nova 자산 |
     |---|---|
     | 인증 | `nova_common.auth`(JWT) + 게이트웨이 로그인 · 개발 로그인 |
     | 인가 · 권한 | 게이트웨이 `<모듈>.<행위>` + `services/gateway/gateway/rbac.json` |
     | 화면 셸 · 메뉴 | `@nova/ui` AppShell · `services/gateway/gateway/menu.json` · 기능 플래그 |
     | 디자인 시스템 | `design/tokens/brand.tokens.json` → `@nova/ui` · `kr.nova.uikit` |
     | 오류 표준 | `{error:{code,message}}` · ErrorState · useAction |
     | 로깅 · 감사 | `nova.events` 로거 · 이벤트 봉투(actor_type · tenant) |
     | 관측성 | `nova_` 메트릭 · Prometheus · Alertmanager · Grafana |
     | 이벤트 · 메시징 | 아웃박스 · 멱등 소비 · DLQ · Kafka |
     | 목록 · 검색 · 페이지 | `nova_common.paging` · DataTable · ListPage |
     | 다국어(i18n) | 내장 없음 — 직접 구현 또는 미사용 |
     | 파일 · 첨부 | 내장 없음 — 직접 구현 또는 미사용 |

   - **같은 질의 안에서** 표준 3종도 판정한다. 어휘가 다르다: 표준은 **[적용 / 면제(이유)]**. 면제도 결정이므로 이유를 남긴다([docs/std](../../docs/std/README.md))
     - STD-TENANCY-001: 둘 이상 조직이 한 시스템을 함께 쓰나
     - STD-DOMAIN-PACK-001: 여러 업종에 다시 낼 제품인가
     - STD-AX-001: AI 가 조회 이상(쓰기 · 승인)을 하나
5. **디자인 킷 확인**(화면이 있으면 건너뛰지 않는 관문 — 체크리스트 설정을 놓치지 않게, REQ-261106-04 · [킷 절](../../docs/design-system/README.md))
   - `python nova.py kit show` 로 지금 킷 · 출처(체크리스트 · 수동 · 기본) · 날짜 · 부품 갭을 보여 주고 **사용자 확인**을 받는다
   - 바꾸려면 `python nova.py kit use <id>`(목록 `python nova.py kit list` — 대비 검사를 통과한 킷만 받는다). 출처가 기본(설정 없음 — 체크리스트 미실행)이면 이 단계에서 고르게 한다
   - 확인한 킷과 부품 갭은 보고에 적는다(갭 부품은 `/plan-new` 에서 만들지 · 대신할지 정한다)
   **UI 구성**(선택 — 화면이 있으면): 셸 구성(사이드바 · 헤더 · 메뉴 · 테마)을 목업으로 보여 고른다(superpowers:brainstorming 시각 도우미).
   - 체크리스트 `design.source` 답에 따라 시안을 만든다
     - `skill`: `design.source.skill` 에서 고른 스킬을 호출한다 — `impeccable`(시안 · 다듬기), `anthropic-skills:theme-factory`(색 · 글꼴 테마), `design:design-critique`(비평), `design:accessibility-review`(접근성)
     - `figma`: `figma:figma-design-to-code` 로 시안 · 토큰을 가져온다
     - `system` · `site`: 그 느낌을 토큰 값으로 옮긴 시안 2~3개를 만든다
   - 어느 경우든 시안은 고객이 고른 뒤 토큰으로 옮기고 대비 검사를 거친다. 베끼지 않고, 라이선스를 확인한다. 결과는 킷이 `nova` 면 `design/tokens/brand.tokens.json` 브랜드 색, 다른 킷이면 그 킷 파일(`design/tokens/kits/<id>.tokens.json`)과 `docs/plans/mockups/_shell.json` 에 반영한다(`python nova.py tokens` 로 대비 검사)

## 산출물
1. `docs/product/spec.json` 의 `foundation`
   - spec.json 이 없으면 `_template_spec.json` 을 복사하고, `prd_version` 을 PRD 버전에 맞춘다
   - 채울 것: stack · architecture · database · crosscutting(11개 전부) · adr
2. **ADR 3건**: `uv run python scripts/docs_new.py adr "<제목>" --slug <영문>` 으로 기술 스택 · 아키텍처 스타일 · DB 를 남긴다
   - 상태는 채택, 검토한 대안 표 포함
   - 번호는 도구가 매긴다. 기존 결정을 바꾸면 새 ADR 로 대체하고, 옛 ADR 상태를 `대체됨(→ ADR-NNN)` 으로 바꾼다
3. **표준 판정**: `nova.project.json` `standards` 에 `{decision, reason, by, date}` 를 쓴다. 정본은 여기 하나다(`by: platform-default` 를 실제 판정으로 바꾼다)
4. 아키텍처가 정해지면 서비스 지도 초안을 spec.json `services` 에 적는다. 이름 · 그룹 · 책임만 적고, 서비스 생성은 `/spec` 승인 뒤에 한다
5. `uv run python scripts/warehouse.py check` → `out` → `uv run python scripts/docs_index.py --check`

## 출력 게이트
foundation 이 채워지고(`warehouse.py check` 통과) ADR 이 기록되면 다음은 `/spec`. 기본에서 벗어난 층(예: 백엔드 Java)이 있으면, 그 층을 위해 Nova 에서 무엇을 쓰지 못하는지를 보고에 적는다.

## 마무리
스택 · 아키텍처 · DB 를 한 줄로 요약하고, 채택 · 직접 구현 · 미사용 수, 표준 판정, 디자인 킷(확인 결과 · 부품 갭), ADR 경로를 보고한 뒤 `/spec` 을 제안한다.
