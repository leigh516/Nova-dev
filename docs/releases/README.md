# docs/releases — 버전 릴리스

판본마다 **목표 · 종료 조건 · 하지 않는 것**을 정하고, 종료 조건이 모두 녹색일 때만 낸다. 결정: [ADR-008](../adr/ADR-008-parallel-bus-release.md) · 규칙: [plans README §5 · §6](../plans/README.md) · **번호 · 정식 릴리스 · 마스터플랜 연결 규칙: [판본 규약](../conventions/versioning.md)**

| 파일 | 무엇 | 누가 |
|---|---|---|
| `releases.json` | 판본 원장(상태 JSON) — version(X.Y.Z · 사전 판본 X.Y.Z-rc.N) · status(draft · shipped) · goal(300자 안) · exit(종료 조건) · not_doing · reqs · 날짜 · tag · due(목표일, 선택) · masterplan(담는 마스터플랜 판본) | 도구(`release draft · ship`) + 사람(종료 조건 · 하지 않는 것 · 판정) |
| `v<버전>.md` | 릴리스 노트(사람이 쓴다) — 새로운 것 · 바뀐 것 · 고친 것 · **복제본이 받을 때** · 올리는 법 · **되돌리기** · 알려진 문제 | 사람 · Claude([_template.md](_template.md) 복사) |
| 루트 `CHANGELOG.md` | 생성물(Keep a Changelog) — 원장 + 노트에서 `release changelog`, `release check`(lint)가 최신인지 본다 | 도구 |
| `checkpoints.jsonl` | 체크포인트 · 되돌리기 사건 원장(추가 전용 JSONL — `checkpoint` · `rolled_back` 한 줄씩). 첫 `release checkpoint` 가 만든다 — [판본 규약 §9](../conventions/versioning.md) | 도구(`release checkpoint · rollback`) — 손으로 고치지 않는다 |

## 흐름
1. `python nova.py release draft 0.2.0 --goal "<한두 문장>" --req REQ-…` — draft 는 한 번에 하나
2. `releases.json` 에서 종료 조건(기본: test · lint) · 하지 않는 것을 채운다(자리표시 `(… 채운다)` 를 그대로 두면 `release check` 가 실패). 사람이 볼 조건은 `"how": "사람"` + 판정 `"judged": "충족 YYYY-MM-DD"`
3. 노트 `v0.2.0.md` 를 쓴다 — '복제본이 받을 때' · '되돌리기' 절은 없거나 자리표시로 두면 낼 수 없다(예상 충돌 · 손 마이그레이션 / 태그 · 데이터 되돌림 가능 여부 · 확인 지점)
4. `python nova.py release suggest` — 지난 정식 태그 뒤 커밋 종류로 최소 올림을 본다. 원장 판본이 그보다 낮으면 ship 이 거부한다
5. `python nova.py release ship 0.2.0` — 묶인 요구가 완료인지, 종료 조건을 실제로 판정 → 모두 녹색이면 `nova.project.json` version · 인프라 생성물 재생성 · shipped · CHANGELOG → 판본 커밋 → 로컬 태그 `v0.2.0`(태그가 판본 기록 커밋을 가리킨다). `docs/releases/` 밖에 커밋하지 않은 변경이 있으면 거부, 어느 단계든 실패하면 종료 1
6. git 기록 → 사람 확인 뒤 `git push origin main v0.2.0` → `python nova.py release publish 0.2.0`(먼저 `--dry`) — GitHub Release 를 만든다(rc 는 prerelease). **정식을 공개하면 `release` 브랜치가 자동으로 그 태그로 앞당겨진다**(`.github/workflows/release-branch.yml` — fast-forward 만) → 템플릿 = 최신 정식본
7. 다음 판본 draft(`--masterplan v<정본>` · 필요하면 `--due`)
- 판본 사이에 새로 보인 것은 다음 판본의 목표 · 하지 않는 것으로 간다(지금 판본을 넓히지 않는다)
