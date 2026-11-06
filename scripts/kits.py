#!/usr/bin/env python3
"""디자인 킷 고르기(REQ-261106-04 · ADR-016) — 킷 = 토큰 한 벌(design/tokens/kits/) + 부품 갭.

  python nova.py kit list              # 킷 목록 · 지금 고른 킷 표시
  python nova.py kit show              # 지금 설정 · 출처(checklist | manual | default) · 날짜 · 갭
  python nova.py kit use <id> [--by 이름] [--source manual|checklist]

흐름: 체크리스트에서 고르면 import 가 use(…, source="checklist") 로 설정 → /foundation 5단계가 kit show 로
확인받고, 바꾸면 kit use 로 다시 설정한다. 되돌리기는 kit use nova(생성물이 원래 바이트로 돌아간다).
use 는 목록에 있는 킷만, 대비 · 분리 · 상태색 겹침 검사를 통과한 킷만 받는다. 실패하면 KitError(메타는 그대로).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_tokens as gt  # noqa: E402
from novalib import ROOT, write  # noqa: E402

SOURCES = ("manual", "checklist")
SOURCE_LABEL = {"manual": "수동(kit use)", "checklist": "체크리스트", "default": "기본(설정 없음)"}


class KitError(Exception):
    """킷을 고를 수 없다 — 모르는 id · 대비 미달 · 생성 실패."""


def _meta_path(root: Path) -> Path:
    return root / "nova.project.json"


def _write_meta(root: Path, meta: dict) -> None:
    write(_meta_path(root), json.dumps(meta, ensure_ascii=False, indent=2) + "\n")


def show(root: Path = ROOT) -> dict:
    """지금 설정 — design 키가 없으면 기본 킷 nova · 출처 default."""
    d = gt.project(root).get("design") or {}
    if not d.get("kit"):
        return {"kit": gt.DEFAULT_KIT, "source": "default", "date": "", "by": ""}
    return {"kit": d["kit"], "source": d.get("source", "manual"), "date": d.get("date", ""), "by": d.get("by", "")}


def use(kit_id: str, *, root: Path = ROOT, by: str, source: str = "manual", today: dt.date | None = None) -> dict:
    """킷을 고른다 — 검사 → nova.project.json design 기록 → 토큰 생성(대비 출력). 체크리스트 import 도 이 함수를 부른다.

    반환: 기록한 design 사전. 실패하면 KitError 이고 nova.project.json · 생성물은 그대로다.
    """
    ids = [k["id"] for k in gt.catalog(root)]
    if kit_id not in ids:
        raise KitError(f"모르는 킷: {kit_id} — 고를 수 있는 킷 {ids}")
    if source not in SOURCES:
        raise KitError(f"출처는 {SOURCES} 중 하나: {source}")
    errs = gt.kit_errors(gt.load_kit(kit_id, root))
    if errs:
        raise KitError(f"킷 {kit_id} 대비 · 분리 검사 미달 {len(errs)}건 — " + " / ".join(errs[:5]))
    before = _meta_path(root).read_text(encoding="utf-8")
    meta = json.loads(before)
    rec = {"kit": kit_id, "date": (today or dt.date.today()).isoformat(), "by": by, "source": source}
    meta["design"] = rec
    _write_meta(root, meta)
    if gt.main(False, root=root) != 0:
        # 생성 · 검사가 실패하면(다른 킷의 미달 · 토큰 밖 색 사용) 고르기 전으로 되돌린다 — 메타와 생성물이 어긋나지 않게
        write(_meta_path(root), before)
        gt.main(False, root=root)
        raise KitError(f"킷 {kit_id} 로 생성했으나 토큰 검사가 실패해 되돌렸다 — 위 ✗ 줄을 고친 뒤 다시")
    return rec


def _print_list(root: Path) -> None:
    cur = show(root)["kit"]
    for k in gt.catalog(root):
        mark = "●" if k["id"] == cur else "○"
        gaps = ", ".join(k.get("gaps") or []) or "없음"
        print(f"{mark} {k['id']:<10} {k.get('label', '')} — {k.get('status', '')} · 부품 갭 {gaps}")


def _print_show(root: Path) -> None:
    s = show(root)
    entry = next((k for k in gt.catalog(root) if k["id"] == s["kit"]), {})
    print(f"킷 {s['kit']} ({entry.get('label', '목록에 없음')})")
    print(f"  출처 {SOURCE_LABEL.get(s['source'], s['source'])} · 날짜 {s['date'] or '-'} · 정한 사람 {s['by'] or '-'}")
    print(f"  부품 갭 {', '.join(entry.get('gaps') or []) or '없음'}")
    if s["source"] != "manual":
        print("  /foundation 5단계에서 확인받는다 — 바꾸려면 python nova.py kit use <id>")


def main(argv: list[str], root: Path = ROOT) -> int:
    if not argv or argv[0] in ("list", "ls"):
        _print_list(root)
        return 0
    if argv[0] == "show":
        _print_show(root)
        return 0
    if argv[0] == "use" and len(argv) >= 2:
        opts = dict(zip(argv[2::2], argv[3::2]))
        by = opts.get("--by") or gt.project(root).get("owner", "")
        try:
            rec = use(argv[1], root=root, by=by, source=opts.get("--source", "manual"))
        except KitError as e:
            print(f"✗ {e}")
            return 1
        print(f"✓ 킷 {rec['kit']} 채택 — nova.project.json design 기록({rec['date']} · {rec['by']} · {rec['source']}) · "
              f"되돌리기: python nova.py kit use {gt.DEFAULT_KIT}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
