"""계약 생성기(scripts/gen_contract.py) — 화면 상한 = 서버 상한, 이메일 규칙 한 곳(plan_REQ_04 P9 · T04-4.03).

가짜 OpenAPI 로 추출 · 이름 규칙 · 충돌을, 실제 서비스로 '서버 값 그대로'를, 임시 파일로 --check 불일치 검출을 본다.
"""
import json
import re

import pytest

import gen_contract as gc
from nova_common.validate import EMAIL_MAX, EMAIL_PATTERN


def fake_openapi(**schemas):
    return {"components": {"schemas": schemas}}


ITEM_IN = {"properties": {
    "name": {"type": "string", "minLength": 1, "maxLength": 100},
    "memo": {"anyOf": [{"type": "string", "maxLength": 2000}, {"type": "null"}]},
    "count": {"type": "integer", "maximum": 9},
}}
NO_LIMITS = {"properties": {"msg": {"type": "string"}, "loc": {"type": "array"}}}


def test_collect_reads_string_limits_including_nullable():
    limits = gc.collect({"sample": fake_openapi(ItemIn=ITEM_IN, ValidationError=NO_LIMITS)})
    assert limits == {"ItemIn": {"service": "sample", "fields": {"name": {"minLength": 1, "maxLength": 100},
                                                                  "memo": {"maxLength": 2000}}}}


def test_collect_rejects_same_schema_name_in_two_services():
    with pytest.raises(gc.ContractError, match="ItemIn"):
        gc.collect({"a": fake_openapi(ItemIn=ITEM_IN), "b": fake_openapi(ItemIn=ITEM_IN)})


def test_const_names():
    assert gc.const_name("ItemIn", "name", "MAX") == "ITEM_NAME_MAX"
    assert gc.const_name("ItemPatch", "memo", "MIN") == "ITEM_PATCH_MEMO_MIN"
    assert gc.const_name("LoginIn", "displayName", "MAX") == "LOGIN_DISPLAY_NAME_MAX"


def test_kotlin_const_collision_is_an_error():
    limits = gc.collect({"s": fake_openapi(ItemIn=ITEM_IN, Item=ITEM_IN)})
    with pytest.raises(gc.ContractError, match="ITEM_NAME_MIN"):   # 이름순 Item → ItemIn, 첫 겹침은 name 의 MIN
        gc.render_kt(limits)


def test_ts_limits_render():
    text = gc.render_ts_limits(gc.collect({"sample": fake_openapi(ItemIn=ITEM_IN)}))
    assert text.splitlines()[0].startswith("/* 생성 파일 — scripts/gen_contract.py")
    assert "export const LIMITS = {" in text and "} as const;" in text
    assert "ItemIn: { name: { minLength: 1, maxLength: 100 }, memo: { maxLength: 2000 } }," in text


def test_ts_validate_keeps_pattern_exact():
    text = gc.render_ts_validate()
    assert text.splitlines()[0].startswith("/* 생성 파일 — scripts/gen_contract.py")
    m = re.search(r"export const EMAIL_PATTERN = (\".*\");", text)
    assert m and json.loads(m.group(1)) == EMAIL_PATTERN   # JSON 문자열 = JS 문자열 리터럴
    assert f"export const EMAIL_MAX = {EMAIL_MAX};" in text


def kotlin_unescape(lit: str) -> str:
    """Kotlin 일반 문자열 리터럴 해석(테스트용) — \\\\ · \\$ · \\\" 만 쓴다."""
    return re.sub(r"\\(.)", lambda m: m.group(1), lit)


def test_kotlin_render_and_pattern_escape():
    text = gc.render_kt(gc.collect({"sample": fake_openapi(ItemIn=ITEM_IN)}))
    assert text.splitlines()[0].startswith("/* 생성 파일 — scripts/gen_contract.py")
    assert "package kr.nova.shared" in text and "object Contract {" in text
    assert "const val ITEM_NAME_MIN = 1" in text and "const val ITEM_NAME_MAX = 100" in text
    assert "const val ITEM_MEMO_MAX = 2000" in text and "ITEM_MEMO_MIN" not in text
    m = re.search(r'const val EMAIL_PATTERN = "(.*)"', text)
    assert m and "$" not in m.group(1).replace("\\$", "")          # 문자열 템플릿으로 읽히는 $ 가 없다
    assert kotlin_unescape(m.group(1)) == EMAIL_PATTERN
    assert f"const val EMAIL_MAX = {EMAIL_MAX}" in text


def test_real_services_give_server_values():
    """서버 모델(sample ItemIn)의 상한이 그대로 나온다 — 화면 상한 = 서버 상한."""
    limits = gc.collect(gc.load_openapis())   # 서비스 경로는 load_openapis 가 잡는다
    from sample.items import ItemIn

    assert limits["ItemIn"]["fields"]["name"]["maxLength"] == ItemIn.model_fields["name"].metadata[-1].max_length


def test_check_detects_stale_output(tmp_path):
    good, stale, missing = tmp_path / "a.ts", tmp_path / "b.ts", tmp_path / "c.ts"
    good.write_text("같음\n", encoding="utf-8")
    stale.write_text("옛것\n", encoding="utf-8")
    errs = gc.stale({good: "같음\n", stale: "새것\n", missing: "새것\n"})
    assert len(errs) == 2 and any("b.ts" in e for e in errs) and any("c.ts" in e for e in errs)


def test_repo_outputs_are_current():
    assert gc.main(check=True) == 0
