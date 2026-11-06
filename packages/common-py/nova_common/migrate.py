"""마이그레이션 실행기 — Alembic 플랫폼 · 서비스 두 분기(ADR-011 · REQ-261104-11-1).

- 플랫폼 분기(`nova_common/migrations/versions`, 이름표 `platform`, 리비전 `p0001`…): 모든 DB 서비스에 들어가는 outbox · processed_event.
  플랫폼 표 변경은 여기 하나만 쓰면 모든 서비스에 간다(서비스마다 복제하지 않는다).
- 서비스 분기(`services/<svc>/migrations/versions`, 이름표 `service`, 리비전 `s0001`…): 그 서비스 표만.
  리비전 ID 는 한 DB(플랫폼 + 그 서비스) 안에서만 겹치지 않으면 되므로 서비스마다 같은 `s0001` 을 쓴다.
- 옛 DB: 표는 있는데 alembic_version 이 없으면(create_all 로 만든 DB) 각 분기의 첫 리비전(baseline)으로 stamp 한 뒤 heads 까지 올린다.
- 연결은 호출한 쪽이 넘긴다(env.py 의 run_env 가 config.attributes 에서 꺼낸다) — `alembic` 명령을 직접 쓰지 않고
  `python nova.py migrate` 또는 Service.init_db 로만 돌린다.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

PLATFORM_DIR = Path(__file__).resolve().parent / "migrations"
PLATFORM_BRANCH = "platform"
SERVICE_BRANCH = "service"
VERSION_TABLE = "alembic_version"

log = logging.getLogger("nova.migrate")


def run_env() -> None:
    """env.py 본문 — 플랫폼 · 서비스 env.py 가 이것만 부른다(설정을 한 곳에 둔다)."""
    from alembic import context as actx

    cfg = actx.config
    conn: Connection | None = cfg.attributes.get("connection")
    if conn is None or actx.is_offline_mode():
        raise RuntimeError("마이그레이션은 nova_common.migrate(python nova.py migrate · 서비스 기동)로만 돌립니다 — alembic 명령을 직접 쓰지 않습니다")
    skip = set(cfg.attributes.get("exclude_tables") or ())

    def include_object(obj, name, type_, reflected, compare_to):  # noqa: ANN001, ARG001
        """서비스 분기 자동 생성에서 플랫폼 표(outbox · processed_event)는 뺀다 — 플랫폼 변경은 플랫폼 분기(p000N)에만 쓴다."""
        table = name if type_ == "table" else getattr(getattr(obj, "table", None), "name", None)
        return table not in skip

    actx.configure(
        connection=conn,
        target_metadata=cfg.attributes.get("target_metadata"),
        include_object=include_object,
        version_table=VERSION_TABLE,
        # SQLite 는 ALTER 가 좁아 칸 변경을 표 복사(batch)로 한다 — MariaDB 는 그대로 ALTER
        render_as_batch=conn.dialect.name == "sqlite",
        compare_type=True,
    )
    with actx.begin_transaction():
        actx.run_migrations()


def resolve_dir(service_dir: Path | str | None) -> Path | None:
    """서비스 폴더(services/<svc>) 또는 그 migrations 폴더 → migrations 폴더. 없으면 None."""
    if service_dir is None:
        return None
    p = Path(service_dir)
    if not (p / "versions").is_dir() and (p / "migrations" / "versions").is_dir():
        p = p / "migrations"
    if not (p / "versions").is_dir():
        raise FileNotFoundError(f"마이그레이션 폴더가 없습니다(versions/ 필요): {p}")
    return p


def _config(base, mdir: Path | None, connection: Connection | None = None, *, script_location: Path | None = None) -> Config:
    """파일(alembic.ini) 없이 만든 설정. env.py 는 서비스 것(있으면) → 플랫폼 것 순으로 쓴다."""
    cfg = Config()
    loc = script_location or (mdir if mdir is not None and (mdir / "env.py").exists() else PLATFORM_DIR)
    locations = [PLATFORM_DIR / "versions"] + ([mdir / "versions"] if mdir is not None else [])
    cfg.set_main_option("path_separator", "os")  # 경로 구분자 — 공백 · 드라이브 문자가 든 경로도 안전하게
    cfg.set_main_option("script_location", str(loc).replace("%", "%%"))
    cfg.set_main_option("version_locations", os.pathsep.join(str(p).replace("%", "%%") for p in locations))
    cfg.attributes["connection"] = connection
    cfg.attributes["target_metadata"] = base.metadata if base is not None else None
    return cfg


def _is_legacy(conn: Connection, base) -> bool:
    """create_all 로 만든 옛 DB — alembic_version 은 없고 이 서비스 표(플랫폼 표 포함)가 하나라도 있다."""
    tables = set(inspect(conn).get_table_names())
    if VERSION_TABLE in tables:
        return False
    known = set(base.metadata.tables) if base is not None else {"outbox", "processed_event"}
    return bool(tables & known)


def platform_head() -> str:
    """플랫폼 분기의 최신 리비전 — 서비스 · 저장소 테스트가 리비전 이름을 손으로 적지 않게(플랫폼 리비전을 더할 때 세 곳을 고치던 문제)."""
    cfg = Config()
    cfg.set_main_option("script_location", str(PLATFORM_DIR))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"플랫폼 분기의 최신 리비전이 하나가 아니다: {heads}")
    return heads[0]


def _baselines(cfg: Config) -> list[str]:
    """각 분기의 첫 리비전 — 옛 DB 는 이 모양(create_all 시절 모델)이라고 보고 stamp 한다."""
    return sorted(ScriptDirectory.from_config(cfg).get_bases())


MIGRATE_LOCK_TIMEOUT = 120  # 초 — 다른 복제본의 마이그레이션을 기다리는 상한(NOVA_MIGRATE_LOCK_TIMEOUT 로 덮어쓴다)
_LOCKING_DIALECTS = {"mysql", "mariadb"}  # GET_LOCK 을 쓰는 방언. SQLite 는 한 프로세스 · 한 파일이라 잠그지 않는다


@contextmanager
def migration_lock(conn, service: str, timeout: float | None = None) -> Iterator[None]:
    """복제본 여럿이 동시에 기동해도 마이그레이션(DDL)이 한 번에 하나만 돌게 한다(T07-1.01 · review_261105_02 B1).

    MariaDB · MySQL: 같은 연결에서 `GET_LOCK('<서비스>:migrate', 초)` → 안의 일 → `RELEASE_LOCK`. 뒤에 온 복제본은
    앞 복제본이 끝날 때까지 기다렸다가, 이미 heads 인 DB 를 보고 아무것도 하지 않는다.
    시간 안에 못 얻으면(0 = 시간 초과, NULL = 오류) 마이그레이션을 하지 않고 RuntimeError → 기동 실패(재시작으로 다시 시도).
    SQLite 는 잠금 SQL 을 내지 않는다."""
    if conn.dialect.name not in _LOCKING_DIALECTS:
        yield
        return
    wait = int(timeout if timeout is not None else float(os.getenv("NOVA_MIGRATE_LOCK_TIMEOUT", str(MIGRATE_LOCK_TIMEOUT))))
    name = f"{service}:migrate"  # 잠금 이름은 64자 이하(MariaDB) — 서비스 이름은 카탈로그에서 짧게 정한다
    got = conn.execute(text("SELECT GET_LOCK(:name, :timeout)"), {"name": name, "timeout": wait}).scalar()
    if got != 1:
        why = "시간 초과" if got == 0 else "잠금 오류(NULL)"
        log.error("%s: 마이그레이션 잠금 '%s' 을 %s초 안에 얻지 못했습니다(%s) — 다른 복제본이 마이그레이션 중이거나 멈췄습니다. "
                  "기동을 멈춥니다(재시작 때 다시 시도)", service, name, wait, why)
        raise RuntimeError(f"{service}: 마이그레이션 잠금 '{name}' 을 {wait}초 안에 얻지 못했습니다({why}) — 기동을 멈춥니다")
    log.info("%s: 마이그레이션 잠금 '%s' 을 얻었습니다", service, name)
    try:
        yield
    finally:
        try:
            conn.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})
        except Exception:  # noqa: BLE001 — 연결이 끊겼으면 잠금은 세션과 함께 풀린다. 원래 예외를 가리지 않게 기록만
            log.warning("%s: 마이그레이션 잠금 '%s' 해제 실패 — 연결 종료와 함께 풀립니다", service, name, exc_info=True)


def upgrade(db, base, service_dir: Path | str | None = None) -> None:
    """플랫폼 분기 + 서비스 분기를 heads 까지 올린다. 옛 create_all DB 는 baseline stamp 뒤 올린다(행 보존).

    db: nova_common.db.Database · base: 서비스 Base(NovaBase) · service_dir: 서비스 migrations 폴더(None 이면 플랫폼 분기만).
    MariaDB 에서는 `migration_lock` 안에서 돈다 — 복제본이 동시에 기동해도 한 번만."""
    mdir = resolve_dir(service_dir)
    with db.engine.begin() as conn, migration_lock(conn, db.service):
        cfg = _config(base, mdir, conn)
        if _is_legacy(conn, base):
            bases = _baselines(cfg)
            log.warning("%s: alembic_version 이 없는 옛 DB — baseline %s 로 stamp 한 뒤 올립니다", db.service, ", ".join(bases))
            command.stamp(cfg, bases)
        command.upgrade(cfg, "heads")


def downgrade(db, base, service_dir: Path | str | None, target: str) -> None:
    """target(예: `service@-1` · `platform@base`)까지 내린다 — 되돌리기 경로. 운영에서는 사용자 확인 뒤에만."""
    mdir = resolve_dir(service_dir)
    with db.engine.begin() as conn:
        command.downgrade(_config(base, mdir, conn), target)


def status(db, base, service_dir: Path | str | None = None) -> dict[str, Any]:
    """{'current': DB 에 적힌 리비전, 'heads': 코드의 최신 리비전, 'up_to_date': 같은가, 'legacy': stamp 대상인가}"""
    mdir = resolve_dir(service_dir)
    heads = sorted(ScriptDirectory.from_config(_config(base, mdir)).get_heads())
    with db.engine.connect() as conn:
        legacy = _is_legacy(conn, base)
        current = sorted(MigrationContext.configure(conn, opts={"version_table": VERSION_TABLE}).get_current_heads())
    return {"current": current, "heads": heads, "up_to_date": current == heads, "legacy": legacy}


def drift(db, base) -> list:
    """DB 스키마와 모델(base.metadata)의 차이(Alembic compare_metadata). 비면 마이그레이션이 모델을 따라잡은 것.

    테스트(서비스 · 템플릿)와 `migrate status` 가 '모델만 고치고 마이그레이션을 안 쓴' 것을 잡는 데 쓴다."""
    from alembic.autogenerate import compare_metadata

    with db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), base.metadata)
    return [d for d in diff if not (isinstance(d, tuple) and d[0] == "remove_table" and d[1].name == VERSION_TABLE)]


def new_revision(db, base, service_dir: Path | str, message: str, *, autogenerate: bool = True) -> Path:
    """서비스 분기에 새 리비전 파일을 만든다(`s<NNNN>`, 파일 `<NNNN>_<설명>.py`). 반환: 만든 파일.

    autogenerate 는 db 를 heads 까지 올린 뒤 모델(base)과 비교한다 — 보통 메모리 DB 를 넘긴다.
    리비전 파일 틀(script.py.mako)은 플랫폼 폴더 하나만 둔다(서비스마다 복제하지 않는다)."""
    mdir = resolve_dir(service_dir)
    assert mdir is not None
    if autogenerate:
        upgrade(db, base, mdir)
    script = ScriptDirectory.from_config(_config(base, mdir))
    here = (mdir / "versions").resolve()
    mine = [r for r in script.walk_revisions() if Path(r.path).resolve().parent == here]
    n = len(mine) + 1
    rev_id = f"s{n:04d}"
    with db.engine.begin() as conn:
        cfg = _config(base, mdir, conn, script_location=PLATFORM_DIR)
        cfg.set_main_option("file_template", f"{n:04d}_%%(slug)s")
        cfg.attributes["exclude_tables"] = {"outbox", "processed_event"}
        kw: dict[str, Any] = {"head": f"{SERVICE_BRANCH}@head"} if mine else {"head": "base", "branch_label": SERVICE_BRANCH}
        made = command.revision(cfg, message=message, autogenerate=autogenerate, rev_id=rev_id,
                                version_path=str(mdir / "versions"), **kw)
    scripts = made if isinstance(made, list) else [made]
    return Path(scripts[0].path)


# ---------------------------------------------------------------- 명령 (python nova.py migrate …)
USAGE = """마이그레이션 명령 — python nova.py migrate <서비스> <동작>  (python -m nova_common.migrate 와 같다)

  status                 DB 에 적힌 리비전 · 코드의 최신 리비전 · 모델과 마이그레이션 차이
  up                     플랫폼 + 서비스 분기를 heads 까지 올린다(옛 create_all DB 는 baseline stamp 뒤)
  new "<설명>" [--empty]  모델과 비교해 서비스 분기 다음 리비전(s000N)을 만든다 — 차이가 없으면 만들지 않는다(--empty 는 데이터 이전용 빈 리비전)

  공통 옵션 --root <저장소>   services/<서비스> 를 찾을 곳(기본: 현재 폴더)
  DB 는 서비스와 같은 규칙(DATABASE_URL_<SVC> → DATABASE_URL → sqlite:///./data/<svc>.db). new 는 메모리 DB 로 비교하고 실제 DB 를 건드리지 않는다.
  운영 DB 의 up 은 사용자 확인 뒤에만(ADR-011)."""


def _open_service(name: str, root: Path):
    """services/<name> 의 `<pkg>.main:svc` — 서비스와 같은 Base · DB 설정 · migrations 폴더를 쓴다."""
    import importlib
    import sys

    from . import catalog

    try:
        spec = catalog.get(name)
    except Exception as e:  # noqa: BLE001 — 카탈로그 조회 실패 사유를 그대로 보여 준다
        raise SystemExit(f"✗ 서비스 카탈로그에 없는 서비스입니다: {name} ({e})") from e
    sdir = root / "services" / name
    if not sdir.is_dir():
        raise SystemExit(f"✗ 서비스 폴더가 없습니다: {sdir}")
    sys.path.insert(0, str(sdir))
    return importlib.import_module(f"{spec.package}.main").svc


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="python nova.py migrate", description=USAGE, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("service")
    ap.add_argument("action", choices=["status", "up", "new"])
    ap.add_argument("message", nargs="?")
    ap.add_argument("--empty", action="store_true", help="차이가 없어도 빈 리비전을 만든다(데이터 이전용)")
    ap.add_argument("--root", default=".", help="저장소 루트(services/<서비스> 를 찾을 곳)")
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001 — 재설정이 안 되는 스트림(테스트 캡처 등)은 그대로 쓴다
            pass
    logging.getLogger("alembic").setLevel(logging.WARNING)  # 명령 출력은 아래 요약만 — alembic 단계 로그는 숨긴다
    try:
        svc = _open_service(a.service, Path(a.root).resolve())
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    if svc.migrations_dir is None:
        print(f"✗ {a.service}: migrations 폴더가 없는 서비스입니다 — 예전대로 create_all 로 만든다(상태 없는 메모리 DB). 표를 가지려면 services/{a.service}/migrations 를 만드세요")
        return 0 if a.action == "status" else 1
    from .db import Database

    if a.action == "status":
        st = status(svc.db, svc.Base, svc.migrations_dir)
        print(f"{a.service}: DB {svc.db.url}")
        if st["up_to_date"]:
            print(f"  ✓ 최신 — {', '.join(st['current'])}")
        else:
            print(f"  · 올릴 리비전이 있습니다 — DB [{', '.join(st['current']) or '없음'}] → 코드 [{', '.join(st['heads'])}]   python nova.py migrate {a.service} up")
        if st["legacy"]:
            print("  · alembic_version 이 없는 옛 DB(create_all) — up 이 baseline 으로 stamp 한 뒤 올린다(행 보존)")
        mem = Database(f"{a.service}-drift", "sqlite://")
        upgrade(mem, svc.Base, svc.migrations_dir)
        d = drift(mem, svc.Base)
        print("  ✓ 모델과 마이그레이션 차이 없음" if not d else f"  ✗ 모델과 마이그레이션 차이 {len(d)}건 — python nova.py migrate {a.service} new \"<설명>\"")
        for x in d:
            print(f"    - {x}")
        return 0
    if a.action == "up":
        upgrade(svc.db, svc.Base, svc.migrations_dir)
        st = status(svc.db, svc.Base, svc.migrations_dir)
        print(f"✓ {a.service}: {', '.join(st['current'])} 까지 올렸습니다 ({svc.db.url})")
        return 0
    if not a.message:
        print("✗ 설명이 필요합니다 — python nova.py migrate <서비스> new \"<설명>\"", file=sys.stderr)
        return 2
    mem = Database(f"{a.service}-autogen", "sqlite://")
    upgrade(mem, svc.Base, svc.migrations_dir)
    if not drift(mem, svc.Base) and not a.empty:
        print(f"· {a.service}: 모델과 마이그레이션 차이가 없습니다 — 빈 리비전을 만들지 않습니다(데이터 이전이면 --empty)")
        return 1
    path = new_revision(mem, svc.Base, svc.migrations_dir, a.message, autogenerate=not a.empty)
    print(f"✓ 만들었습니다: {path}")
    print("  다음: 내용 확인(downgrade 포함 · 칸 comment=) → 서비스 tests(마이그레이션 = 모델 검사) → registry sync")
    return 0


if __name__ == "__main__":
    # `python -m` 로 돌면 이 파일이 __main__ 으로 한 번 더 적재된다 — env.py 가 부르는 nova_common.migrate 와 같은 모듈을 쓰도록 정본에서 부른다
    from nova_common.migrate import main as _main

    raise SystemExit(_main())
