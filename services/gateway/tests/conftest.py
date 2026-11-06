import os
import sys
from pathlib import Path

# 서비스 폴더를 import 경로에 — 어떤 실행 방식(uv run pytest · python -m pytest · 저장소 루트)에서도 같은 결과
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("GW_FLAG_TTL", "30")
os.environ.setdefault("GW_MONITOR_CACHE", "0")
os.environ.setdefault("NOVA_SKIP_LIFESPAN", "1")
