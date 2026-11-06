# ADR-015 · 릴리스 체크포인트와 되돌리기 — rolled_back 재도입

| 항목 | 내용 |
|---|---|
| 일자 | 2026-11-06 |
| 상태 | 채택 |
| 대체 | - (ADR-008 은 그대로 — '버린 것' 가운데 rolled_back 하나만 번복한다) |
| 요구 | [REQ-261106-02](../requirement/requirement_261106_02.md) |
| 문서 ID | ADR-015 |
| 생성 | 2026-11-06 · `docs_new.py adr` |
| 위치 | `docs/adr/ADR-015-rolled-back.md` |
| 원천 | 2026-11-06 사용자 원문("중요한것들을 적용하기 전에 릴리즈버전을 만들어서 그 부분으로 되돌아가서 … 그 버전이후를 폐기하고") · REQ-261106-02 · 같은 날 세션 조사(v0.1.0 뒤 커밋 126개 · 판본 0) |
| 연결 | 상위 [REQ-261106-02](../requirement/requirement_261106_02.md) · 번복 대상 [ADR-008](ADR-008-parallel-bus-release.md)(릴리스 행 '버린 것') · 규약 [판본 규약 §9](../conventions/versioning.md) · 기록 형식 [ADR-004](ADR-004-ledger-formats.md) · 명령 `/release`(`.claude/commands/release.md`) · 도구 `scripts/release.py`(checkpoint · rollback) |

## 배경
- ADR-008 은 psg05 의 릴리스 체계에서 핵심만 가져오며 트랙 4종 · frozen · superseded · **rolled_back** 을 버렸다. 그때 판단은 "판본은 ship 하나로 충분하고, 되돌리기는 이전 태그로 재배포하면 된다"였다 — 예외 처리 · 사건 기록이 스크립트를 키운 psg05 를 되풀이하지 않으려는 것
- 그 뒤 실제로 일어난 일: v0.1.0(2026-11-04) 뒤 커밋 126개 · 파일 451개가 판본 없이 쌓였다. `release ship` 은 묶인 요구가 다 끝나야만 태그를 만들고, 요구 상태 판정이 정확 일치라 `완료(종료 조건 충족 …)` 같은 꼬리 붙은 완료도 거부했다. 되돌릴 지점도 · 되돌리는 명령도 · 폐기 기록도 없었다
- 사용자 요구: 중요한 변경 직전에 지점을 남기고, 잘못되면 그 지점으로 돌아가 이후를 폐기한 뒤 다시 만든다
- 제약: 이 저장소는 이력이 앞으로만 간다는 전제 위에 서 있다 — 번호 기록(요구 · 이력 · git 기록) · 마스터플랜 봉인(`docs/plans/archive/seals.json`) · worktree · 복제본(`upstream` 의 base 커밋). 강제 푸시로 이력을 되감으면 이 모두가 깨진다

## 결정
판본과 따로 **가벼운 체크포인트**와 **revert 방식 되돌리기**를 `scripts/release.py` 에 둔다. rolled_back 사건을 다시 기록한다.

- `release checkpoint "<사유>"` — 판정 없이 지금 HEAD 에 주석 태그 `checkpoint/YYMMDD-NN`(같은 날 순번). 사건 원장 `docs/releases/checkpoints.jsonl`(추가 전용 JSONL — ADR-004: 쌓이는 사건은 JSONL)에 한 줄을 적어 커밋한다. 정식 판본 원장 `releases.json`(draft · shipped)은 건드리지 않는다
- `release rollback <태그> [--yes]` — 기본은 할 일만 보인다. `--yes` 면
  1. 지금 HEAD 를 `discarded/<YYMMDD>-<태그 끝>` 브랜치로 **보존**한다(폐기한 커밋이 어디에도 남지 않는 일을 막는다)
  2. **코드 경로만** 지점 상태로 되돌리는 **새 커밋**(revert 방식)을 만든다 — 지점 뒤 새로 생긴 코드 파일도 지운다
  3. 사건 원장에 `rolled_back` 한 줄(지점 · 옛 HEAD · 폐기 브랜치 · 되돌린 / 지운 파일)
- **코드 경로 = 기록 경로 밖 전부.** 기록 경로는 상수 `RECORD_PATHS` 하나로 둔다: `docs/` · `registry/` · `SOUL.md` · `IDENTITY.md` · `.claude/soul/` · `.claude/state/` · `CHANGELOG.md` · `nova.project.json`. 코드 쪽을 목록으로 적지 않는 것은 새 프로젝트가 새 최상위 폴더를 만들어도 빠짐없이 되돌리기 위해서다
- 둘 다 커밋하지 않은 변경이 있으면 거부하고, 본 작업 트리(main)에서만 쓴다(단일 기록자 · `novalib.require_main`)
- **원격은 사람이 한다.** 명령은 `git push` 안내만 낸다. 원격 `main` 을 옛 지점으로 되감는 강제 푸시는 기본값이 아니며 이 명령이 하지 않는다 — 꼭 필요하면 사람이 따로 판단한다
- 같은 요구에서 `release ship` 의 요구 상태 판정을 머리말 판정으로 고친다(`완료(…)` · `적용됨(…)` 통과 · `승인됨` · `진행 중` 거부 — 정본 `progress.is_done`). 판본은 끝난 요구로 잘라 작게 자주 낸다

## 검토한 대안
| 대안 | 장점 | 단점 | 버린 이유 |
|---|---|---|---|
| `git reset --hard <지점>` + 강제 푸시 | 이력이 깔끔하다 | 번호 기록 · 봉인 · worktree · 복제본 base 가 가리키던 커밋이 사라진다. 기록 문서까지 되감겨 lint 가 깨진다 | 이 저장소의 '앞으로만' 전제와 정면으로 부딪힌다 |
| 저장소 전체를 지점 상태로(`git revert <지점>..HEAD`) | git 표준 | 잘못된 변경을 적은 이력 · 요구 · 마스터플랜 봉인까지 되돌린다 — 반목표('기록 · 봉인까지 되돌려 lint 를 깨는 것')에 해당 | 기록은 남아야 한다 |
| 체크포인트 없이 정식 판본만 자주 | 도구가 하나 | ship 은 노트 · 종료 조건 판정이 필요해 큰 병합 직전마다 내기에는 무겁다 | 빠른 지점이 따로 있어야 '직전에 찍는' 습관이 된다 |
| 코드 경로를 목록으로(포함 목록) | 무엇을 돌리는지 바로 보인다 | 새 최상위 폴더가 생기면 조용히 빠진다 | 새 프로젝트에서 구멍이 된다 — 제외 목록이 안전하다 |

## 결과
- 좋아지는 것
  - 큰 병합 · 마이그레이션 · 계약 변경 직전에 한 줄로 지점을 남기고, 잘못되면 한 커밋으로 코드를 돌린다. 폐기한 이력은 브랜치로 남고 원장에 사건이 남는다
  - 기록 · 봉인 · 원장은 그대로라 lint 의 봉인 · 번호 검사가 깨지지 않는다
  - 꼬리 붙은 완료 상태가 ship 을 막지 않아 판본을 작게 낼 수 있다
- 감수하는 것
  - 코드만 돌리므로 그대로 둔 기록 · 원장 · 메타와 코드가 어긋날 수 있다(지운 스크립트를 가리키는 문서 링크 · `registry/` 의 생성물 원장 · `nova.project.json` 에서 만든 생성물) → 되돌린 뒤 `python nova.py gen` → `python nova.py check` 로 찾아 **앞으로** 고친다
  - DB 데이터 · 배포(k3s)는 돌리지 않는다 — 마이그레이션은 Expand→Migrate→Contract(`/change`)가 대비이고, 배포 되돌리기는 [deploy 규약](../conventions/deploy.md) 그대로다
  - 체크포인트 원장 커밋이 하나씩 늘어난다(태그는 그 커밋 앞을 가리킨다)
- 지킬 것
  - `/converge` · 마이그레이션 · 계약 변경 직전에 `release checkpoint` 를 권고한다(명령 문서에 한 줄)
  - 되돌리기는 먼저 할 일을 보고 사람 확인 뒤 `--yes`. 강제 푸시는 자동화하지 않는다
  - `RECORD_PATHS` 를 바꾸면 이 ADR 과 판본 규약 §9 를 같은 커밋에서 맞춘다
- 되돌리기(이 결정 자체)
  - `release checkpoint` · `rollback` 하위 명령과 `RECORD_PATHS` 를 지우고, `docs/releases/checkpoints.jsonl` 은 남긴다(추가 전용 사건 기록). 이미 찍은 `checkpoint/*` 태그 · `discarded/*` 브랜치는 그대로 두어도 해가 없다
