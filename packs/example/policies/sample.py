"""예시 팩 — 샘플 서비스 포트 구현. 코어(services/sample)는 이 파일을 모른다(팩 → 코어 단방향)."""
from nova_common.packs import implement


@implement("sample.normalize_name")
def normalize_name(name: str) -> str:
    """이 업종 규칙: 앞뒤 공백을 지우고, 안쪽 연속 공백은 하나로."""
    return " ".join(name.split())
