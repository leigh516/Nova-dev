#!/usr/bin/env python3
"""task 묶음 판정 — tasks 문서를 읽어 '지금 동시에 해도 되는 task 묶음'을 고른다(읽기 전용 · 문서를 고치지 않는다).

  uv run python scripts/task_batch.py <tasks 파일> --max N [--skip ID,…]     다음 묶음 + 남은 열린 task 수(한국어)

종료 코드(호출자 task-run 이 문구를 읽지 않고 코드로 가른다):
  0  다음 묶음을 냈다 / 열린 task 가 없어 '끝'
  1  파일 없음 · 인자 오류(--max 가 1 미만)
  2  막힘 — 열린 task 는 있으나 선행이 끝나지 않아 하나도 못 고름
  3  형식 이상 — 최상위 체크박스 줄에서 task ID 나 상태를 읽지 못함(줄 번호는 stderr). 자동 진행은 멈춘다
  4  대기 — `--skip` 으로 뺀(사람 판단 대기) task 때문에만 묶음이 비었음. 막힘(2)과 달리 질문에 답이 오면 이어진다
     (`--skip ID[,ID…]` — 열린 채로 남아 단계 관문 · 선행 판정에는 센다)

`/task-run --auto` 가 병렬 배치 전에 부른다(plan_REQ_08 §1 · §6). 판정 원칙: **의심스러우면 겹침(혼자 한 묶음)**.
- task 줄 = `- [ ]` / `- [x]` + ID `T<NN>-<단계>.<순번>`(🆕 줄 포함). 들여쓴 하위 줄은 본문으로 붙고 상태에 쓰지 않는다
- 취소 = ID 앞이나 줄 머리에 `~~` 취소선. 단계 = `## <n>단계` 머리(그 밖 절의 task 는 단계 없음)
- 겹침 = 같은 경로이거나 한쪽이 다른 쪽의 폴더. 글롭(`*` `?` `[`)은 글롭 앞 폴더 전체로 본다
- 경로가 없거나 `파일:` 줄에서 해석 못 한 조각이 있는 task 는 모두와 겹침(혼자 한 묶음)
- 묶음 = 선행이 끝난 열린 task 중 가장 낮은 단계 것만, 문서 순서로 훑어 겹치지 않으면 넣는다(탐욕)
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ID = r"T\d+-\d+\.\d+"
# 들여쓰지 않은 체크박스 줄(상태 칸은 아무 글자나 받아 두고 뒤에서 거른다 — 모양 이상을 놓치지 않으려고)
CHECK_RE = re.compile(r"^[-*+]\s+(~~)?\s*\[(.)\]\s*(.*)$")
ID_PREFIX_RE = re.compile(rf"^(?P<pre>(?:~~|\s|🆕)*)(?P<id>{ID})")
STAGE_RE = re.compile(r"^##\s+(\d+)단계")
PREREQ_RE = re.compile(r"선행\s*:\s*([^)\n]*)")
FILE_LINE_RE = re.compile(r"(?:^|[\s·])파일[:：]")
# 경로로 보는 파일 확장자
EXTS = ("py", "md", "json", "jsonl", "ts", "tsx", "js", "kt", "kts", "yml", "yaml", "sh", "txt", "html", "css", "toml", "xml", "gradle", "properties", "png")
ASCII_RUN_RE = re.compile(r"[A-Za-z0-9_./\-*?\[\]]+")
GLOB_CHARS = "*?["


@dataclass
class Task:
    id: str
    state: str  # open | done | cancelled
    body: str
    stage: int | None


def parse_tasks_checked(text: str) -> tuple[list[Task], list[tuple[int, str]]]:
    """tasks 문서 → (task 목록, 형식 이상 줄 [(줄 번호, 줄)]). 이상 = 최상위 체크박스 줄에서 ID · 상태를 못 읽음."""
    tasks: list[Task] = []
    anomalies: list[tuple[int, str]] = []
    stage: int | None = None
    cur: Task | None = None
    for no, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            m = STAGE_RE.match(line)
            stage = int(m.group(1)) if m else None
            cur = None
            continue
        tm = CHECK_RE.match(line)
        if tm:
            rest = tm.group(3)
            im = ID_PREFIX_RE.match(rest)
            if im and tm.group(2) in " xX":
                if tm.group(1) or "~~" in im.group("pre"):
                    state = "cancelled"
                else:
                    state = "done" if tm.group(2) in "xX" else "open"
                cur = Task(id=im.group("id"), state=state, body=rest, stage=stage)
                tasks.append(cur)
            else:
                anomalies.append((no, line))
                cur = None
            continue
        if cur is not None and line[:1] in (" ", "\t"):
            cur.body += "\n" + line.strip()
        elif line.strip():
            cur = None  # 들여쓰지 않은 다른 줄 — 앞 task 의 본문이 끝났다
    return tasks, anomalies


def parse_tasks(text: str) -> list[Task]:
    """tasks 문서 → task 목록(문서 순서). 하위 들여쓰기 줄은 본문에 붙는다. 형식 이상 줄은 parse_tasks_checked 로 본다."""
    return parse_tasks_checked(text)[0]


def _norm(p: str) -> str:
    p = p.strip().strip("`").replace("\\", "/").split("::")[0]
    while p.startswith("./"):
        p = p[2:]
    return p


def _expand_braces(tok: str) -> list[str]:
    """`src/{a,b}.py` → [`src/a.py`, `src/b.py`] (중첩은 안쪽부터)."""
    m = re.search(r"\{([^{}]*)\}", tok)
    if not m:
        return [tok]
    out: list[str] = []
    for alt in m.group(1).split(","):
        out += _expand_braces(tok[: m.start()] + alt.strip() + tok[m.end():])
    return out


def _path_like(run: str, trusted: bool) -> bool:
    """trusted(백틱 안 · `파일:` 줄)는 슬래시나 알려진 확장자면 경로, 그 밖은 슬래시 + (확장자 · 끝 `/` · 글롭)일 때만."""
    if not re.search(r"[A-Za-z0-9]", run) and not any(c in run for c in GLOB_CHARS):
        return False
    slash = "/" in run
    last = run.rstrip("/").rsplit("/", 1)[-1]
    ext = "." in last and last.rsplit(".", 1)[-1] in EXTS
    if trusted:
        return slash or ext
    return slash and (ext or run.endswith("/") or any(c in run for c in GLOB_CHARS))


def _scan(text: str, trusted: bool) -> tuple[list[str], list[str]]:
    """글에서 경로 후보를 뽑는다 → (경로들, 경로로 못 읽은 영숫자 조각들)."""
    paths: list[str] = []
    left: list[str] = []
    for tok in text.split():
        for exp in _expand_braces(tok):
            exp = re.sub(r"::[A-Za-z0-9_\[\]\-]+", "", exp)          # tests/x.py::이름
            exp = re.sub(r":\d+(?:-\d+)?(?![A-Za-z0-9])", "", exp)   # a.py:12 · a.py:12-30
            for run in ASCII_RUN_RE.findall(exp):
                run = run.rstrip(".")
                if not run:
                    continue
                if _path_like(run, trusted):
                    paths.append(run)
                elif re.search(r"[A-Za-z0-9]", run):
                    left.append(run)
    return paths, left


def _extract(body: str) -> tuple[list[str], bool]:
    """본문 → (경로 목록, 불확실 여부). 불확실 = `파일:` 줄에 경로로 해석 못 한 조각이 남음."""
    body = body.replace("\\", "/")
    paths: list[str] = []
    uncertain = False
    for line in body.splitlines():
        m = FILE_LINE_RE.search(line)
        head, tail = (line[: m.start()], line[m.end():]) if m else (line, "")
        # 머리: 백틱 안은 신뢰, 밖은 엄격
        for i, part in enumerate(head.split("`")):
            paths += _scan(part, trusted=(i % 2 == 1))[0]
        if m:
            tail = tail.replace("`", " ")
            while True:  # 괄호 꼬리 `(신규)` 는 설명 — 안의 경로만 건진다
                inner = re.search(r"\(([^()]*)\)", tail)
                if not inner:
                    break
                paths += _scan(inner.group(1), trusted=False)[0]
                tail = tail[: inner.start()] + " " + tail[inner.end():]
            found, left = _scan(tail, trusted=True)
            paths += found
            if left:
                uncertain = True
    out: list[str] = []
    for p in paths:
        n = _norm(p)
        if n and n not in out:
            out.append(n)
    return out, uncertain


def task_paths(task: Task | str) -> list[str]:
    """본문에서 건드릴 경로를 모은다(백틱 안 · `파일:` 줄 · 백틱 밖 `a/b.py`·`dir/` 꼴). 없으면 빈 목록."""
    return _extract(task if isinstance(task, str) else task.body)[0]


def paths_uncertain(task: Task | str) -> bool:
    """`파일:` 줄에 경로로 해석 못 한 조각이 남았나(그러면 겹침 판정에서 혼자 한 묶음으로 본다)."""
    return _extract(task if isinstance(task, str) else task.body)[1]


def _key(p: str) -> str:
    """겹침 비교용 정규형 — 글롭은 글롭이 처음 나오는 마디 앞의 폴더로 낮춘다(빈 문자열 = 전체)."""
    segs = [s for s in _norm(p).rstrip("/").split("/") if s not in ("", ".")]
    keep: list[str] = []
    for s in segs:
        if any(c in s for c in GLOB_CHARS):
            break
        keep.append(s)
    return "/".join(keep).casefold()


def overlaps(paths_a: list[str], paths_b: list[str]) -> bool:
    """두 task 의 경로 집합이 겹치나. 같은 경로 · 폴더 포함 · 글롭이면 겹침, 경로가 없는 쪽은 모두와 겹침."""
    if not paths_a or not paths_b:
        return True
    for a in map(_key, paths_a):
        for b in map(_key, paths_b):
            if not a or not b or a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                return True
    return False


def _prereqs(task: Task) -> list[str]:
    ids: list[str] = []
    for chunk in PREREQ_RE.findall(task.body):
        ids += re.findall(ID, chunk)
    return [i for i in ids if i != task.id]


def unknown_prereqs(tasks: list[Task]) -> list[tuple[str, str]]:
    """열린 task 가 가리키는 선행 중 이 문서에 없는 ID [(task, 선행)] — 막지는 않으나 오타일 수 있어 알린다."""
    known = {t.id for t in tasks}
    return [(t.id, p) for t in tasks if t.state == "open" for p in _prereqs(t) if p not in known]


def _candidates(tasks: list[Task]) -> list[Task]:
    """단계 관문 — 가장 낮은 단계에 열린 task 가 남아 있으면 그 단계만, 모두 끝났으면 단계 없는 task."""
    opens = [t for t in tasks if t.state == "open"]
    staged = [t.stage for t in opens if t.stage is not None]
    if staged:
        low = min(staged)
        return [t for t in opens if t.stage == low]
    return [t for t in opens if t.stage is None]


def _effective_paths(t: Task) -> list[str]:
    return [] if paths_uncertain(t) else task_paths(t)


def next_batch(tasks: list[Task], max_parallel: int, skip: frozenset[str] | set[str] = frozenset()) -> list[str]:
    """선행이 끝난 열린 task 를 겹침 없이 최대 max_parallel 개 고른다(task ID 목록).

    skip 의 task 는 묶음에서만 뺀다 — 열린 채로 남아 단계 관문 · 선행 판정에는 그대로 센다(사람 판단 대기 task 가
    있다고 다음 단계가 앞당겨지거나 그 task 에 달린 뒤 task 가 풀리지 않게).
    """
    if max_parallel < 1:
        raise ValueError("max_parallel 은 1 이상이어야 한다")
    # 취소된 task 는 더 끝나지 않으므로 선행을 막지 않는다. 이 문서에 없는 ID 는 판단할 수 없어 막지 않는다
    known = {t.id for t in tasks}
    unfinished = {t.id for t in tasks if t.state == "open"}
    chosen: list[Task] = []
    for t in _candidates(tasks):
        if len(chosen) >= max_parallel:
            break
        if t.id in skip:
            continue
        if any(p in unfinished and p in known for p in _prereqs(t)):
            continue
        paths = _effective_paths(t)
        if any(overlaps(paths, _effective_paths(c)) for c in chosen):
            continue
        chosen.append(t)
    return [t.id for t in chosen]


def pending_ids(tasks: list[Task]) -> list[str]:
    """재개용 — 체크된 · 취소된 task 를 건너뛴 열린 task ID(문서 순서)."""
    return [t.id for t in tasks if t.state == "open"]


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="tasks 문서에서 겹치지 않는 다음 task 묶음을 고른다")
    ap.add_argument("tasks_file", help="tasks 문서 경로")
    ap.add_argument("--max", type=int, required=True, dest="max_parallel", help="한 묶음의 최대 task 수")
    ap.add_argument("--skip", default="", help="묶음에서 뺄 열린 task ID(쉼표 구분 — 사람 판단 대기 중인 것)")
    args = ap.parse_args(argv)
    path = Path(args.tasks_file)
    if not path.is_file():
        print(f"오류: tasks 파일을 찾을 수 없습니다 — {path}", file=sys.stderr)
        return 1
    if args.max_parallel < 1:
        print("오류: --max 는 1 이상이어야 합니다", file=sys.stderr)
        return 1
    tasks, anomalies = parse_tasks_checked(path.read_text(encoding="utf-8"))
    if anomalies:
        for no, line in anomalies:
            print(f"형식 이상: {path.name}:{no} — task ID 나 상태를 읽을 수 없음 — {line.strip()[:80]}", file=sys.stderr)
        print(f"형식 이상 {len(anomalies)}줄 — 자동 진행을 멈춥니다(문서를 고친 뒤 다시)", file=sys.stderr)
        return 3
    for tid, pre in unknown_prereqs(tasks):
        print(f"경고: {tid} 의 선행 {pre} 은 이 문서에 없어 막지 않습니다(오타인지 확인)", file=sys.stderr)
    remaining = len(pending_ids(tasks))
    if remaining == 0:
        print("끝 — 열린 task 없음")
        return 0
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    open_ids = set(pending_ids(tasks))
    for sid in sorted(skip - open_ids):
        print(f"경고: --skip 의 {sid} 은 열린 task 가 아니라 무시합니다(오타이거나 이미 끝남)", file=sys.stderr)
    batch = next_batch(tasks, args.max_parallel, skip)
    if not batch and skip and next_batch(tasks, args.max_parallel):
        # 제외 때문에만 비었다 — 막힘이 아니라 사람 판단을 기다리는 상태
        print(f"대기 — 사람 판단 대기 task 만 남음({' · '.join(sorted(skip))}) — 남은 열린 task {remaining}개")
        return 4
    if not batch:
        print(f"막힘 — 다음 묶음 없음(선행이 끝나지 않음) — 남은 열린 task {remaining}개")
        return 2
    print(f"다음 묶음 {len(batch)}개: {' · '.join(batch)} — 남은 열린 task {remaining}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
