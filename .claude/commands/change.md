---
description: 변경요청 — 이미 만든 것을 바꿔 달라는 요청을 접수하고 영향을 조회해 등급(L1~L3)을 매긴 뒤 사용자 승인을 받아 계획으로 보낸다. 영향분석 없이 승인 없다
argument-hint: <요청 한 줄> | <ISS-ID>
---

# /change — 변경요청 접수 · 영향분석 · 승인

인자: `$ARGUMENTS`
원장: [docs/issues/README.md](../../docs/issues/README.md) — 변경요청은 결함과 같은 원장에 `--kind change` 로 들어간다

구분: [/issue](issue.md) 결함 = 만들기로 한 것이 안 된다 · `/req-new` = 처음 요구 · **/change = 만들기로 한 것 자체가 바뀐다**. 접수는 언제든, 반영은 경계(다음 판본 · 계획)에서만.

## 절차
1. **접수** — 고객의 말 그대로를 남기고 해석을 덧붙인다(해석이 틀렸을 때 원문으로 돌아가려고). 승인 재료 정리는 `change-manager` 에이전트에 맡길 수 있다
   ```bash
   python nova.py issue add --kind change --grade P2 --title "<한 줄>" \
     --repro "지금 동작: …" --expected "바뀌길 원하는 것: 고객 원문 \"…\" / 해석: …" \
     --actual "지금은 …" --env "v0.1.0 기준 · 범위 …"
   ```
2. **영향 조회** — 조사가 아니라 조회다. 대장 · 원장 · 서비스 목록 · 소스를 역참조한다
   ```bash
   python nova.py impact <표> <컬럼> <화면ID> <API 경로> <권한키> <이벤트> …
   ```
   참조가 넓거나 계약 · 스키마가 걸리면 `contract-auditor` 에이전트에게 영향 등급 판정 재료를 맡긴다(읽기 전용 — 판정은 사람). 토큰 · 디자인 규칙 변경이면 `design-rule-architect` 를 함께.
   출력의 **5줄 보고 초안**(대상 · 직접 · 간접 · 등급 힌트 · 갱신할 산출물)을 읽고 사람이 고쳐 확정한다. 필요하면 대장을 더 본다([docs/registry/](../../docs/registry/README.md))
3. **등급** — 도구의 등급은 힌트다. 판정은 사람 몫이고, 애매하면 한 단계 올린다

   | 등급 | 정의 | 필요한 것 |
   |---|---|---|
   | L1 로컬 | 한 화면 · 모듈 안, 계약 불변 | 간이 승인 → 🆕 task 로 |
   | L2 도메인 | 한 서비스의 표 · API · 이벤트에 **추가만** | 승인 + Expand + 대장 · 원장 동시 갱신 → `/plan-new` |
   | L3 전역 | 계약의 **의미 변경 · 삭제**, 여러 서비스로 번짐 | 승인 + **ADR**(`docs_new.py adr`) + Expand→Migrate→Contract 3단 계획 → `/plan-new` |

   영향도(L1~L3)와 심각도(P0~P3)는 다른 축이다 — 합치지 않는다
4. **사용자 승인** — 5줄 보고 · 등급 · 대가(무엇을 다음 판본으로 미루나)를 보여 주고 **사용자가 승인한 뒤에만** 올린다
   ```bash
   python nova.py issue set <ISS-ID> --status in_progress \
     --impact "1) 대상 … 2) 직접 … 3) 간접 … 4) 등급 … 5) 갱신 …" \
     --level L2 --approved-by "<승인한 사람>"
   # L3 면: --adr docs/adr/ADR-NNN-….md   (파일이 실재해야 한다)
   ```
   영향(impact) · 등급(level) · 승인자(approved-by) 중 하나라도 없거나, L3 인데 ADR 이 실재하지 않으면 **거부된다**
5. **계획으로** — L2 · L3 는 `/plan-new`(§0 영향분석에 5줄 보고를 옮긴다), L1 은 진행 중 계획의 🆕 task 로
   - Expand(새 구조 추가만 · 기존 불변) → Migrate(백필 · 코드 전환, 신 · 구 병행) → Contract(아무도 옛 구조를 안 쓸 때 제거) — 단계마다 커밋 · 마이그레이션을 나눈다
   - 마이그레이션 · 계약 변경을 반영하기 직전에 `python nova.py release checkpoint "<무엇> 직전"` 을 권고한다 — 잘못되면 `release rollback <태그>` 로 코드를 돌릴 지점(DB 데이터는 돌리지 않는다 — Expand 단계가 그 대비다 · [판본 규약 §9](../../docs/conventions/versioning.md) · REQ-261106-02)
   - 표 · 화면 · API · 토픽을 만들거나 지우면 `registry.py sync`, 대장은 `ledgers.py` 로 다시 만든다
   - Contract 가 남으면 `/session-end` 인수인계의 "다음" 에 적는다
6. **마감** — 반영되면 `python nova.py issue set <ISS-ID> --status closed`, 이력 · git 기록

## 보고
ISS ID · 등급 · 승인 여부 · 갱신할 산출물. 승인 전이면 무엇이 막고 있는지(영향 미기록 · L3 ADR 없음 · 승인자 없음)를 적는다.
