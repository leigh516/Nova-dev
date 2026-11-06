"""디자인 킷(REQ-261106-04-1 · -4) — 킷 합치기 · 모든 킷 대비 검사 · 정보=성공 상태색 겹침 · kit use/show.

저장소의 실제 nova.project.json · 생성물은 건드리지 않는다 — 임시 폴더에 토큰 원천과 메타만 복사해 그 안에서 생성한다.
"""
import json
import shutil
from pathlib import Path

import pytest

import gen_tokens as gt
import kits

REPO = gt.ROOT


@pytest.fixture
def root(tmp_path: Path) -> Path:
    shutil.copytree(REPO / "design" / "tokens", tmp_path / "design" / "tokens")
    meta = json.loads((REPO / "nova.project.json").read_text(encoding="utf-8"))
    meta.pop("design", None)                     # 저장소가 무슨 킷이든 '설정 없음'에서 시작
    (tmp_path / "nova.project.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return tmp_path


def css(root: Path) -> str:
    return (root / gt.OUT_CSS.relative_to(REPO)).read_text(encoding="utf-8")


def meta(root: Path) -> dict:
    return json.loads((root / "nova.project.json").read_text(encoding="utf-8"))


def test_default_kit_is_nova_and_bytes_equal_current_outputs(root):
    """반목표 — 기본 킷 nova 의 생성물이 바뀌면 안 된다: 설정이 없을 때 · kit=nova 일 때 모두 저장소 생성물과 같은 바이트."""
    assert gt.selected_kit(root) == "nova"
    outs = gt.outputs(root)
    repo_outs = {gt.OUT_CSS: gt.OUT_CSS.read_text(encoding="utf-8"), gt.out_kt(): gt.out_kt().read_text(encoding="utf-8")}
    for path, text in repo_outs.items():
        assert outs[root / path.relative_to(REPO)] == text.replace("\r\n", "\n"), path


def test_use_newtype_writes_newtype_values_then_nova_restores(root, capsys):
    rec = kits.use("newtype", root=root, by="tester", source="checklist")
    assert rec["kit"] == "newtype" and rec["by"] == "tester" and rec["source"] == "checklist" and rec["date"]
    assert meta(root)["design"]["kit"] == "newtype"
    text = css(root)
    assert "--color-action-primary: #1E7A5A;" in text           # newtype 주 색
    assert "--color-border-control: #7A8682;" in text           # 조정한 경계선(원본 #C9D3CF 은 1.53)
    assert "--radius-md: 12px;" in text
    assert "WCAG" in capsys.readouterr().out                    # 대비 결과를 보인다
    kt = (root / gt.out_kt(root).relative_to(root)).read_text(encoding="utf-8")
    assert "Color(0xFF1E7A5A)" in kt
    kits.use("nova", root=root, by="tester", source="manual")
    assert css(root) == gt.OUT_CSS.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert kits.show(root)["kit"] == "nova" and kits.show(root)["source"] == "manual"


def test_show_without_setting_reports_default(root):
    s = kits.show(root)
    assert s["kit"] == "nova" and s["source"] == "default"


def test_unknown_kit_is_rejected_and_meta_untouched(root):
    before = (root / "nova.project.json").read_text(encoding="utf-8")
    with pytest.raises(kits.KitError, match="모르는 킷"):
        kits.use("glendale", root=root, by="t", source="manual")
    assert (root / "nova.project.json").read_text(encoding="utf-8") == before


def _add_kit(root: Path, kid: str, tokens: dict) -> None:
    cat_p = root / "design" / "tokens" / "kits" / "catalog.json"
    cat = json.loads(cat_p.read_text(encoding="utf-8"))
    cat["kits"].append({"id": kid, "label": kid, "desc": "시험", "tokens": f"{kid}.tokens.json",
                        "preview": {"hex": "#000000", "radius": "md", "gap": "2", "dark": False}, "gaps": [], "status": "채택 가능"})
    cat_p.write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    (root / "design" / "tokens" / "kits" / f"{kid}.tokens.json").write_text(json.dumps(tokens), encoding="utf-8")


def test_low_contrast_kit_in_catalog_fails_check_even_if_not_selected(root, capsys):
    """선택하지 않은 킷도 미달이면 --check 실패 — 대비 미달 킷이 목록에 올라 '고를 수 있는' 상태가 되지 않게."""
    gt.main(False, root=root)                                     # 선택 킷(nova) 생성물을 먼저 만든다
    assert gt.main(True, root=root) == 0
    _add_kit(root, "pale", {"primitive": {"color": {"neutral": {"500": {"$value": "#E0E0E0"}}}}})   # 컨트롤 경계가 거의 흰색
    capsys.readouterr()
    assert gt.main(True, root=root) == 1
    out = capsys.readouterr().out
    assert "킷 pale" in out and "border.control" in out
    with pytest.raises(kits.KitError, match="대비"):
        kits.use("pale", root=root, by="t", source="manual")
    assert "design" not in meta(root)


def test_info_equal_success_fails():
    """-4 — 브랜드가 초록이면 정보색(brand.600)이 성공색과 같아질 수 있다: 같은 값 · 같은 원시 참조 모두 실패."""
    t = gt.load()
    assert gt.check_status_distinct(t) == []
    t["primitive"]["color"]["brand"]["600"]["$value"] = t["primitive"]["color"]["green"]["700"]["$value"]   # 같은 값
    errs = gt.check_status_distinct(t)
    assert any("infoFg" in e and "successFg" in e for e in errs), errs
    t = gt.load()
    st = t["semantic"]["color"]["status"]
    st["infoBg"] = dict(st["successBg"])                                                                     # 같은 원시 참조
    assert any("infoBg" in e and "successBg" in e for e in gt.check_status_distinct(t))


def test_info_equal_success_kit_fails_check(root):
    green = "#0E7A57"   # Nova 성공색 green.700 과 같은 값을 브랜드로 — 정보색이 성공색과 겹친다
    _add_kit(root, "same", {"primitive": {"color": {"brand": {"600": {"$value": green}}}}})
    gt.main(False, root=root)
    assert gt.main(True, root=root) == 1


def test_repo_catalog_kits_all_pass():
    for k in gt.catalog(REPO):
        assert gt.kit_errors(gt.load_kit(k["id"], REPO)) == [], k["id"]
