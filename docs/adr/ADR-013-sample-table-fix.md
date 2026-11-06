# ADR-013 · 샘플 표 구조 정정 — 활동 UUIDv7 기본키 · 테넌트 · recorded_at · 참조 칸

| 항목 | 내용 |
|---|---|
| 일자 | 2026-11-05 |
| 상태 | 채택(사용자 2026-11-05 "진행해주세요") |
| 대체 | 없음 |
| 요구 | [REQ-261104-12](../requirement/requirement_261104_12.md) P2 · P5 · [plan_REQ_04](../plans/plan_REQ_04.md) 2단계 |
| 원천 | [REQ-261104-12](../requirement/requirement_261104_12.md) P2 · P5 — task T04-1.01(ADR 본문 초안) · 사용자 채택 2026-11-05 |
| 연결 | 근거 [ADR-003](ADR-003-uuid-v7-ids.md)(UUIDv7) · [ADR-011](ADR-011-migrations-alembic.md)(마이그레이션) · 실행 [plan_REQ_04](../plans/plan_REQ_04.md) 2단계 · [tasks_REQ_04](../plans/tasks/tasks_REQ_04.md) |

## 배경
샘플 서비스(`services/sample`)와 서비스 템플릿(`services/_template`)은 복제본이 그대로 베끼는 견본이다. 그런데 `item_activity` 가 정수 일련번호 기본키 · 테넌트 칸 없음 · 예약어에 가까운 `at` 칸을 쓰고, `created_by` · `updated_by` 가 일반 문자열 칸이어서 Nova 규칙(ADR-003 UUIDv7 · STD 멀티테넌시 · backend.md 참조 칸)과 어긋난다. 견본이 틀리면 모든 새 프로젝트가 같은 틀림을 물려받는다.

## 결정
- `item_activity.id` 를 `id_column()`(UUIDv7)로, `tenant_column` 을 더하고 소비자가 봉투의 tenant 를 저장한다. 상세 조회는 `tenant_filter` 로 거른다
- `at` → `recorded_at`(API 응답 키 포함), 정렬은 `(recorded_at, id)`
- `created_by` · `updated_by` 를 `ref_column(nullable=True, index=False)` 로(샘플 · 템플릿 모두). 명명 규약 `column_ref`(`_id` · `_by` → VARCHAR(36))
- 표 변경은 **마이그레이션**(ADR-011 서비스 분기 `s000N`)으로 — 옛 DB 에서 올라가는 경로를 둔다
- 개발 DB: 이 PC 의 MariaDB 에 Nova 스키마(`nova` · `nova_sample`)가 없음을 2026-11-05 확인 — 지우고 다시 만들 표가 없다. 메모리 · SQLite 는 재기동으로 충분

## 검토한 대안
| 대안 | 장점 | 단점 | 버린 이유 |
|---|---|---|---|
| 그대로 두고 문서에 예외로 적기 | 비용 0 | 견본이 규칙을 어긴 채 복제된다 | 견본의 목적과 반대 |
| 표를 지우고 create_all 로 다시 만들기 | 단순 | 운영 데이터가 생긴 뒤에는 쓸 수 없는 방법을 견본이 가르친다 | 마이그레이션 체계(ADR-011)가 이미 있다 |

## 결과
- 좋아지는 것: 견본이 UUIDv7 · 테넌트 격리 · 참조 칸 규칙의 모범 예가 된다
- 감수하는 것: API 응답 키 `at` → `recorded_at` 변경(웹 · KMP 동시 반영), 기존 활동 행의 id 형식 변환
- 되돌리기: 마이그레이션 downgrade, 응답 키는 웹 · KMP 와 같은 커밋 묶음에서 되돌린다
- 이후 규칙: 새 서비스 표는 처음부터 이 형태(템플릿이 이미 반영)
