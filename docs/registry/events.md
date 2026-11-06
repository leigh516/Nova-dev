# 이벤트 대장

> 생성 파일 — `uv run python scripts/ledgers.py` 가 코드에서 파생한다(ADR-004). 직접 고치지 않는다 — 원천(코드 · 선언)을 고친다.

이벤트 이름 `<도메인>.<개체>.<과거형>` — 일어난 사실. **카탈로그(`infra/k3s/base/kafka-topics.txt`) 등재 없는 발행 금지**. 페이로드는 추가만(새 필드는 기본값) — 필드 삭제 · 타입 변경 · 의미 변경은 새 토픽(봉투 `version` 도 올린다).

| 이벤트 | 발행 | 구독 | 페이로드 | 파티션 | 보존(일) |
|---|---|---|---|---|---|
| sample.item.created | sample | sample | id, name | 3 | 7 |
| sample.item.updated | sample | — | id, name | 3 | 7 |
| sample.item.archived | sample | sample | id | 3 | 7 |
| sample.item.restored | sample | sample | id | 3 | 7 |
| sample.item.deleted | sample | — | id | 3 | 7 |
| platform.feature.changed | —(아직 없음) | gateway | — | 1 | 7 |
| platform.rbac.changed | —(아직 없음) | gateway | — | 1 | 7 |
