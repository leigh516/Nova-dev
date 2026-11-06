import os
import sys
from pathlib import Path

# 서비스 폴더를 import 경로에 — 어떤 실행 방식(uv run pytest · python -m pytest · 저장소 루트)에서도 같은 결과
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL_SAMPLE", "sqlite://")
