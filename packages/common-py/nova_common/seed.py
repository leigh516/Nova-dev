"""공통 시드(seed/seed.json) 로더 — 목업과 같은 데이터로 모든 서비스를 채운다(통합 환경 규칙)."""
import json
import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_seed() -> dict:
    env = os.getenv("SEED_PATH")
    candidates = [Path(env)] if env else []
    here = Path(__file__).resolve()
    candidates += [p / "seed" / "seed.json" for p in here.parents]
    candidates.append(Path("/app/seed/seed.json"))
    for c in candidates:
        if c.is_file():
            return json.loads(c.read_text(encoding="utf-8"))
    return {}
