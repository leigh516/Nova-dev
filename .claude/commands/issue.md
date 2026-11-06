---
description: 결함 · 변경요청 접수 — 재현 · 기대 · 실제 · 환경 4요소를 갖춘 것만 docs/issues/issues.json 에 올리고 등급(P0~P3)에 따라 다음 절차로 보낸다
argument-hint: <증상 한 줄> | list | show <ISS-ID>
---

# /issue — 결함 · 변경요청 접수

인자: `$ARGUMENTS`
원장: [docs/issues/README.md](../../docs/issues/README.md)(보기) · `docs/issues/issues.json`(원천 — 손으로 고치지 않는다)

## 두 종류를 한 그릇에
| `--kind` | 무엇 | 언제 |
|---|---|---|
| `defect` | 결함 · 장애 | "동작이 잘못됐다" |
| `change` | 변경요청 | "이미 만든 것을 이렇게 바꿔 달라" → 접수 뒤 [/change](change.md). 새 기능이면 여기가 아니라 `/req-new` |

종류는 분류이지 면제가 아니다 — change 도 4요소를 똑같이 받는다(재현 = 지금 어떻게 동작하나 · 기대 = 어떻게 바뀌길 원하나 · 실제 = 지금은 이렇다 · 환경 = 어느 버전 · 범위 기준인가).

## 절차
0. **본 작업 트리(main)에서** — worktree 에서는 스크립트가 거부한다(단일 기록자). worktree 에서 발견했으면 `python nova.py send --to main …` 으로 알린다
1. **4요소를 모은다** — 사용자 말에서 뽑고, 빠진 것은 **추측으로 채우지 않고 묻는다**(공백만 넣어도 거부된다)
   - 재현 `--repro`: `1) … 2) …` 순서. "가끔 그런다" 는 재현 절차가 아니다
   - 기대 `--expected` · 실제 `--actual`(오류 메시지 원문 포함) · 환경 `--env`(`v0.1.0 / 로컬` · 없으면 커밋 해시)
2. **등급을 정한다** — 애매하면 한 단계 높게 잡고 분류(triaged) 때 낮춘다

   | 등급 | 정의 | 다음 |
   |---|---|---|
   | P0 | 서비스 중단 · 보안사고 · 데이터 손실 | [/hotfix](hotfix.md) 즉시 |
   | P1 | 핵심 기능 결함(우회로 없음) | `/req-new` → `/plan-new`, 24시간 안 착수 |
   | P2 | 일반 결함(우회로 있음) | `/req-new` → `/plan-new`, 다음 릴리스 |
   | P3 | 개선 · 사소 | 백로그 — 분기 정리 |
3. **접수**
   ```bash
   python nova.py issue add --kind defect --grade P1 --title "<한 줄>" \
     --repro "1) … 2) …" --expected "…" --actual "…" --env "v0.1.0 / 로컬"
   ```
   - 번호 `ISS-YYMMDD-NN` 은 스크립트가 발급한다 — **발급된 뒤에 인용한다**
   - 열린 항목과 제목이 50% 이상 겹치면 경고가 나온다(접수는 된다). 같은 건이면 새 것을 `deferred` 로 돌리고 기존 건에 잇는다
   - 한국어 · 따옴표가 섞여 셸 인용이 꼬이면 값을 스크래치패드 파일에 쓰고 파이썬 스크립트로 `issues.main([...])` 을 부른다
4. **다음으로 보낸다** — 위 표대로. change 는 [/change](change.md)
5. **보고** — ISS ID · 등급 · 다음 절차를 한국어로 알린다

## 상태
`open` → `triaged` → `in_progress` → `verifying` → `closed`, 재현 불가 · 중복은 `deferred`
```bash
python nova.py issue set ISS-YYMMDD-NN --status triaged
python nova.py issue list --open          # 열린 것
python nova.py issue show ISS-YYMMDD-NN
```
- P0 결함의 closed 는 `--repro-test 경로::이름` 과 `--postmortem 경로` 둘 다(파일 실재) 있어야 통과한다
- P0 결함의 deferred(재현 불가 · 중복)는 `--approved-by 이름`(보류를 정한 사람)이 있어야 통과한다 — 보류로 종결 게이트를 건너뛰지 않게. 승인 없이 접수자가 혼자 내려놓지 않는다
- change 의 in_progress 이상은 `--impact` · `--level` · `--approved-by`(L3 는 `--adr`)가 있어야 통과한다

## 하지 않는 것
- 이 명령은 고치지 않는다 — 접수 · 분류까지. 수정은 `/hotfix` · `/plan-new` → `/task-run`
- `issues.json` · README 표를 손으로 고치지 않는다(lint 의 `issue check` 가 잡는다)
- `critical` · `긴급` 같은 변형 등급을 쓰지 않는다(P0~P3 만)
