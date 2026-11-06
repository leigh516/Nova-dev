# outbound/db-sql — 출고

> 나가는 것: `schema.sql`(SPEC 데이터 모델 → MariaDB DDL 초안, 기본키 UUIDv7 `CHAR(36)`) · 짝으로 `rollback.sql` · `analysis_db-sql.md`(입고 db-sql 분석 발견 — 우리 모델과의 차이는 `/intake` 가 발견 · 부족 항목으로 기록)

- 만드는 법: 자동 — `spec.json` `data_model` 에서. 🔴 실행 DB 에 적용하는 것은 사람 승인 후 건별로
- 🔴 정본이 아니다 — 고칠 일이 있으면 정본(`docs/product/`)을 고치고 `uv run python scripts/warehouse.py out`
- 입고 쪽 같은 이름 [inbound/db-sql](../../inbound/db-sql/README.md) 은 **받은 것**, 여기는 **우리가 만든 것** — 방향이 반대다

관련: [출고 규칙](../README.md)
