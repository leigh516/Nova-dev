"""격리(parked) 아웃박스 행 재처리 명령 — 운영자가 셸(`kubectl exec`)에서 쓴다(R8 · REQ-261104-11-3).

    python -m nova_common.outbox_admin <서비스> list [--limit N]          # 격리 행 목록(원인 last_error 포함). parked 는 같은 뜻
    python -m nova_common.outbox_admin <서비스> requeue --id N [N …]      # 고른 행만 해제
    python -m nova_common.outbox_admin <서비스> requeue --all             # 전부 해제
    python nova.py parked <서비스> list | requeue …                     # 같은 명령(nova.py 연결)

HTTP 내부 API 가 아니라 명령인 이유: NetworkPolicy 가 네임스페이스 단위라 /internal 쓰기 API 를 열면 같은 네임스페이스의
아무 파드나 부를 수 있다. 명령은 exec 권한이 있는 사람만 쓴다(plan_REQ_03 §2). 서비스는 catalog 의 `<pkg>.main:svc` 로
열어 서비스와 같은 DB 설정(DATABASE_URL_<SVC> → DATABASE_URL → sqlite:///./data/<svc>.db)을 쓴다. 스키마는 만들지 않는다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

USAGE = __doc__.split("\n\n", 2)[1]

EXIT_USAGE = 2  # 잘못 쓴 명령 · 없는 서비스(argparse 와 같은 코드)


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python nova.py parked", description=USAGE,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("service", help="서비스 이름(services.json)")
    ap.add_argument("--root", default=".", help="저장소 루트(services/<서비스> 를 찾을 곳)")
    sub = ap.add_subparsers(dest="action", required=True, metavar="list | requeue")
    ls = sub.add_parser("list", aliases=["parked"], help="격리 행 목록")
    ls.add_argument("--limit", type=int, default=100, help="최대 행 수(기본 100)")
    rq = sub.add_parser("requeue", help="격리 해제(attempts 0 · last_error 보존) — --id 또는 --all 중 하나가 꼭 필요")
    which = rq.add_mutually_exclusive_group(required=True)
    which.add_argument("--id", dest="ids", type=int, nargs="+", action="extend", metavar="N", help="해제할 outbox.id")
    which.add_argument("--all", action="store_true", help="격리 행 전부")
    return ap


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001 — 재설정이 안 되는 스트림(테스트 캡처 등)은 그대로 쓴다
            pass
    a = _parser().parse_args(argv)  # 잘못 쓰면 argparse 가 종료 코드 2 로 끝낸다
    import logging

    logging.getLogger("alembic").setLevel(logging.WARNING)  # 명령 출력은 요약만 — 서비스 모듈을 열 때의 alembic 로그는 숨긴다
    from sqlalchemy import inspect

    from .migrate import _open_service

    try:
        svc = _open_service(a.service, Path(a.root).resolve())
    except SystemExit as e:
        print(e, file=sys.stderr)
        return EXIT_USAGE
    table = svc.Outbox.__table__.name
    if not inspect(svc.db.engine).has_table(table):
        print(f"✗ {a.service}: {table} 표가 없습니다({svc.db.url}) — 서비스를 한 번 기동하거나 python nova.py migrate {a.service} up",
              file=sys.stderr)
        return 1
    if a.action in ("list", "parked"):
        rows = svc.parked_rows(limit=a.limit)
        print(f"{a.service}: 격리 행 {len(rows)}건{' (상한 ' + str(a.limit) + ')' if len(rows) >= a.limit else ''} — {svc.db.url}")
        for r in rows:
            print(f"  id={r['id']} topic={r['topic']} key={r['key']} attempts={r['attempts']} created_at={r['created_at']}")
            print(f"      원인: {r['last_error'] or '(기록 없음)'}")
        if rows:
            print(f"  다음: 원인을 고친 뒤 python nova.py parked {a.service} requeue --id N … (또는 --all)")
        return 0
    n = svc.requeue_parked(None if a.all else a.ids)
    print(f"✓ {a.service}: 격리 해제 {n}건 — 서비스 릴레이가 다음 주기에 다시 발행합니다. 같은 원인이면 한계에서 다시 격리됩니다")
    return 0


if __name__ == "__main__":
    # `python -m` 로 돌면 이 파일이 __main__ 으로 한 번 더 적재된다 — 서비스가 쓰는 nova_common 과 같은 모듈에서 부른다
    from nova_common.outbox_admin import main as _main

    raise SystemExit(_main())
