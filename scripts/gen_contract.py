#!/usr/bin/env python3
"""계약 생성기 — 화면 상한 = 서버 상한, 이메일 규칙은 한 곳(plan_REQ_04 P9 · REQ-261104-12-9).

  uv run python scripts/gen_contract.py          # 생성물 다시 만들기(python nova.py gen 이 부른다)
  uv run python scripts/gen_contract.py --check  # 생성물이 서버 계약과 같은지만 검사(lint)

원천:
  길이 상한  각 서비스(services.json) <pkg>.main 의 app.openapi() — 요청 스키마의 문자열 minLength · maxLength
  이메일     nova_common.validate.EMAIL_PATTERN · EMAIL_MAX(서버 Email 타입과 같은 값)
생성물(머리에 '생성 파일' 표시 — 손으로 고치지 않는다):
  web/apps/app/lib/contract.gen.ts                              LIMITS.<스키마>.<칸>.{minLength,maxLength}
  web/packages/sdk/src/validate.gen.ts                          EMAIL_PATTERN · EMAIL_MAX(모든 웹 앱 공통)
  apps/kmp/shared/src/commonMain/kotlin/kr/nova/shared/Contract.kt  Contract.<스키마>_<칸>_MIN|MAX · EMAIL_PATTERN · EMAIL_MAX
닫힘 실패: 서비스 import · OpenAPI 생성이 실패하거나 이름이 겹치면 생성하지 않고 실패한다 — 상한을 추측해 만들지 않는다(계획 §6).
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import re
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, same, write  # noqa: E402

from nova_common import catalog  # noqa: E402
from nova_common.validate import EMAIL_MAX, EMAIL_PATTERN  # noqa: E402

OUT_TS = ROOT / "web" / "apps" / "app" / "lib" / "contract.gen.ts"
OUT_SDK = ROOT / "web" / "packages" / "sdk" / "src" / "validate.gen.ts"
OUT_KT = ROOT / "apps" / "kmp" / "shared" / "src" / "commonMain" / "kotlin" / "kr" / "nova" / "shared" / "Contract.kt"
HDR = "/* 생성 파일 — scripts/gen_contract.py (원천: {src}). 직접 고치지 않는다 — 원천을 고치고 python nova.py gen. */"
KEYS = ("minLength", "maxLength")


class ContractError(Exception):
    """계약을 확정할 수 없음 — 생성하지 않고 실패한다."""


# ------------------------------------------------------------------ 읽기
def load_openapis() -> dict[str, dict]:
    """서비스마다 OpenAPI 문서. import 동안만 메모리 DB · 경고 숨김 — 끝나면 환경을 되돌린다(ledgers.scan_db 와 같은 방식)."""
    saved = dict(os.environ)
    docs: dict[str, dict] = {}
    logging.disable(logging.WARNING)          # Kafka 미설정 알림 등 — 생성 출력에 섞이지 않게
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # 게이트웨이 passthrough 의 중복 operationId 경고 — 계약과 무관
            for s in catalog.services():
                if s.db:
                    os.environ.setdefault(f"DATABASE_URL_{s.env}", "sqlite://")
                path = str(ROOT / "services" / s.name)
                if path not in sys.path:
                    sys.path.insert(0, path)
                try:
                    docs[s.name] = importlib.import_module(f"{s.package}.main").app.openapi()
                except Exception as e:  # 닫힘 — 어떤 서비스든 못 읽으면 전체를 멈춘다(상한 추측 금지)
                    raise ContractError(f"서비스 {s.name} 의 OpenAPI 를 읽지 못했습니다: {type(e).__name__}: {e}") from e
    finally:
        logging.disable(logging.NOTSET)
        os.environ.clear()
        os.environ.update(saved)
    return docs


def _string_limits(prop: dict) -> dict:
    """문자열 칸의 길이 제약 — str | None 은 anyOf 안의 string 쪽에서 읽는다."""
    for p in (prop, *prop.get("anyOf", [])):
        if p.get("type") == "string":
            got = {k: p[k] for k in KEYS if k in p}
            if got:
                return got
    return {}


def collect(docs: dict[str, dict]) -> dict[str, dict]:
    """{스키마: {service, fields: {칸: {minLength?, maxLength?}}}} — 길이 제약이 있는 칸만, 스키마 이름순."""
    out: dict[str, dict] = {}
    for svc in sorted(docs):
        for name, schema in docs[svc].get("components", {}).get("schemas", {}).items():
            fields = {f: lim for f, prop in schema.get("properties", {}).items() if (lim := _string_limits(prop))}
            if not fields:
                continue
            if name in out:
                raise ContractError(f"스키마 이름 {name} 이 서비스 {out[name]['service']} · {svc} 에 겹칩니다 — 한쪽 이름을 바꾸세요")
            out[name] = {"service": svc, "fields": fields}
    return dict(sorted(out.items()))


# ------------------------------------------------------------------ 이름 · 그리기
def _snake(s: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s).upper()


def const_name(schema: str, field: str, kind: str) -> str:
    """ItemIn.name → ITEM_NAME_MAX — 요청 스키마 끝의 In 은 뗀다(ItemPatch → ITEM_PATCH)."""
    base = schema[:-2] if schema.endswith("In") and len(schema) > 2 else schema
    return f"{_snake(base)}_{_snake(field)}_{kind}"


def _kt_str(s: str) -> str:
    """Kotlin 일반 문자열 리터럴 — \\ · " · $(문자열 템플릿) 를 이스케이프한다."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$") + '"'


def _sources(limits: dict) -> str:
    svcs = sorted({v["service"] for v in limits.values()})
    return "서비스 OpenAPI(" + ", ".join(svcs) + ")" if svcs else "서비스 OpenAPI"


def render_ts_limits(limits: dict) -> str:
    lines = [HDR.format(src=_sources(limits)),
             "/** 입력 길이 상한 — 서버 요청 스키마(pydantic Field min_length · max_length) 그대로. 화면에 숫자를 쓰지 않고 이것을 쓴다. */",
             "export const LIMITS = {"]
    for name, v in limits.items():
        fields = ", ".join(f"{f}: {{ " + ", ".join(f"{k}: {lim[k]}" for k in KEYS if k in lim) + " }"
                           for f, lim in v["fields"].items())
        lines.append(f"  {name}: {{ {fields} }},  // {v['service']}")
    lines.append("} as const;")
    return "\n".join(lines) + "\n"


def render_ts_validate() -> str:
    return "\n".join([
        HDR.format(src="nova_common/validate.py"),
        "/** 이메일 형식 — 서버 Email 타입과 같은 정규식(앞뒤 공백을 뗀 값에 쓴다). */",
        f"export const EMAIL_PATTERN = {json.dumps(EMAIL_PATTERN)};",
        "/** 이메일 전체 길이 상한(RFC 5321) */",
        f"export const EMAIL_MAX = {EMAIL_MAX};",
    ]) + "\n"


def render_kt(limits: dict) -> str:
    consts: dict[str, int] = {}
    body = []
    for name, v in limits.items():
        body.append(f"    // {name} ({v['service']})")
        for f, lim in v["fields"].items():
            for key, kind in (("minLength", "MIN"), ("maxLength", "MAX")):
                if key not in lim:
                    continue
                c = const_name(name, f, kind)
                if c in consts:
                    raise ContractError(f"Kotlin 상수 이름 {c} 이 겹칩니다 — 스키마 이름을 바꾸세요")
                consts[c] = lim[key]
                body.append(f"    const val {c} = {lim[key]}")
    return "\n".join([
        HDR.format(src=_sources(limits) + " · nova_common/validate.py"),
        "package kr.nova.shared",
        "",
        "/** 서버 계약 — 입력 길이 상한(서버 요청 스키마 그대로) · 이메일 형식. 화면에 숫자를 쓰지 않고 이것을 쓴다. */",
        "object Contract {",
        *body,
        "    /** 이메일 형식 — 서버 Email 타입과 같은 정규식(앞뒤 공백을 뗀 값에 쓴다) */",
        f"    const val EMAIL_PATTERN = {_kt_str(EMAIL_PATTERN)}",
        f"    const val EMAIL_MAX = {EMAIL_MAX}",
        "}",
    ]) + "\n"


def build(docs: dict[str, dict] | None = None) -> dict[Path, str]:
    limits = collect(load_openapis() if docs is None else docs)
    return {OUT_TS: render_ts_limits(limits), OUT_SDK: render_ts_validate(), OUT_KT: render_kt(limits)}


def stale(outs: dict[Path, str]) -> list[str]:
    return [f"생성물이 서버 계약과 다름: {_rel(p)} — python nova.py gen 실행" for p, text in outs.items() if not same(p, text)]


def _rel(p: Path) -> str:
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def main(check: bool) -> int:
    try:
        outs = build()
    except ContractError as e:
        print("✗ " + str(e))
        return 1
    if check:
        errs = stale(outs)
        if errs:
            print("\n".join("✗ " + e for e in errs))
            return 1
    else:
        for path, text in outs.items():
            if not same(path, text):
                write(path, text)
                print("생성", _rel(path))
    print(f"✓ 계약 생성물 최신 — {len(outs)}개(길이 상한 · 이메일 형식)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
