import os
import sys
from pathlib import Path

# 서비스 폴더를 import 경로에 — 어떤 실행 방식에서도 같은 결과
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL___ENV__", "sqlite://")
