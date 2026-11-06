"""로컬 MariaDB 에 서비스별 스키마 · 계정을 만들고 .env 에 접속 정보를 쓴다 (재실행 안전).

    NOVA_DB_ROOT_PASSWORD=... uv run python scripts/local_db_setup.py [--host 127.0.0.1] [--port 3306] [--prefix <slug>]

- 서비스마다 자기 스키마 `<prefix>_<svc>` + 전용 계정(자기 스키마에만 권한) — "서비스는 자기 DB만"(backend.md §2)
- prefix 기본값 = nova.project.json 의 slug
- 대표 DB `<prefix>` 도 만든다(비어 있음, 이름 예약용)
- root 비밀번호는 환경 변수로만 받는다(파일·로그에 남기지 않음). 서비스 계정 비밀번호는 매번 새로 생성해 .env(커밋 안 됨)에 쓴다
- 다른 프로젝트 DB 는 건드리지 않는다(<prefix> 로 시작하는 것만 생성·권한 부여)
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from pathlib import Path

import pymysql

from nova_common import catalog

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import project  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB_SERVICES = catalog.db_services()  # 서비스 목록 단일 원천(nova_common/services.json)
ENV_BEGIN, ENV_END = "# >>> local mariadb (scripts/local_db_setup.py)", "# <<< local mariadb"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=3306)
    ap.add_argument("--prefix", default=project()["slug"].replace("-", "_"))
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", a.prefix):
        print("prefix 는 소문자·숫자·밑줄만", file=sys.stderr)
        return 2
    pw = os.environ.get("NOVA_DB_ROOT_PASSWORD")
    if not pw:
        print("NOVA_DB_ROOT_PASSWORD 환경 변수가 필요합니다", file=sys.stderr)
        return 2
    conn = pymysql.connect(host=a.host, port=a.port, user="root", password=pw, autocommit=True, connect_timeout=5)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{a.prefix}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    lines = [ENV_BEGIN]
    for svc in DB_SERVICES:
        name = f"{a.prefix}_{svc.replace('-', '_')}"
        user_pw = secrets.token_urlsafe(18)
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        for host in ("localhost", "127.0.0.1"):
            cur.execute(f"CREATE USER IF NOT EXISTS '{name}'@'{host}' IDENTIFIED BY %s", (user_pw,))
            cur.execute(f"ALTER USER '{name}'@'{host}' IDENTIFIED BY %s", (user_pw,))
            cur.execute(f"GRANT ALL PRIVILEGES ON `{name}`.* TO '{name}'@'{host}'")
        env = "DATABASE_URL_" + svc.upper().replace("-", "_")
        lines.append(f"{env}=mysql+pymysql://{name}:{user_pw}@{a.host}:{a.port}/{name}?charset=utf8mb4")
        print(f"✓ {name} (계정 {name})")
    cur.execute("FLUSH PRIVILEGES")
    lines.append(ENV_END)
    env_path = ROOT / ".env"
    old = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    kept = re.sub(rf"{re.escape(ENV_BEGIN)}.*?{re.escape(ENV_END)}\n?", "", old, flags=re.S).rstrip()
    env_path.write_text((kept + "\n\n" if kept else "") + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"✓ 접속 정보 → {env_path.relative_to(ROOT)} (git 제외 파일)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
