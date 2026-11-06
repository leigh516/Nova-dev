# 규칙(포트 구현)

`<서비스 패키지>.py` 파일에서 코어 포트를 구현한다:

```python
from nova_common.packs import implement

@implement("sample.normalize_name")
def normalize(name: str) -> str:
    return " ".join(name.split())
```
