"""명명 규약 · 개념 원장(naming.py) — 형식마다 잘못된 이름을 잡는지, baseline 이 신규만 막는지, 조회 5갈래 · 정규화,
금지 별칭 · 좀비 · 미등재, naming.md 생성 구간 드리프트, 지금 저장소가 통과하는지. 임시 폴더를 root 로 쓴다."""
import json
import re
import shutil
from pathlib import Path

import pytest

import naming
import new_service
import novalib
import packs
from novalib import write

ROOT = Path(__file__).resolve().parents[1]
BASE_COLS = [
    {"table": "item", "column": "id", "type": "VARCHAR(36)", "flags": ["PK"], "service": "sample", "common": False},
    {"table": "item", "column": "name", "type": "VARCHAR(100)", "flags": [], "service": "sample", "common": False},
    {"table": "item", "column": "created_at", "type": "DATETIME", "flags": [], "service": "sample", "common": False},
]


def _dump(p: Path, data) -> None:
    write(p, json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def set_cols(root: Path, rows: list[dict]) -> None:
    led = json.loads((root / naming.LEDGERS).read_text(encoding="utf-8"))
    led["db"] = rows
    _dump(root / naming.LEDGERS, led)


def set_rules(root: Path, **changes) -> dict:
    rules = naming.load_rules(root)
    rules.update(changes)
    _dump(root / naming.RULES, rules)
    naming.write_doc(root)
    return rules


def errors(root: Path) -> list[str]:
    return naming.check(root)[0]


def has(errs: list[str], needle: str) -> bool:
    return any(needle in e for e in errs)


@pytest.fixture
def repo(tmp_path):
    """작은 저장소 — 플랫폼 형식(naming.json)은 그대로, baseline · 예외는 비우고 항목(item) 하나만 등재.

    예외도 baseline 처럼 그 저장소의 실제 표(outbox · processed_event)에 묶인 목록이다 — 표가 없는 작은 저장소에서는
    '더 이상 위반이 아니다'로 잡힌다(2026-11-04 T03-9.05 로 예외가 처음 생겨 드러남)."""
    rules = json.loads((ROOT / naming.RULES).read_text(encoding="utf-8"))
    rules["baseline"] = []
    rules["exceptions"] = []
    _dump(tmp_path / naming.RULES, rules)
    write(tmp_path / naming.DOC, (ROOT / naming.DOC).read_text(encoding="utf-8"))
    _dump(tmp_path / naming.SERVICES, {"services": [{"name": "sample", "scope": "SAMPLE"}, {"name": "gateway", "scope": "GW", "gateway": True}]})
    write(tmp_path / naming.TOPICS, "# 카탈로그\nsample.item.created 3 7\nplatform.rbac.changed 1 7\n")
    _dump(tmp_path / naming.RBAC, {"roles": {"user": {"name": "사용자", "perms": ["sample.read", "sample.create"]}, "admin": {"perms": ["*"]}}})
    _dump(tmp_path / naming.LEDGERS, {"db": BASE_COLS, "permissions": [{"key": "sample.read"}]})
    _dump(tmp_path / naming.ARTIFACTS, {"API-SAMPLE-0001": {"kind": "API", "name": "GET /sample/items/{item_id}/archive", "status": "active"},
                                        "CMP-UI-0001": {"kind": "CMP", "name": "DataTable", "status": "active"}})
    write(tmp_path / naming.UI_INDEX, 'export { Button, type Variant } from "./basic";\nexport { useApi, fmtAt, DEFAULT_SHORTCUTS } from "./hooks";\n')
    (tmp_path / "packs" / "example").mkdir(parents=True)
    _dump(tmp_path / "packs" / "example" / "pack.json", {"name": "example", "extends": ["sample"], "entities": []})
    naming.write_doc(tmp_path)
    naming.add_entity(tmp_path, "item", "항목", "sample", "item", "core", lookup_aliases=["항목"], by="test", at="2030-01-01T00:00:00Z")
    return tmp_path


# ───────────────────────── 지금 저장소 · 깨끗한 저장소
def test_current_repo_passes():
    errs, stats = naming.check(ROOT)
    assert errs == [], errs
    assert stats["rules"] >= 15 and stats["baseline"] == len(naming.load_rules(ROOT)["baseline"])


def test_clean_fixture_passes(repo):
    assert errors(repo) == []


# ───────────────────────── 형식마다 잘못된 이름
def _col(column, typ="VARCHAR(40)", table="item"):
    return {"table": table, "column": column, "type": typ, "flags": [], "service": "sample", "common": False}


@pytest.mark.parametrize("extra,rule", [
    (_col("createdAt"), "[column]"),
    (_col("at", "DATETIME"), "[column_datetime]"),
    (_col("sent_at", "VARCHAR(20)"), "[column_datetime]"),
    (_col("parked", "BOOLEAN"), "[column_bool]"),
    (_col("is_done", "VARCHAR(1)"), "[column_bool]"),
    (_col("emp_name"), "[forbidden_abbr]"),
])
def test_column_formats(repo, extra, rule):
    set_cols(repo, BASE_COLS + [extra])
    assert has(errors(repo), rule), errors(repo)


@pytest.mark.parametrize("table,rule", [("items", "[table_singular]"), ("Order", "[table]"), ("cust_order", "[forbidden_abbr]")])
def test_table_formats(repo, table, rule):
    set_cols(repo, BASE_COLS + [{**c, "table": table} for c in BASE_COLS])
    assert has(errors(repo), rule)


def test_pk_must_be_single_uuid_id(repo):
    set_cols(repo, BASE_COLS + [{**_col("id", "INTEGER", "item_log"), "flags": ["PK"]}])
    assert has(errors(repo), "[pk] 표 'item_log'")
    set_cols(repo, BASE_COLS + [{**_col("event_id", "VARCHAR(36)", "item_log"), "flags": ["PK"]},
                                {**_col("consumer", "VARCHAR(36)", "item_log"), "flags": ["PK"]}])
    assert has(errors(repo), "[pk] 표 'item_log'")  # 복합키


def test_column_ref_catches_hand_written_ref(repo):
    """REQ-261104-12-7 — _id · _by 로 끝나는 참조 칸이 손으로 쓴 String(40) 이면 잡는다(ref_column = VARCHAR(36))."""
    set_cols(repo, BASE_COLS + [_col("created_by", "VARCHAR(40)")])
    assert has(errors(repo), "[column_ref] 칸 'item.created_by'"), errors(repo)
    set_cols(repo, BASE_COLS + [_col("owner_id", "INTEGER")])
    assert has(errors(repo), "[column_ref] 칸 'item.owner_id'")


def test_column_ref_passes_ref_column_and_tenant(repo):
    """ref_column(VARCHAR(36)) 은 통과, tenant_id 는 tenant_column 헬퍼(VARCHAR(40)) 라 형식 정의에서 뺀다(길이 통일은 별도 요구)."""
    set_cols(repo, BASE_COLS + [_col("created_by", "VARCHAR(36)"), _col("item_id", "VARCHAR(36)"), _col("tenant_id", "VARCHAR(40)")])
    assert errors(repo) == []


def test_column_ref_rule_is_required(repo):
    rules = naming.load_rules(repo)
    del rules["formats"]["column_ref"]
    _dump(repo / naming.RULES, rules)
    assert has(errors(repo), "formats.column_ref 가 없다 — 판정 불가")


@pytest.mark.parametrize("topic,needle", [
    ("sample.item.create", "과거형"), ("billing.item.created", "첫 마디"), ("Sample.item.created", "[topic]"),
    ("sample.item", "[topic]"), ("sample.prod.created", "[forbidden_abbr]"),
])
def test_topic_formats(repo, topic, needle):
    write(repo / naming.TOPICS, f"sample.item.created 3 7\n{topic} 1 7\n")
    assert has(errors(repo), needle), errors(repo)


def test_topic_irregular_past_and_platform_ok(repo):
    write(repo / naming.TOPICS, "sample.item.sent 3 7\nplatform.feature.changed 1 7\n")
    assert errors(repo) == []


@pytest.mark.parametrize("perm,needle", [("sample.item.read", "[permission]"), ("billing.read", "모듈 'billing'"), ("sample.approve", "[permission]")])
def test_permission_formats(repo, perm, needle):
    _dump(repo / naming.RBAC, {"roles": {"user": {"perms": ["sample.read", perm]}}})
    assert has(errors(repo), needle)


def test_permission_declared_module_ok(repo):
    _dump(repo / naming.RBAC, {"roles": {"manager": {"perms": ["sample.*", "ops.read"]}}})
    assert errors(repo) == []  # ops 는 declared_permission_modules


def test_error_code_api_component_web_export(repo):
    write(repo / "services/sample/sample/x.py", 'raise ApiError(404, "ItemNotFound", "항목이 없습니다")\n')
    reg = json.loads((repo / naming.ARTIFACTS).read_text(encoding="utf-8"))
    reg["API-SAMPLE-0002"] = {"kind": "API", "name": "GET /sample/Items/{itemId}", "status": "active"}
    reg["CMP-UI-0002"] = {"kind": "CMP", "name": "dataList", "status": "active"}
    reg["API-SAMPLE-0003"] = {"kind": "API", "name": "GET /sample/BAD", "status": "deleted"}  # 삭제된 것은 보지 않는다
    _dump(repo / naming.ARTIFACTS, reg)
    write(repo / naming.UI_INDEX, 'export { Button, _hidden } from "./basic";\n')
    errs = errors(repo)
    for needle in ("[error_code] 오류 코드 'ItemNotFound'", "[api_segment] API 경로 'Items'", "[api_segment] API 경로 '{itemId}'",
                   "[component] 컴포넌트 'dataList'", "[web_export] @nova/ui '_hidden'"):
        assert has(errs, needle), (needle, errs)
    assert not has(errs, "'BAD'")


def test_service_scope_pack_formats(repo):
    _dump(repo / naming.SERVICES, {"services": [{"name": "sample", "scope": "SAMPLE"}, {"name": "Order_Hub", "scope": "o"}]})
    (repo / "packs" / "Bad-Pack").mkdir()
    write(repo / "packs/example/schema/sample.py", '__tablename__ = "example_item"\n')
    errs = errors(repo)
    for needle in ("[service] 서비스 'Order_Hub'", "[scope] 범위 'o'", "[pack] 팩 'Bad-Pack'", "[pack_ext_table]"):
        assert has(errs, needle), (needle, errs)


def test_project_formats_are_added(repo):
    set_rules(repo, project={"formats": {"no_memo": {"applies_to": "column", "deny": "^memo$", "label": "메모 칸 금지", "why": "프로젝트 규칙"}},
                             "forbidden_abbr": {"nm": "name"}})
    set_cols(repo, BASE_COLS + [_col("memo"), _col("item_nm")])
    errs = errors(repo)
    assert has(errs, "[project.no_memo]") and has(errs, "금지 축약 'nm'")


# ───────────────────────── baseline · 예외 — 신규만 막는다
def test_baseline_blocks_only_new(repo):
    set_cols(repo, BASE_COLS + [_col("at", "DATETIME")])
    set_rules(repo, baseline=[{"rule": "column_datetime", "target": "sample:item.at", "why": "기존 위반 — 별도 요구"}])
    assert errors(repo) == []
    set_cols(repo, BASE_COLS + [_col("at", "DATETIME"), _col("parked", "BOOLEAN")])  # 새 위반은 막는다
    assert has(errors(repo), "[column_bool]") and not has(errors(repo), "'item.at'")
    set_cols(repo, BASE_COLS)  # 고쳤으면 baseline 에서 지우게 한다(줄기만)
    assert has(errors(repo), "더 이상 위반이 아니다")


def test_baseline_and_exceptions_need_reason(repo):
    set_cols(repo, BASE_COLS + [_col("at", "DATETIME")])
    set_rules(repo, exceptions=[{"rule": "column_datetime", "target": "sample:item.at", "why": " "}])
    assert has(errors(repo), "why(이유)")


def test_empty_formats_is_undecidable(repo):
    rules = naming.load_rules(repo)
    rules["formats"] = {}
    _dump(repo / naming.RULES, rules)
    assert has(errors(repo), "판정 불가")
    rules = json.loads((ROOT / naming.RULES).read_text(encoding="utf-8"))
    del rules["formats"]["pk"]
    _dump(repo / naming.RULES, rules)
    assert has(errors(repo), "formats.pk 가 없다 — 판정 불가")


# ───────────────────────── 조회 5갈래 · 정규화
@pytest.mark.parametrize("raw,norm", [
    ("DeptMaster", "dept"), ("dept-masters", "dept"), ("dept_master", "dept"), ("order_log", "order log"),
    ("order_history", "order history"), ("status", "status"), ("categories", "category"), ("item_tbl", "item"),
    ("부서마스터", "부서"), ("master", "master"), ("OrderLines", "order line"),
])
def test_normalize(raw, norm):
    assert naming.normalize(raw) == norm


def test_lookup_five_verdicts(repo, capsys):
    naming.add_entity(repo, "member", "회원", "sample", None, "core", forbidden_aliases=["usr"], by="t")
    naming.add_entity(repo, "coupon", "쿠폰", "sample", None, "core", by="t")
    naming.retire(repo, "coupon", "쿠폰 기능 폐지", by="t")
    verdict = lambda q: naming.lookup(repo, q)["verdict"]  # noqa: E731
    assert verdict("item") == verdict("Items") == verdict("ItemMaster") == verdict("item_tbl") == "정확"
    assert verdict("항목") == "별칭" and verdict("usr") == "별칭"
    assert verdict("item_log") == "유사"
    assert verdict("coupons") == "은퇴"
    assert verdict("invoice") == "없음"
    assert naming.main(["lookup", "invoice", "coupon"], root=repo) == 0  # 조회는 항상 0
    out = capsys.readouterr().out
    assert "사람 승인 후" in out and "복원인지 신설인지" in out


# ───────────────────────── 금지 별칭 · 좀비 · 미등재
def test_forbidden_alias_in_ledger_name(repo):
    naming.add_alias(repo, "item", "entry", forbidden=True, by="t")
    assert errors(repo) == []
    set_cols(repo, BASE_COLS + [_col("entry_name")])
    assert has(errors(repo), "금지 별칭: 칸 'entry_name'")
    naming.add_entity(repo, "order", "주문", "sample", None, "core", by="t")
    with pytest.raises(naming.NamingError, match="정본 이름"):
        naming.add_alias(repo, "order", "item", by="t")  # 다른 개념의 정본 이름을 별칭으로 쓸 수 없다


def test_zombie_and_unregistered(repo):
    naming.add_entity(repo, "order", "주문", "sample", "order", "core", by="t")
    assert has(errors(repo), "좀비 개념: order")
    set_cols(repo, BASE_COLS + [{**c, "table": "order"} for c in BASE_COLS] + [{**c, "table": "invoice"} for c in BASE_COLS])
    errs = errors(repo)
    assert not has(errs, "좀비") and has(errs, "미등재 표: sample.invoice")
    naming.retire(repo, "order", "주문 기능 이전", by="t")
    assert has(errors(repo), "미등재 표: sample.order")  # 은퇴한 개념은 실물을 덮지 않는다


def test_platform_entity_matches_common_tables(repo):
    naming.add_entity(repo, "outbox", "아웃박스", "*", "outbox", "platform", by="t")
    assert has(errors(repo), "좀비 개념: outbox")
    set_cols(repo, BASE_COLS + [{**BASE_COLS[0], "table": "outbox", "common": True}])
    assert errors(repo) == []
    with pytest.raises(naming.NamingError, match="platform 층만"):
        naming.add_entity(repo, "x_star", "별", "*", None, "core", by="t")


def test_entity_validation_and_retired_key(repo):
    with pytest.raises(naming.NamingError, match="layer=pack"):
        naming.add_entity(repo, "rx", "처방", "sample", None, "pack", by="t")
    with pytest.raises(naming.NamingError, match="없는 서비스"):
        naming.add_entity(repo, "rx", "처방", "billing", None, "core", by="t")
    with pytest.raises(naming.NamingError, match="이미 item 로 등재"):
        naming.add_entity(repo, "thing", "물건", "sample", "item", "core", by="t")
    naming.retire(repo, "item", "샘플 삭제", by="t")
    with pytest.raises(naming.NamingError, match="은퇴한 키"):
        naming.add_entity(repo, "item", "항목", "sample", "item", "core", by="t")


def test_pack_entities_must_match(repo):
    naming.add_entity(repo, "example_item_ext", "예시 확장", "sample", None, "pack", "example", by="t")
    assert has(errors(repo), "pack.json entities 에 없다")
    _dump(repo / "packs/example/pack.json", {"name": "example", "entities": ["example_item_ext", "ghost"]})
    errs = errors(repo)
    assert not has(errs, "entities 에 없다") and has(errs, "'ghost'")
    naming.set_layer(repo, "example_item_ext", "core", "코어 승격", by="t")
    assert naming.entities(repo)["example_item_ext"]["layer"] == "core"


# ───────────────────────── 이력 · 생성 구간 드리프트
def test_snapshot_must_equal_replay(repo):
    p = repo / naming.ENTITIES
    write(p, p.read_text(encoding="utf-8").replace("항목", "아이템", 1))
    assert has(errors(repo), "재생 결과와 다르다")
    lines = (repo / naming.ENTITY_LOG).read_text(encoding="utf-8").splitlines()
    write(repo / naming.ENTITY_LOG, "\n".join(lines * 2) + "\n")
    assert has(errors(repo), "이력 오류")


def test_doc_section_drift(repo):
    rules = naming.load_rules(repo)
    rules["formats"]["table"]["example"] = "바뀐 예"
    _dump(repo / naming.RULES, rules)
    assert has(errors(repo), "naming --write")
    assert naming.main(["--write"], root=repo) == 0 and errors(repo) == []
    text = (repo / naming.DOC).read_text(encoding="utf-8")
    write(repo / naming.DOC, text.replace(naming.END, ""))
    assert has(errors(repo), "표식이 없다")


def test_doc_section_has_every_rule(repo):
    text = (repo / naming.DOC).read_text(encoding="utf-8")
    for rid in naming.load_rules(repo)["formats"]:
        assert f"`{rid}`" in text
    assert "손으로 고치지 않는다" in text


# ───────────────────────── 쓰기는 main 만 · 새 프로젝트
def test_writes_require_main(repo, monkeypatch):
    monkeypatch.delenv("NOVA_ALLOW_WORKTREE_WRITE", raising=False)
    monkeypatch.setattr(novalib, "in_linked_worktree", lambda cwd=None: True)
    with pytest.raises(SystemExit, match="단일 기록자"):
        naming.main(["retire", "item", "--why", "x"], root=repo)
    assert naming.main(["lookup", "item"], root=repo) == 0  # 조회는 어디서나


def test_cli_write_commands(repo, monkeypatch):
    monkeypatch.setenv("NOVA_ALLOW_WORKTREE_WRITE", "1")
    assert naming.main(["alias", "add", "item", "물품", "--by", "t"], root=repo) == 0
    assert naming.main(["entity", "add", "member", "--title", "회원", "--service", "sample", "--layer", "core", "--by", "t"], root=repo) == 0
    assert naming.main(["entity", "add", "member", "--title", "회원", "--service", "sample", "--layer", "core"], root=repo) == 1
    assert naming.lookup(repo, "물품")["verdict"] == "별칭"
    assert [e["action"] for e in naming.load_events(repo)] == ["create", "alias", "create"]


def test_reset_for_project(repo):
    naming.add_alias(repo, "item", "entry", forbidden=True, by="t")
    naming.add_entity(repo, "outbox", "아웃박스", "*", "outbox", "platform", forbidden_aliases=["event_queue"], by="t")
    naming.add_entity(repo, "coupon", "쿠폰", "sample", None, "core", by="t")
    naming.retire(repo, "coupon", "폐지", by="t")
    state = naming.reset_for_project(repo, at="2030-05-06T00:00:00Z")
    assert sorted(state) == ["item", "outbox"]  # 은퇴 · 이력은 가져가지 않는다
    assert state["item"]["forbidden_aliases"] == [] and state["outbox"]["forbidden_aliases"] == ["event_queue"]
    assert [e["seq"] for e in naming.load_events(repo)] == [1, 2]


# ───────────────────────── 정규식 단일화
def test_other_scripts_read_regex_from_naming_json():
    fm = naming.formats(ROOT)
    assert new_service.NAME.pattern == fm["service"]["regex"] and new_service.SCOPE.pattern == fm["scope"]["regex"]
    assert packs.NAME.pattern == fm["pack"]["regex"]
    src = (ROOT / "tests/test_topic_catalog.py").read_text(encoding="utf-8")
    assert 'naming.pattern("topic"' in src
    assert naming.pattern("pack_ext_table", ROOT, pack="pharma").match("pharma_item_ext")
    assert not naming.pattern("pack_ext_table", ROOT, pack="pharma").match("fresh_item_ext")
    for bad in ("Order", "order_hub", "-x"):
        assert not new_service.NAME.match(bad)
    assert re.fullmatch(fm["permission"]["regex"], "order-hub.*")


def test_new_service_registers_template_entity(repo):
    shutil.copytree(ROOT / "services/_template", repo / "services/_template", ignore=shutil.ignore_patterns("__pycache__"))
    write(repo / "services/gateway/gateway/rbac.json", (ROOT / naming.RBAC).read_text(encoding="utf-8"))
    _dump(repo / naming.SERVICES, {"groups": [{"key": "business"}], "services": [{"name": "sample", "scope": "SAMPLE", "local_port": 8001},
                                                                                   {"name": "gateway", "scope": "GW", "gateway": True, "local_port": 8080}]})
    new_service.create(repo, "order-hub", "business", "ORDER", "주문")
    e = naming.entities(repo)["order_hub_record"]
    assert (e["service"], e["table"], e["layer"]) == ("order-hub", "record", "core")
    assert '__tablename__ = "record"' in (repo / "services/order-hub/order_hub/models.py").read_text(encoding="utf-8")
