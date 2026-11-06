"""토픽 카탈로그 정합성 — 서비스가 발행 · 구독하는 모든 토픽이 infra/k3s/base/kafka-topics.txt 에 있어야 한다.

Kafka 는 auto.create.topics.enable=false 라서, 카탈로그에 없는 토픽을 발행하면 실패하고 아웃박스가 막힌다.
f-string 토픽은 정적으로 검사할 수 없으므로 금지한다(명시적 매핑 사용).
"""
import re
from pathlib import Path

from nova_common import catalog

import naming

ROOT = Path(__file__).resolve().parents[1]
LINES = [ln.split() for ln in (ROOT / "infra/k3s/base/kafka-topics.txt").read_text(encoding="utf-8").splitlines()
         if ln.strip() and not ln.startswith("#")]
CATALOG = {ln[0] for ln in LINES}
SOURCES = [p for p in (ROOT / "services").rglob("*.py")
           if "tests" not in p.parts and ".pytest_cache" not in p.parts and "_template" not in p.parts]
EMIT = re.compile(r"svc\.emit\(\s*\w+\s*,\s*(f?)\"([^\"]+)\"")
ON = re.compile(r"@svc\.on\(\s*\"([^\"]+)\"")
# 토픽 모양 문자열의 도메인 = 카탈로그 첫 마디 ∪ 서비스 이름
DOMAINS = sorted({t.split(".")[0] for t in CATALOG} | {n.replace("-", "_") for n in catalog.names()})
TOPIC_LITERAL = re.compile(r"[\"']((?:" + "|".join(map(re.escape, DOMAINS)) + r")\.[a-z_]+\.[a-z_]+)[\"']")
# f-string 문자열 전부(접두어 f · rf · fr, 따옴표 둘 다) — 상수 정의(T_X = f"{d}.item.created")든 호출 인자든 같이 본다
FSTRING = re.compile(r"(?<![A-Za-z0-9_])(?:[rR]?[fF]|[fF][rR])(\"[^\"\n]*\"|'[^'\n]*')")
TOPIC_SHAPE = re.compile(r"^[a-z_]+\.[a-z_]+\.[a-z_]+$")
NAME = naming.pattern("topic", ROOT)  # 형식 정규식은 명명 규약 선언 정본(registry/naming.json) 하나에만


def _scan(rx):
    for p in SOURCES:
        for m in rx.finditer(p.read_text(encoding="utf-8")):
            yield p.relative_to(ROOT).as_posix(), m


def test_catalog_lines_well_formed():
    for ln in LINES:
        assert len(ln) == 3 and NAME.match(ln[0]) and ln[1].isdigit() and ln[2].isdigit(), f"형식: <도메인>.<개체>.<과거형> <파티션> <보존일> — {ln}"
    assert len(CATALOG) == len(LINES), "토픽 중복"


def topic_shaped_fstrings(text: str) -> list[str]:
    """f-string 중 자리표시({…})를 채우면 토픽 모양(<a>.<b>.<c>)이 되는 것 — 정적으로 카탈로그와 대조할 수 없다."""
    out = []
    for m in FSTRING.finditer(text):
        body = m.group(1)[1:-1]
        if "{" in body and TOPIC_SHAPE.match(re.sub(r"\{[^{}]*\}", "x", body)):
            out.append(m.group(0))
    return out


def test_fstring_detector_catches_constants_and_calls():
    """회귀 — 예전 검사는 svc.emit(s, f"…") 직접 인자만 봐서 상수로 빼 둔 f-string 토픽을 놓쳤다."""
    assert topic_shaped_fstrings('T_CREATED = f"{DOMAIN}.item.created"')
    assert topic_shaped_fstrings("svc.emit(s, f'sample.{kind}.created', x)")
    assert topic_shaped_fstrings('T = rf"{d}.{e}.updated"')
    assert not topic_shaped_fstrings('key = f"sample:{T_UPDATED}:{item.id}"')      # 멱등 키 — 토픽 모양 아님
    assert not topic_shaped_fstrings('T_CREATED = "sample.item.created"')          # 정적 문자열은 카탈로그 대조로 본다


def test_no_dynamic_topic_names():
    dynamic = [f"{p}: {m.group(2)}" for p, m in _scan(EMIT) if m.group(1)]
    dynamic += [f"{p.relative_to(ROOT).as_posix()}: {x}" for p in SOURCES for x in topic_shaped_fstrings(p.read_text(encoding="utf-8"))]
    assert not dynamic, f"f-string 토픽 금지(명시적 매핑으로): {dynamic}"


def test_every_emitted_topic_is_in_catalog():
    missing = sorted({f"{m.group(2)} ({p})" for p, m in _scan(EMIT) if not m.group(1) and m.group(2) not in CATALOG})
    assert not missing, f"카탈로그에 없는 발행 토픽: {missing}"


def test_every_consumed_topic_is_in_catalog():
    missing = sorted({f"{m.group(1)} ({p})" for p, m in _scan(ON) if m.group(1) not in CATALOG})
    assert not missing, f"카탈로그에 없는 구독 토픽: {missing}"


def test_every_topic_shaped_literal_is_in_catalog():
    """변수로 넘기는 토픽(상수 · 매핑표)도 잡기 위해, 서비스 코드의 토픽 모양 문자열 전부를 대조한다."""
    missing = sorted({f"{m.group(1)} ({p})" for p, m in _scan(TOPIC_LITERAL) if m.group(1) not in CATALOG})
    assert not missing, f"카탈로그에 없는 토픽 문자열: {missing}"
