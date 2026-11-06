#!/usr/bin/env python3
"""메시지 버스 — worktree(브랜치)별 세션이 서로 질문 · 보고 · 인계를 주고받는다(ADR-008).

  python nova.py send --to main --type question --subject "<한 줄>" --body "<내용>"   (--to a,b · * 는 모두)
  python nova.py inbox [--as <이름>]          내 앞으로 온 것(main 은 전부 본다)
  python nova.py done <ID> --result "<무엇이 됐나>"   처리 끝 → 결과를 붙여 archive 로
  python nova.py outbox [--as <이름>]         내가 보낸 것과 그 결과
  python nova.py show <ID>

규칙: 메시지는 본 작업 트리의 `.collab/` 하나에만 둔다(worktree 에서도 같은 곳 — 커밋 안 함).
보낸 메시지는 고치지 않는다(회신은 --reply-to 로 새 메시지). 한 주제로 3번 넘게 오가면 main 에 escalation.
이름 = 브랜치 이름(본 작업 트리는 main). ID = UUIDv7(번호 다툼 없음).
--as 는 대리 처리용 이름 지정이다 — 인증이 아니다(같은 PC 의 세션끼리 쓰는 버스라 막을 경계가 없다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "common-py"))
from novalib import current_branch, in_linked_worktree, main_root, write  # noqa: E402
from nova_common.ids import new_id  # noqa: E402

TYPES = ("question", "report", "handoff", "escalation")
TYPE_KO = {"question": "질문", "report": "보고", "handoff": "인계", "escalation": "올림(main 판단)"}
MAX_HOP = 3


def me(cwd: Path | None = None) -> str:
    return current_branch(cwd) if in_linked_worktree(cwd) else "main"


def base(cwd: Path | None = None) -> Path:
    return main_root(cwd) / ".collab"


def parse(p: Path) -> dict:
    text = p.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}
    head = dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line)
    head["to"] = [x.strip() for x in head.get("to", "").split(",") if x.strip()]
    head["hop"] = int(head.get("hop", "1"))
    head["body"], head["path"] = m.group(2), p
    head["done"] = "\n## 결과" in m.group(2)   # 누군가 결과를 붙였다(표시용) — 받은함 판정은 done_for 로 사람마다
    head["done_by"] = re.findall(r"^## 결과 — (.+?) · ", m.group(2), re.M)
    head["archived"] = p.parent.name != "bus"
    return head


def messages(cwd: Path | None = None, *, archived: bool = False) -> list[dict]:
    b = base(cwd)
    files = list((b / "bus").glob("*.md")) + (list((b / "archive").rglob("*.md")) if archived else [])
    return sorted((m for m in map(parse, files) if m), key=lambda m: m.get("created", ""))


def find(prefix: str, cwd: Path | None = None) -> dict:
    hits = [m for m in messages(cwd, archived=True) if m.get("id", "").startswith(prefix)]
    if len(hits) != 1:
        raise SystemExit(f"✗ ID '{prefix}' 에 맞는 메시지가 {len(hits)}개 — 더 길게 적어 주세요")
    return hits[0]


def send(to: list[str], typ: str, subject: str, body: str, *, reply_to: str = "", sender: str = "", cwd: Path | None = None) -> dict:
    if typ not in TYPES:
        raise SystemExit(f"✗ type 은 {', '.join(TYPES)} 중 하나")
    if not subject.strip() or not body.strip():
        raise SystemExit("✗ --subject(요지) 와 --body(내용)는 비울 수 없다")
    sender = sender or me(cwd)
    hop, thread = 1, ""
    if reply_to:
        parent = find(reply_to, cwd)
        hop, thread = parent["hop"] + 1, parent.get("thread") or parent["id"]
    if hop > MAX_HOP and typ != "escalation":
        raise SystemExit(f"✗ 한 주제로 {MAX_HOP}번 넘게 오갔다 — 사람(main)이 판단할 자리다: --type escalation --to main")
    if typ == "escalation":
        to = ["main"]
    mid = new_id()
    now = dt.datetime.now().astimezone()
    head = {"id": mid, "from": sender, "to": ",".join(to), "type": typ, "subject": subject.strip(),
            "thread": thread or mid, "hop": str(hop), "created": now.isoformat(timespec="seconds")}
    fm = "\n".join(f"{k}: {v}" for k, v in head.items())
    safe = re.sub(r"[^\w.-]", "-", sender)
    path = base(cwd) / "bus" / f"{now:%Y%m%dT%H%M%S}_{mid[-8:]}_{safe}.md"
    write(path, f"---\n{fm}\n---\n## 요지\n{subject.strip()}\n\n## 내용\n{body.strip()}\n")
    gi = base(cwd) / ".gitignore"
    if not gi.exists():
        write(gi, "*\n")   # 버스는 커밋하지 않는다(작업 중 대화 — 기록은 history · git 기록이 남긴다)
    return parse(path)


def for_me(m: dict, name: str) -> bool:
    return name in m["to"] or "*" in m["to"]


def done_for(m: dict, name: str) -> bool:
    """name 에게 끝난 메시지인가 — 처리 상태는 받는 사람마다 따로다(전체 · 여러 명 수신에서 한 사람이 끝내도 남은 사람에게는 열려 있다)."""
    return m.get("archived", False) or name in m.get("done_by", [])


def pending(who: str, cwd: Path | None = None) -> list[dict]:
    """who 의 받은함 — 아직 who 가 끝내지 않은 것(main 은 버스 전체를 본다)."""
    return [m for m in messages(cwd) if not done_for(m, who) and (who == "main" or for_me(m, who))]


def done(prefix: str, result: str, *, actor: str = "", cwd: Path | None = None) -> Path:
    actor = actor or me(cwd)
    m = find(prefix, cwd)
    if not result.strip():
        raise SystemExit("✗ --result 없이 끝낼 수 없다 — 보낸 쪽은 '무엇이 됐는지'를 알아야 다음을 정한다")
    if not for_me(m, actor) and actor != "main":
        raise SystemExit(f"✗ 받는 사람만 끝낼 수 있다(받는 사람: {', '.join(m['to'])} · 나: {actor})")
    p: Path = m["path"]
    when = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"\n## 결과 — {actor} · {when}\n{result.strip()}\n")
    if actor != "main":
        if "*" in m["to"]:
            return p   # 모두에게 보낸 것은 각자 결과만 붙이고 버스에 남는다 — 거두는 것은 main
        if any(t not in m["done_by"] + [actor] for t in m["to"]):
            return p   # 여러 명에게 보낸 것은 받는 사람이 모두 끝내야 archive — 먼저 끝낸 사람이 남의 받은함을 비우지 않게
    dest = base(cwd) / "archive" / m.get("created", "")[:7] / p.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(p), str(dest))
    return dest


def line(m: dict) -> str:
    flag = "✔" if m["done"] else "●"
    return f"{flag} {m['id'][-8:]} [{TYPE_KO.get(m['type'], m['type'])}] {m['from']} → {', '.join(m['to'])} · {m['subject']} (홉 {m['hop']})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send")
    s.add_argument("--to", required=True)
    s.add_argument("--type", default="question", choices=TYPES)
    s.add_argument("--subject", required=True)
    s.add_argument("--body", default="")
    s.add_argument("--body-file")
    s.add_argument("--reply-to", default="")
    for n in ("inbox", "outbox"):
        sub.add_parser(n).add_argument("--as", dest="who", default="")
    sh = sub.add_parser("show")
    sh.add_argument("id")
    d = sub.add_parser("done")
    d.add_argument("id")
    d.add_argument("--result", required=True)
    d.add_argument("--as", dest="who", default="")
    a = ap.parse_args(argv)
    if a.cmd == "send":
        body = Path(a.body_file).read_text(encoding="utf-8") if a.body_file else a.body
        m = send([x.strip() for x in a.to.split(",") if x.strip()], a.type, a.subject, body, reply_to=a.reply_to)
        print(f"✓ 보냄 {m['id']} → {', '.join(m['to'])}")
        return 0
    if a.cmd == "show":
        m = find(a.id)
        print(m["path"].read_text(encoding="utf-8"))
        return 0
    if a.cmd == "done":
        print(f"✓ 끝 — {done(a.id, a.result, actor=a.who)}")
        return 0
    who = a.who or me()
    if a.cmd == "inbox":
        ms = pending(who)
        print(f"■ 받은함 — {who} · 처리할 것 {len(ms)}건" + (" (main 은 버스 전체를 본다)" if who == "main" else ""))
        for m in ms:
            print("  " + line(m))
        if not ms:
            print("  없음")
        return 0
    ms = [m for m in messages(archived=True) if m["from"] == who]
    print(f"■ 보낸함 — {who} · {len(ms)}건")
    for m in ms:
        print("  " + line(m))
        res = m["body"].split("\n## 결과", 1)
        if len(res) > 1:
            print("     결과:" + res[1].strip().replace("\n", " ")[:160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
