# 권한 대장

> 생성 파일 — `uv run python scripts/ledgers.py` 가 코드에서 파생한다(ADR-004). 직접 고치지 않는다 — 원천(코드 · 선언)을 고친다.

권한키 `<모듈>.<행위>` — 모듈 = services.json `perm`(없으면 서비스 이름), 행위 = HTTP 메서드(GET=read · POST=create · PUT/PATCH=update · DELETE=delete) 또는 rbac.json `overrides`.
역할 정본: [`services/gateway/gateway/rbac.json`](../../services/gateway/gateway/rbac.json) — 역할은 여기 먼저 등재한다. AI 자동화도 같은 권한 검사를 받는다(STD-AX-001).

## 역할

| 역할 | 이름 | 부여 |
|---|---|---|
| guest | 비로그인 | sample.read |
| user | 일반 사용자 | sample.read, sample.create, sample.update |
| manager | 관리책임자 | sample.*, ops.read |
| admin | 관리자 | * |

## 권한

| 권한키 | 설명 | 보유 역할 | 쓰는 API |
|---|---|---|---|
| ops.read | ops 조회 | manager, admin | 게이트웨이 운영 API |
| sample.create | sample 등록 | user, manager, admin | POST /sample/items |
| sample.delete | sample 삭제 | manager, admin | DELETE /sample/items/{item_id} |
| sample.read | sample 조회 | guest, user, manager, admin | GET /sample/items, GET /sample/items/{item_id} |
| sample.update | sample 수정 | user, manager, admin | PATCH /sample/items/{item_id}, POST /sample/items/{item_id}/archive, POST /sample/items/{item_id}/restore |
