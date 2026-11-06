# ADR-011 · 마이그레이션 체계 — Alembic 플랫폼 · 서비스 분기

| 항목 | 내용 |
|---|---|
| 일자 | 2026-11-04 |
| 상태 | 채택 |
| 대체 | - |
| 요구 | [REQ-261104-11](../requirement/requirement_261104_11.md) R6 · 계획 [plan_REQ_03](../plans/plan_REQ_03.md) |

## 배경
- 서비스 DB 는 `Database.create_all` 로만 만들어진다(`nova_common/db.py`). 이미 있는 표에 칸을 더하지 못하므로, 표 구조를 바꾸면 개발자 PC 의 DB 가 깨지고 운영에서는 손으로 고쳐야 한다.
- 모든 DB 서비스가 같은 플랫폼 표(`outbox` · `processed_event`)를 가진다. 서비스마다 같은 칸 추가 마이그레이션을 복제하면 요구의 반목표("서비스마다 같은 코드 복제")를 어긴다.
- 제약 · 인덱스 이름 규칙이 없어 DB 마다 이름이 달라지고, 마이그레이션으로 지우거나 바꾸기 어렵다.

## 결정
- **Alembic 을 쓴다**(`uv add --package nova-common alembic` — 의존성 추가는 사용자 승인 2026-11-04).
- **두 분기**: 플랫폼 분기(`nova_common/migrations/versions` — 플랫폼 표)와 서비스 분기(`services/<svc>/migrations/versions` — 그 서비스 표). 실행기 `nova_common.migrate.upgrade` 가 두 분기의 heads 까지 올린다.
- **제약 이름 규칙** `db.NAMING_CONVENTION`(ix · uq · ck · fk · pk)을 `db.NovaBase` 의 MetaData 에 둔다 — 모든 서비스 Base 가 상속.
- **옛 DB**: 표는 있는데 `alembic_version` 이 없으면 baseline 으로 stamp 한 뒤 upgrade 한다(기존 행 보존).
- **migrations 폴더가 없는 서비스**(게이트웨이 메모리 DB)는 `create_all` 을 유지한다.
- 모든 마이그레이션은 downgrade 를 함께 쓴다. 명령 `python nova.py migrate <svc> new | up | status`.

## 검토한 대안
| 대안 | 장점 | 단점 | 버린 이유 |
|---|---|---|---|
| 자체 러너(SQL 파일 순번) | 의존성 없음 | autogenerate · downgrade · 분기를 직접 만들어야 함 | 만드는 비용 · 유지 비용이 크다 |
| `create_all` 유지 + 문서 | 아무것도 안 바꿈 | 칸 추가 · 이름 변경을 못 함 | P1 · D3 를 할 수 없다 |
| 서비스마다 독립 Alembic | 단순 | 플랫폼 표 변경을 서비스마다 복제 | 반목표 |

## 결과
- **좋아지는 것**: 플랫폼 표 변경이 마이그레이션 하나로 모든 서비스에 간다 · 제약 이름이 같다 · 되돌리기(downgrade)가 생긴다
- **감수하는 것**: 의존성 1개(+ Mako) · 새 서비스는 migrations 폴더를 갖고 시작한다(템플릿이 만든다)
- **이후 규칙**: 표 · 칸을 바꾸면 마이그레이션을 쓴다(`create_all` 로 우회하지 않는다) · 운영 마이그레이션은 사용자 확인 뒤
