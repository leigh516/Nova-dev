---
description: 현황 진단(기존 프로젝트 합류 · 현황 파악) — 분모 고정 → 대장 · 원장 조회 → 게이트 출력 → 축별 진단 한 장을 내고, 결함 사냥은 /deep-audit(처분 5갈래)로 넘긴다. 새 프로젝트 시작은 /kickoff
argument-hint: [집중 영역 경로 …] (비우면 전체)
---

# /analyze — 현황 진단

인자: `$ARGUMENTS`
규칙: 분모 [audit_scope.py](../../scripts/audit_scope.py) · 대장 [docs/registry](../../docs/registry/README.md) · 감사 [/deep-audit](deep-audit.md) · 북극성 [PROJECT.md](../../docs/PROJECT.md)

`/analyze` 는 **지도를 그리는** 명령이다(무엇이 어디 있고 지금 녹색인가). 개선점을 파헤쳐 고치는 것은 `/deep-audit` 이다 — 둘을 한 번에 하지 않는다.

## 절차
1. **분모 고정**: `uv run python scripts/audit_scope.py $ARGUMENTS` — 축별 대상 수 · 제외(생성물 · 잠금 · 캡처)와 사유. 진단 보고의 모든 수는 이 분모에 대어 말한다
2. **원천 · 대장을 읽는다**(코드를 훑기 전에 — 이미 정리된 답이 있다)
   - 서비스 `packages/common-py/nova_common/services.json` · 토픽 `infra/k3s/base/kafka-topics.txt` · 프로젝트 메타 `nova.project.json`(standards · packs)
   - 대장 4종 `docs/registry/`(화면 · DB 사전 · 권한 · 이벤트) — `uv run python scripts/ledgers.py` 로 최신인지 먼저
   - 명명 · 개념 원장: `python nova.py naming check`
   - 제품 정본이 있으면 `docs/product/intake.json` · `prd.json` · `spec.json`, 입고 자료가 새로 있으면 `/intake` 로 보낸다
3. **게이트 출력**: `python nova.py check`(test · lint 동시) · `python nova.py progress` · `python nova.py doctor`. 출력을 자르지 않는다(종료 코드를 삼킨다)
4. **축별 진단** — 범위에 실재하는 축만, 대상 수와 함께: 구조(서비스 · 패키지 · 웹 · 모바일) · 의존성(`uv.lock` · `web/package-lock.json` · Gradle) · 백엔드(라우트 · 권한 `<모듈>.<행위>` · 오류 봉투 · 아웃박스) · 화면(템플릿 · 토큰) · 데이터(UUIDv7 · comment · ref_column) · 문서 정합. 넓으면 `researcher` 에이전트에 축 하나씩 맡겨 한 메시지에 함께 띄운다(읽기 전용 · 한국어 4절 보고 — 핵심 답 · 실측 · 근거 · 미해결)
5. **보고**(화면) — 요약 한 문단 → 강점 → 개선 필요(심각 순, `파일:줄`) → 판정 불가(무엇이 있으면 되는지) → 권장 다음
6. 다음으로 보낸다

   | 본 것 | 다음 |
   |---|---|
   | 결함 · 개선점을 파헤쳐 고쳐야 한다 | `/deep-audit [범위]`(처분: 즉시 고친다 · 기록으로 옮긴다 · 의도적으로 안 한다 · 판정 불가 · 제안한다) |
   | 북극성 · 범위가 비어 있다 | `/kickoff` |
   | 새 요구가 보였다 | `/req-new` |
   | 재현되는 결함 | `/issue` → `/debug` |

## 하지 않는 것
- 진단 중에 고치기 — 고치는 것은 `/deep-audit` §6 의 처분을 거친다
- 게이트가 이미 잡는 것(lint · test)을 발견으로 다시 세기
- 보고 파일 만들기 — 진단은 화면 보고다(남겨야 하면 `/deep-audit` 가 `docs/reviews/` 에 남긴다)
