# 서비스 템플릿

`python nova.py new-service <이름> --group <그룹> --scope <범위> [--title <한국어 이름>] [--package <패키지>]` 가 이 폴더를 `services/<이름>/` 으로 복사하고 자리표시자를 바꾼다. 직접 복사하지 않는다.

| 자리표시자 | 바뀌는 값 | 예 |
|---|---|---|
| `__SERVICE__` | 서비스 이름 | `order-hub` |
| `__PKG__` | 파이썬 패키지(폴더 이름도) | `order_hub` |
| `__TITLE__` | 사람이 읽는 이름 | `주문`(`--title` 을 빼면 서비스 이름) |
| `__DOMAIN__` | 토픽 · 권한 도메인 | `order_hub` |
| `__ENV__` | 환경 변수 접미어(대문자 · 밑줄) | `ORDER_HUB` |

구조 규약: [docs/conventions/backend.md §1](../../docs/conventions/backend.md)
