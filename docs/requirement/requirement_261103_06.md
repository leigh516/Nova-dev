# REQ-261103-06 · DB UUID 는 version 7

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-03 |
| 요청자 | jongyeolhan |
| 원문 | "db에 uuid를 사용할때 최신인 version7을 사용해주세요" |
| 상태 | 적용됨(상시 규칙) |
| 계획 | [ADR-003](../adr/ADR-003-uuid-v7-ids.md) · [backend.md §4](../conventions/backend.md) · plan_REQ_01 🆕 T01-2.08 |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261103-06-1 | DB 기본키는 UUIDv7 | `nova_common.ids.id_column()`(CHAR(36), 기본값 `new_id()`) · 샘플 · 서비스 템플릿이 사용 | T01-2.08 |
| REQ-261103-06-2 | RFC 9562 준수 · 시간순 | 버전 7 · 변형 RFC 4122 · 같은 ms 안 2만 개도 엄격 증가 · 생성 시각 추출(`uuid7_time`) — `test_ids.py` | T01-2.08 |
| REQ-261103-06-3 | 이벤트 ID 도 UUIDv7 | `Envelope.id` 기본값 `new_id()` | T01-2.08 |
| REQ-261103-06-4 | 다른 개체를 가리키는 칸도 같은 형식 | `ref_column()` — 개발 계정 사용자 · 테넌트 ID 도 v7 | T01-2.08 |

## 적용 · 결과
- ULID · 접두어 ID(`IT-…`) 폐기 → `new_id()` = UUIDv7 소문자 36자
- 검증: `packages/common-py/tests/test_ids.py` 5건 · 전체 `python nova.py test` 통과
