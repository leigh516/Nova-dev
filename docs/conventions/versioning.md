# 판본 규약 — 번호 · 정식 릴리스 · 마스터플랜 연결

> 결정: [REQ-261105-06](../requirement/requirement_261105_06.md) · [ADR-008](../adr/ADR-008-parallel-bus-release.md). 도구: `scripts/release.py`(`python nova.py release …`) · 번호 규칙 코드 `scripts/versions.py` · 원장 [docs/releases](../releases/README.md).
> 참고: [Semantic Versioning 2.0.0](https://semver.org/lang/ko/) · [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) · [Conventional Commits](https://www.conventionalcommits.org/ko/v1.0.0/).

## 1. 무엇이 '공개 API' 인가
Nova 의 판본 번호는 **복제본(Nova 로 만든 프로젝트)이 받는 것**이 깨지는지로 정한다. 공개 API 는 셋이다.

| 공개 API | 어디 | 깨짐의 예 |
|---|---|---|
| 공통부 | `scripts/upstream.py` 의 `COMMON` 목록(공통 라이브러리 · 스크립트 · 명령 · 스킬 · 에이전트 · 규약 · 토큰 틀 · 웹/모바일 공통 부품) | 함수 · 모듈 · 부품의 이름이나 서명을 바꾼다, 경로를 옮기거나 지운다 |
| 명령 | `python nova.py <명령>` · `.claude/commands/*.md` | 명령 · 하위 명령 · 옵션을 지우거나 뜻을 바꾼다 |
| 원장 JSON 형식 | `docs/releases/releases.json` · `registry/*.json` · `nova.project.json` · `docs/product/*.json` | 칸을 지우거나 뜻을 바꿔 복제본의 기존 파일이 검사에 걸린다 |

## 2. 번호 올리기 — MAJOR.MINOR.PATCH
| 올림 | 조건(하나라도) | 커밋 신호 |
|---|---|---|
| **MAJOR** | 받으면 깨진다 — 손 마이그레이션이 필요하다 · 명령/경로를 지웠다 · 복제본이 손대지 않은 파일인데도 `upstream plan` 에서 surface 가 생긴다 | `type!:` · 본문 `BREAKING CHANGE:` |
| **MINOR** | 호환되는 추가 — 새 명령 · 새 칸(선택) · 새 공통 부품 | `feat` |
| **PATCH** | 호환되는 수정 — 결함 · 문서 · 내부 정리 | `fix` · `docs` · `refactor` · `test` · `chore` … |

- `python nova.py release suggest` 가 마지막 **정식** 태그 뒤 커밋 제목을 세어 **최소 올림**을 낸다. `release ship` 은 원장 판본이 그보다 낮으면 거부한다(높이는 것은 사람 판단 — 커밋 신호가 놓친 깨짐이 있으면 올린다)
- 커밋 type 을 정확히 쓰는 것이 번호를 지킨다 — [git 규약](git.md)

## 3. 0.x 와 1.0.0
- **0.x 동안은 깨짐도 0.y 올림**이다(SemVer §4 — 초기 개발 단계). `0.y` 가 오르면 깨졌을 수 있으니 노트의 '복제본이 받을 때' 절을 꼭 읽는다
- **1.0.0 = 첫 복제본이 운영에 들어갈 때.** 그때부터는 깨짐 = MAJOR 를 지킨다

## 4. 사전 판본 — `X.Y.Z-rc.N`
- 정식 전에 복제본 하나에서 미리 받아 보는 판본. 원장에 `0.2.0-rc.1` 로 따로 draft → ship → `release publish` 하면 GitHub Release 가 **prerelease** 로 나간다
- rc 는 '최신 정식'으로 치지 않는다 — 새 프로젝트 시작(`new-project` · `init`) · `upstream` 의 기본 대상 · `release suggest` 의 기준에서 빠진다

## 5. 판본을 내는 기준
판본마다 원장에 셋을 적는다. 셋이 없으면 판본이 끝없이 자란다.
| 칸 | 뜻 |
|---|---|
| 범위 | `goal`(300자 안) · `reqs`(묶인 요구) · `not_doing`(하지 않는 것) |
| 종료 조건 | `exit` 1~7개 — 한 번 돌리거나 한 번 보고 답이 나오는 것. 모두 녹색이면 낸다([plans README §5](../plans/README.md)) |
| 목표일 | `due`(선택 · YYYY-MM-DD). 판본 주기는 두지 않는다(사용자 결정 2026-11-05) — 적었다면 넘길 때 남은 범위를 **다음 판본으로** 옮기고 이번 것을 낸다 |

**판본은 작게 자주** — 판본이 곧 되돌릴 지점이다. 묶인 요구가 다 끝나기를 기다리며 판본을 키우지 않는다: 끝난 요구로 잘라 내고 남은 것은 다음 판본으로 옮긴다(v0.1.0 뒤 커밋 126개가 판본 없이 쌓였던 일 — [REQ-261106-02](../requirement/requirement_261106_02.md)). `release ship` 은 묶인 요구의 상태 칸 **머리말**이 `완료` · `적용됨` 이면 끝난 것으로 본다(`완료(종료 조건 충족 …)` 처럼 괄호 꼬리는 설명 · `승인됨` · `진행 중` · `적용됨 · 확인 대기` 는 아직).

## 6. 정식 릴리스 → 템플릿 = 최신 정식본
```
release ship <버전>      종료 조건 판정 → 판본 커밋 · 로컬 태그 · CHANGELOG
   ▼ (사람 확인)
git push origin main v<버전>
release publish <버전>   GitHub Release(정식은 --latest · rc 는 --prerelease, --verify-tag)
   ▼ 자동(.github/workflows/release-branch.yml)
release 브랜치 ← 태그 커밋(fast-forward 만 — 되감기 · 강제 푸시 없음, 안 되면 실패하고 멈춤)
```
- **공개하면 `release` 브랜치가 자동으로 앞당겨진다** — `release` 는 템플릿 기본 브랜치라, 'Use this template' 으로 받으면 언제나 최신 정식본이다. 개발은 `main` 에서 계속한다
- `new-project` · `init` 도 최신 정식 태그에서 만든다(`--ref HEAD` 로 작업 트리를 고르면 경고). 복제본의 `nova.project.json` `upstream` 에 `{url, base: 태그 커밋, tag}` 가 남고, `upstream` git 원격이 등록된다
- 복제본이 새 판본을 받을 때는 `upstream tags` 로 후보를 보고 **사람이 판본을 고른다**(최신 자동 선택 없음) → `upstream plan <태그>`(건너뛰는 판본의 '복제본이 받을 때' 절을 함께 보인다) → `apply`

## 7. 마스터플랜 1 : 릴리스 N
- 마스터플랜 판본(v1.x — 계획의 판본)과 릴리스 판본(vX.Y.Z — 내보내는 판본)은 번호가 다르다. **마스터플랜 한 판본이 릴리스 여럿(MINOR · PATCH · rc)을 담는다**
- 원장의 각 판본에 `masterplan`(예: `"v1.3"`)을 적는다. 정본 `## 종료 조건 (exit)` 절 첫 줄은 "이 판본(vX.Y)이 … 릴리스 vA.B.C 로 닫는다" 형식으로 지금 닫을 릴리스를 가리킨다
- `masterplan check`(lint)가 맞물림을 본다 — 정본 판본 = 그 문장의 판본, 그 릴리스가 원장에 있고 `masterplan` 이 정본 판본, draft 판본의 `masterplan` 이 정본 판본
- 정본을 새 판본으로 채택하면(`masterplan adopt`) draft 판본의 `masterplan` 과 종료 조건 절 문장을 같은 커밋에서 맞춘다

## 8. CHANGELOG
- 루트 [CHANGELOG.md](../../CHANGELOG.md)는 **생성물**이다 — 원천은 원장 + 노트. `python nova.py release changelog` 로 만들고 `release check`(lint)가 최신인지 본다. `ship` · `draft` 가 다시 만든다
- 맨 위 `[Unreleased]` = draft 판본, 아래로 낸 판본(새것부터) — 목표 · 추가/변경/수정(노트의 새로운 것 · 바뀐 것 · 고친 것) · 되돌리기 링크

## 9. 체크포인트 · 되돌리기 — 정식 판본과 다르다
결정: [ADR-015](../adr/ADR-015-rolled-back.md) · 요구 [REQ-261106-02](../requirement/requirement_261106_02.md).

| | 정식 판본(`release ship`) | 체크포인트(`release checkpoint`) |
|---|---|---|
| 뜻 | 복제본이 받는 판본 — 번호 · 노트 · CHANGELOG | 되돌릴 지점만 — 번호 없음, 복제본 · 템플릿과 무관 |
| 판정 | 묶인 요구 완료 + 종료 조건 실제 판정 | 없음(빠른 지점) — 커밋하지 않은 변경이 없어야 한다 |
| 태그 | `v<버전>` | `checkpoint/YYMMDD-NN`(같은 날 순번 · 주석 태그) |
| 기록 | `releases.json`(상태 JSON) | `docs/releases/checkpoints.jsonl`(사건 JSONL — 추가 전용) |

- **언제 찍나** — 큰 병합(`/converge`) · 마이그레이션 · 계약 변경 직전에 `python nova.py release checkpoint "<무엇 직전>"`. 지금 HEAD 에 태그를 달고 사건 한 줄을 원장에 적어 커밋한다. 원격 보존은 사람 확인 뒤 `git push origin <태그>`
- **되돌리기** — `python nova.py release rollback <태그>` 는 할 일(되돌릴 코드 파일 · 지울 새 코드 파일 · 그대로 둘 기록)만 보인다. `--yes` 면
  1. 지금 HEAD 를 `discarded/<YYMMDD>-<태그 끝>` 브랜치로 보존한다(폐기한 커밋이 어디에도 남지 않는 일을 막는다)
  2. **코드 경로만** 그 지점 상태로 되돌리는 **새 커밋**을 만든다 — 지점 뒤에 새로 생긴 코드 파일도 지운다. 이력은 앞으로만 간다(reset · 강제 푸시 없음)
  3. 사건 원장에 `rolled_back` 한 줄(지점 · 옛 HEAD · 폐기 브랜치 · 되돌린 / 지운 파일)
- **되돌리지 않는 것**(`scripts/release.py` `RECORD_PATHS` — 이 밖이 코드 경로)

  | 경로 | 이유 |
  |---|---|
  | `docs/` | 번호 기록 · 요구 · 계획 · 마스터플랜 봉인(`docs/plans/archive/seals.json`) · 판본 · 사건 원장 — 되돌리면 번호가 비고 봉인이 어긋난다. 잘못된 변경을 적은 기록도 남는다 |
  | `registry/` | 생성물 · 명명 · 개념 원장(추가 전용) — 코드와 어긋나면 `registry.py sync` 로 앞으로 맞춘다 |
  | `SOUL.md` · `IDENTITY.md` · `.claude/soul/` | 정체성 — 사람의 명시 지시로만 바뀐다 |
  | `.claude/state/` | 훅 기록(기계마다 로컬) |
  | `CHANGELOG.md` | `docs/releases` 의 생성 보기 — 원천을 두므로 보기도 둔다 |
  | `nova.project.json` | 판본 번호 · 표준 판정 · 상류 기록 — 낸 판본과 함께 앞으로만 간다 |
- **되돌린 뒤** — `python nova.py gen`(그대로 둔 원천 · 메타와 되돌린 생성물이 어긋날 수 있다) → `python nova.py check`(기록 문서가 지운 코드를 가리키면 문서 검사가 잡는다 — 앞으로 고친다) → 사람 확인 뒤 `git push origin main`. 원격 `main` 을 옛 지점으로 되감는 강제 푸시는 이 명령이 하지 않는다 — 꼭 필요하면 사람이 따로 판단한다
- 미커밋 변경이 있으면 둘 다 거부하고, 본 작업 트리(main)에서만 쓴다(단일 기록자 — worktree 에서는 거부)
