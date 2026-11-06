# 이벤트 스키마

- 봉투: [`envelope.avsc`](envelope.avsc) — `nova_common.events.Envelope` 와 같은 필드. `data` 는 토픽별 스키마(JSON 직렬화)
- 토픽별 스키마: `<토픽>.avsc` (예: `sample.item.created.avsc`) — **선택**. 지금은 봉투(`envelope.avsc`)만 있고, 토픽별 본문은 이벤트 대장이 `emit` 의 dict 키로 대신 보인다(검사 없음)
- 호환성: **BACKWARD** — 새 필드는 반드시 `default` 를 둔다. 필드 삭제 · 타입 변경 · 의미 변경은 새 토픽으로 낸다(봉투 `version` 도 올린다)
- 직렬화: 현재 JSON 봉투. Schema Registry(Avro) 연동은 후속
- 규약: [docs/conventions/backend.md §3](../../../docs/conventions/backend.md)
