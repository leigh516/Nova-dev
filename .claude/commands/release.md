---
description: 버전 릴리스 — 판본의 목표 · 종료 조건 · 하지 않는 것을 확인하고, 종료 조건을 실제로 판정해 모두 녹색일 때만 낸다(태그 · 노트 · 다음 판본)
argument-hint: draft <버전> | ship <버전> | status | checkpoint "<사유>" | rollback <태그>
---

# /release — 버전 릴리스

인자: `$ARGUMENTS`
규칙: [docs/releases/README.md](../../docs/releases/README.md) · [plans README §5](../../docs/plans/README.md)

## draft — 새 판본 열기
1. `python nova.py release status` — draft 는 한 번에 하나. 직전 판본의 '하지 않는 것' · 이월 항목을 하나씩 처분한다(올림 · 이월 · 기각 — 이유 한 줄)
2. `python nova.py release draft <버전> --goal "<한두 문장 · 300자 안>" --req REQ-…`
3. `docs/releases/releases.json` 을 채운다
   - 종료 조건: 기본은 test · lint, 사람이 볼 것은 `"how": "사람"`
   - 하지 않는 것: 이 판본에서 안 하는 것 — 새로 보인 것은 다음 판본으로
4. 사용자에게 목표 · 종료 조건 · 하지 않는 것을 보여 확인받는다

## ship — 내기
0. **진입 조건**(원장 대조는 `project-manager` · lint 단계별은 `verifier` 에이전트를 함께 띄울 수 있다)
   - 진척 대조 `python nova.py progress` — 묶인 요구 · task · 판본이 서로 맞는가
   - 클린 클론 재현: 임시 폴더에 `git clone` → `python nova.py install` → `python nova.py check` (커밋 안 된 것에 기대지 않는지)
   - 의존성 감사: `uv pip list --outdated` · `npm audit`(web) 결과를 노트 '알려진 문제'에 적는다(막지는 않는다)
1. 노트 `docs/releases/v<버전>.md` 를 쓴다(`_template.md` 복사 — 초안은 `release-manager` 에이전트에 맡겨도 된다)
   - 새로운 것 · 바뀐 것 · 고친 것 · 올리는 법을 적는다
   - **되돌리기**: 이전 태그 · 이미지, 데이터를 되돌릴 수 있는지, 확인할 지점
   - 알려진 문제
2. 사람이 볼 종료 조건은 사용자가 확인한 뒤 판정 칸에 `충족 YYYY-MM-DD` 를 적는다(확인 없이 적지 않는다)
3. `python nova.py release ship <버전>` — 묶인 요구가 완료인지, 종료 조건(명령은 실제 실행)을 판정해 모두 녹색이면 **판본 기록(`nova.project.json` version · shipped) · 인프라 생성물 재생성 → 판본 커밋 → 로컬 태그** 순서로 한다(태그가 판본 기록 커밋을 가리킨다 — 되돌리기 지점 = 그 판본의 이미지 태그)
   - 명령 판정의 시간 제한은 기본 1200초 — 이 PC 처럼 전체 test 가 20분을 넘으면 `NOVA_EXIT_TIMEOUT=3600 python nova.py release ship <버전>`. 사람 판정 칸은 `충족 YYYY-MM-DD` 로 시작해야 녹색(`scripts/goals.py`)
   - `docs/releases/` 밖에 커밋하지 않은 변경이 있으면 거부한다 — 먼저 커밋하거나 치운다(판본 커밋에 남의 변경이 섞이지 않게)
   - 어느 단계든 실패하면 종료 1 — 출력된 안내대로 고친 뒤 다시 한다
4. git 기록(`git_record.py`). 태그를 원격에 올리는 것은 사용자 확인 뒤: `git push origin main v<버전>`
5. 다음 판본 draft 를 연다 — 이번에 하지 않은 것 · 새로 보인 것이 그 입력이다
- 판본은 작게 — 묶인 요구가 다 끝나기를 기다리지 말고 끝난 요구로 잘라 내고, 남은 것은 다음 판본으로 옮긴다([판본 규약 §5](../../docs/conventions/versioning.md))

## checkpoint — 되돌릴 지점(정식 판본 아님 — [판본 규약 §9](../../docs/conventions/versioning.md) · [ADR-015](../../docs/adr/ADR-015-rolled-back.md))
1. 큰 병합 · 마이그레이션 · 계약 변경 직전에 `python nova.py release checkpoint "<무엇 직전>"` — 판정 없이 지금 HEAD 에 주석 태그 `checkpoint/YYMMDD-NN` · 사건 원장 `docs/releases/checkpoints.jsonl` 한 줄(커밋). 커밋하지 않은 변경이 있으면 거부한다
2. 원격 보존은 사용자 확인 뒤: `git push origin <태그>`

## rollback — 지점으로 되돌리기
1. `python nova.py release rollback <태그>` — 할 일만 본다(되돌릴 코드 파일 · 지울 새 코드 파일 · 그대로 둘 기록). 사용자에게 보여 확인받는다
2. 확인되면 `python nova.py release rollback <태그> --yes` — 지금 HEAD 를 `discarded/<YYMMDD>-<태그 끝>` 로 보존 → 코드 경로만 되돌리는 새 커밋 → 사건 원장 `rolled_back`. 기록 문서 · 원장 · 봉인(`RECORD_PATHS`)은 그대로다
3. `python nova.py gen` → `python nova.py check` — 어긋난 생성물 · 지운 코드를 가리키는 기록을 앞으로 고친다
4. git 기록 → 사용자 확인 뒤 `git push origin main`(폐기 브랜치도 남기려면 함께). 강제 푸시는 하지 않는다 — 꼭 필요하면 사용자가 따로 정한다
