"""서비스 카탈로그(services.json) — 단일 원천 검사: 저장소의 services/ 디렉터리·패키지와 일치해야 한다."""
from pathlib import Path

from nova_common import catalog

ROOT = Path(__file__).resolve().parents[3]


def test_catalog_matches_service_directories():
    on_disk = {p.name for p in (ROOT / "services").iterdir() if p.is_dir() and not p.name.startswith((".", "_"))}
    assert set(catalog.names()) == on_disk
    for s in catalog.services():
        assert (ROOT / "services" / s.name / s.package / "main.py").exists(), s.name


def test_catalog_shape():
    assert catalog.names()[-1] == catalog.gateway()  # 게이트웨이는 마지막에 기동
    assert catalog.gateway() not in catalog.backends()
    ports = [s.local_port for s in catalog.services()]
    assert len(set(ports)) == len(ports)
    scopes = [s.scope for s in catalog.services()]
    assert len(set(scopes)) == len(scopes)
    assert all(s.db == (s.name in catalog.db_services()) for s in catalog.services())
    assert {g["key"] for g in catalog.groups()} >= {s.group for s in catalog.services()}


def test_package_override_and_db_name():
    """파이썬 패키지 이름은 서비스 이름에서 오되, 표준 모듈과 겹치면 services.json 의 package 로 바꾼다(plan_REQ_21 §14.2).
    DB 스키마·환경 변수 이름은 항상 서비스 이름 기준."""
    import sys

    s = catalog.ServiceSpec(name="platform", group="platform", desc="", scope="PLATFORM", local_port=1, package_name="platform_svc")
    assert s.package == "platform_svc" and s.db_name == "platform" and s.env == "PLATFORM"
    d = catalog.ServiceSpec(name="order-svc", group="business", desc="", scope="ORDER", local_port=2)
    assert d.package == "order_svc" and d.db_name == "order_svc"
    stdlib = set(sys.stdlib_module_names)
    assert all(x.package not in stdlib for x in catalog.services()), "표준 모듈과 같은 패키지 이름"
    assert catalog._main(["package", "sample"]) == 0  # 셸·Dockerfile 용


def test_cli_package(capsys):
    catalog._main(["package", "sample"])
    assert capsys.readouterr().out.strip() == "sample"


def test_routes_longest_prefix_first():
    assert catalog.route_for("/sample/items") == "sample"
    assert catalog.route_for("/sample") == "sample"
    assert catalog.route_for("/samplex") is None
    lens = [len(p) for p, _ in catalog.routes()]
    assert lens == sorted(lens, reverse=True)


def test_allow_from_default_empty():
    """서비스 단위 NetworkPolicy 허용 목록(REQ-261104-10-4) — services.json k8s.allow_from(선택). 없으면 빈 값 = 게이트웨이만 부른다."""
    assert all(isinstance(s.allow_from, tuple) for s in catalog.services())
    bare = catalog.ServiceSpec(name="a", group="business", desc="", scope="A", local_port=1)
    assert bare.allow_from == ()
    s = catalog.ServiceSpec(name="b", group="business", desc="", scope="B", local_port=2, k8s={"allow_from": ["a", "c"]})
    assert s.allow_from == ("a", "c")
