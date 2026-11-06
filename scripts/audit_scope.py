#!/usr/bin/env python3
"""심층 감사(/deep-audit) 분모 — 무엇을 몇 개 보고, 무엇을 왜 빼고, 기존 게이트가 이미 무엇을 잡는지.

  uv run python scripts/audit_scope.py                 전체 분모 표(축별 대상 파일 수 · 제외 · 게이트)
  uv run python scripts/audit_scope.py services/sample 범위를 경로로 좁힌다(여러 개 가능)
  uv run python scripts/audit_scope.py --json          기계용(축 위임 프롬프트에 그대로 싣는다)
  uv run python scripts/audit_scope.py --files <축>    그 축이 볼 파일 목록

감사 축은 .claude/commands/deep-audit.md §2 가 정본이고, 이 스크립트는 축마다 '볼 파일 묶음'과 '이미 게이트가 보는 것'을 계산만 한다.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT  # noqa: E402

MARKERS = ("생성 파일", "생성물:")
# 표시는 없지만 생성기가 만드는 파일(생성기 이름 = 제외 사유)
GENERATED_GLOBS = {
    "docs/registry/*.md": "ledgers.py · registry.py 가 만든다",
    "registry/ledgers.json": "ledgers.py 가 만든다",
    "registry/registry.json": "registry.py 가 만든다",
    "registry/entities.json": "naming.py 가 entities.jsonl 을 재생해 만든다",
    "infra/observability/grafana/dashboards/*.json": "gen_dashboards.py 가 만든다",
    "uv.lock": "uv 잠금 파일",
    "web/package-lock.json": "npm 잠금 파일",
    "docs/screenshots/*": "화면 캡처(바이너리)",
}
BUCKETS = {
    "python": ("파이썬 코드", lambda p: p.suffix == ".py" and not is_test(p)),
    "web": ("웹 코드", lambda p: p.parts[0] == "web" and p.suffix in (".ts", ".tsx", ".css", ".mjs")),
    "kmp": ("앱 코드(KMP)", lambda p: p.parts[0] == "apps" and p.suffix in (".kt", ".kts")),
    "infra": ("인프라 · 배포", lambda p: p.parts[0] == "infra" or p.name in ("docker-compose.yml", "Makefile")),
    "docs": ("문서 · 규칙 · 명령", lambda p: p.suffix == ".md"),
    "tests": ("테스트", lambda p: is_test(p)),
    "data": ("선언 · 설정(JSON · 토큰)", lambda p: p.suffix in (".json", ".toml", ".yaml", ".yml") and p.parts[0] not in ("infra",)),
    "form": ("폼 · 템플릿(HTML)", lambda p: p.suffix == ".html"),
}
# 감사 축 → 볼 묶음 · 이미 게이트가 보는 것(분모에서 뺄 것)
AXES = {
    "연결성": (("python", "web", "data"), "packs.py check(코어 → 팩 import 금지) · ledgers.py --check(없는 API · 카탈로그 밖 구독)"),
    "비즈니스 로직": (("python", "web", "kmp"), "단위 · 통합 테스트(python nova.py test)가 덮는 분기"),
    "보안": (("python", "web", "infra", "data"), "게이트웨이 테스트(/internal 차단 · 헤더 위조 제거 · 권한) — 그 밖의 경로가 대상"),
    "API 계약": (("python", "web", "data"), "ledgers.py --check(화면이 부르는 API 실재) · warehouse.py check(SPEC 참조)"),
    "에러 처리": (("python", "web", "kmp"), "없음 — 삼킨 예외 · 실패 표시는 게이트가 보지 않는다"),
    "입력 유효성": (("python", "web", "kmp"), "없음 — §3 표 전부가 대상"),
    "데이터 모델": (("python", "data"), "ledgers.py --check(칸 의미 comment) · ADR-003 UUIDv7 테스트"),
    "성능": (("python", "web"), "없음 — 실측으로만(추측 보고 금지)"),
    "접근성 · 디자인 토큰": (("web", "kmp", "form"), "gen_tokens.py --check(WCAG 대비 50쌍) · ui-smoke · checklist-smoke"),
    "테스트 실효": (("tests", "python"), "없음 — 초록이 무엇을 지키는지는 게이트가 모른다"),
    "문서 · 코드 정합": (("docs",), "docs_index.py --check(인덱스 · 링크 · 한글 · 표준 판정)"),
    "표준 · 테넌시 · AX": (("python", "web", "data"), "docs_index.py(판정 존재만) — 판정과 코드가 맞는지는 대상"),
    "한국어 규칙": (("python", "web", "kmp", "form"), "docs_index.py(문서의 한글만) — 주석 · 오류 메시지 · 화면 문구가 대상"),
    "생성물 · 단일 원천": (("data", "infra", "web"), "gen_tokens · gen_k3s · gen_dashboards · ledgers · registry · checklist · warehouse 의 --check"),
    "운영 · 인프라": (("infra",), "validate_infra.py(렌더 · 규칙 · 대시보드) — 자원 한도 · 프로브 · 비밀 · 알림 범위가 대상"),
}
# nova.py lint 의 각 단계가 잡는 것 — test_audit_scope 가 lint 와 이 표가 같은지 확인한다
GATES = {
    "gen_tokens.py": "디자인 토큰 생성물 최신 · WCAG AA 대비",
    "ui_check.py": "웹 화면 · 부품의 토큰 밖 색 · 인라인 px(예외는 web/ui-check.json 이유 필수 · 토큰 값 대조)",
    "gen_k3s.py": "k3s · Helm · compose 생성물 최신",
    "gen_dashboards.py": "Grafana 대시보드 생성물 최신",
    "gen_contract.py": "계약 생성물(웹 · KMP 입력 상한 · 이메일 형식) = 서버 OpenAPI · nova_common.validate",
    "registry.py": "생성물 원장(삭제 이름 재사용 · 미등록)",
    "ledgers.py": "대장 4종 최신 · 없는 API · 권한 · 역할 · 구독 · 칸 의미",
    "naming.py": "명명 형식(표 · 칸 · 토픽 · 권한 · API · 오류 코드 · 컴포넌트) · 금지 축약 · 개념 원장(금지 별칭 · 좀비 · 미등재) · naming.md 생성 구간",
    "packs.py": "도메인 팩 경계(코어 → 팩 · 팩 ↔ 팩 import 금지)",
    "docs_index.py": "문서 인덱스 · 링크 · 한글 · 표준 판정",
    "checklist.py": "체크리스트 트리 · 자동 채움 근거 · 폼 · md 최신",
    "warehouse.py": "PRD · SPEC 스키마 · 참조 · 출고본 드리프트 · 입고/출고 대칭",
    "validate_infra.py": "k3s 렌더 · Prometheus 규칙 · 대시보드 메트릭",
    "masterplan.py": "마스터플랜 판본(정본 하나 · 이력 일치 · 보관본 봉인 해시)",
    "release.py": "릴리스 원장(초안 하나 · 목표 · 하지 않는 것 · 종료 조건 형식 · 노트)",
    "issues.py": "이슈 기록 형식 · 인덱스",
    "claude_check.py": "에이전트 · 스킬 정의 형식(frontmatter · 6절 · 판정자 쓰기 금지 · 단일 기록자 명령 위치 · 링크/명령 실재) · 편제표 최신",
    "lessons.py": "교훈 기록 형식 · 인덱스",
    "project_profile.py": "규모 프로파일(lite · product · platform) 선언 · 이유 · 날짜 · 고침 이력",
    "quick_check.py": "tasks 형식(단계 관문 · 코드 task 의 테스트 경로 · 하위 줄 커밋 없음 — 체크 안 한 task 만)",
}


def is_test(p: Path) -> bool:
    return "tests" in p.parts or p.name.startswith("test_") or p.name == "conftest.py"


def tracked() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    return [Path(x) for x in out.splitlines() if x and (ROOT / x).is_file()]


def generated_reason(p: Path, k3s: set[str]) -> str:
    rel = p.as_posix()
    if rel in k3s:
        return "gen_k3s.py 가 만든다"
    for g, why in GENERATED_GLOBS.items():
        if p.match(g):
            return why
    if p.parts[0] == "scripts":   # 생성기 · 템플릿 자신은 원천이다(템플릿이 생성물 표시 문구를 품고 있어도)
        return ""
    if p.suffix in (".css", ".kt", ".yaml", ".yml", ".md", ".html", ".sql", ".json", ".txt"):
        try:
            head = (ROOT / p).read_text(encoding="utf-8", errors="ignore")[:800]
        except OSError:
            return ""
        if any(m in head for m in MARKERS):
            m = re.search(r"(?:생성 파일|생성물:)\s*[—-]?\s*(scripts/[\w./]+|[\w.]+\.py)", head)
            return f"{m.group(1) if m else '생성기'} 가 만든다(머리 표시)"
    return ""


def k3s_outputs() -> set[str]:
    try:
        import gen_k3s
        return {Path(p).resolve().relative_to(ROOT).as_posix() for p in gen_k3s.generate()}
    except Exception:  # 생성기를 못 부르면 머리 표시로만 판정한다(보고에 적는다)
        return set()


def scope(paths: list[str]) -> dict:
    k3s = k3s_outputs()
    files, excluded = [], {}
    for p in tracked():
        if paths and not any(p.as_posix() == s.rstrip("/") or p.as_posix().startswith(s.rstrip("/") + "/") for s in paths):
            continue
        why = generated_reason(p, k3s)
        if why:
            excluded[p.as_posix()] = why
        else:
            files.append(p)
    buckets = {k: [f.as_posix() for f in files if fn(f)] for k, (_, fn) in BUCKETS.items()}
    axes = {}
    for name, (bs, gate) in AXES.items():
        fs = sorted({f for b in bs for f in buckets[b]})
        axes[name] = {"buckets": list(bs), "files": len(fs), "gate_covers": gate, "list": fs}
    return {"scope": paths or ["--all"], "tracked": len(files) + len(excluded), "audited": len(files),
            "excluded": excluded, "k3s_known": bool(k3s),
            "buckets": {k: len(v) for k, v in buckets.items()}, "axes": axes, "gates": GATES}


def render(d: dict) -> str:
    by_reason: dict[str, int] = {}
    for why in d["excluded"].values():
        by_reason[why] = by_reason.get(why, 0) + 1
    out = [f"■ 감사 분모 — 범위 {', '.join(d['scope'])}",
           f"   형상관리 파일 {d['tracked']}개 · 감사 대상 {d['audited']}개 · 제외(생성물 · 잠금 · 바이너리) {len(d['excluded'])}개",
           "   제외 사유: " + (" · ".join(f"{k} {v}" for k, v in sorted(by_reason.items())) or "없음"),
           "   " + ("gen_k3s 생성 목록으로 판정함" if d["k3s_known"] else "⚠ gen_k3s 생성 목록을 못 불러 머리 표시로만 판정함"),
           "", "■ 묶음별 파일 수"]
    out += [f"   {BUCKETS[k][0]:<16} {n}" for k, n in d["buckets"].items()]
    out += ["", "■ 축별 대상 · 이미 게이트가 보는 것(분모에서 뺀다)"]
    for name, a in d["axes"].items():
        out.append(f"   {name:<14} 파일 {a['files']:>4} · 게이트: {a['gate_covers']}")
    out += ["", "■ python nova.py lint 단계"] + [f"   {k:<18} {v}" for k, v in d["gates"].items()]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--files", metavar="축")
    a = ap.parse_args(argv)
    d = scope(a.paths)
    if a.files:
        if a.files not in d["axes"]:
            print(f"없는 축: {a.files} — {', '.join(d['axes'])}")
            return 2
        print("\n".join(d["axes"][a.files]["list"]))
        return 0
    if a.json:
        for ax in d["axes"].values():
            ax.pop("list")
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(render(d), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
