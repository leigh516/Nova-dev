---
description: 저장(psg05 이름 /git-save) — 바꾼 파일을 명시해 담고 한국어로 커밋한 뒤 git 기록을 남기고 푸시한다. 민감 파일과 생성물 손수정을 먼저 확인한다
argument-hint: "<커밋 요약(한국어)>" [범위]
---

# /git-save — 커밋 · 기록 · 푸시

인자: `$ARGUMENTS`
규칙: [docs/conventions/git.md](../../docs/conventions/git.md) · CLAUDE.md 문서 규칙 4

## 절차
1. **본 작업 트리(main)에서** 한다 — worktree 안이면 커밋만 하고 기록 · 푸시는 main 이 `/converge` 뒤에 한다(단일 기록자)
2. `git status -s` 로 바뀐 것을 본다
   - 민감 파일(`.env` · `*.key` · `*.pem` · `id_rsa` · 비밀번호가 든 설정)이 있으면 **멈춘다** — 담지 않는다
   - 생성물만 바뀌었는데 원천이 안 바뀌었으면 손수정이다 → 원천을 고치고 `python nova.py gen`
   - 이번 일과 상관없는 파일은 담지 않는다
3. 담기는 **파일을 명시해서** `git add <경로…>`(`git add -A` 는 위 확인을 마친 뒤에만)
4. `python nova.py check` 가 녹색인지(빨강이면 커밋하지 않는다)
5. 커밋 — `feat(범위): 한국어 요약`(type 접두어는 git.md), 본문은 무엇을 · 왜, 끝에 협업 꼬리말
6. `uv run python scripts/git_record.py "<요약>"` — 범위를 주지 않으면 지난 기록 뒤 커밋 전부(커밋에 민감 파일이 있으면 경고한다) → 기록 파일 커밋
7. `git push origin main` — 태그 원격 푸시 · 강제 푸시는 사용자 확인 뒤에만

## 하지 않는 것
- 민감 파일 담기 · 훅 건너뛰기(`--no-verify`) · 확인 없는 강제 푸시 · 영어 커밋 메시지
