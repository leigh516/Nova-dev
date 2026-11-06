# Nova 공통개발플랫폼 — 저장소 작업 규칙

Nova 는 모든 신규 프로그램의 출발점이 되는 공통개발플랫폼이다. 문서 프로세스 · 백엔드 공통 라이브러리(`nova_common`) · 서비스 골격 · 인프라 생성기 · 생성물 원장 · 디자인 시스템 · 웹/모바일 골격을 담는다. 계획: [`docs/plans/master_plan.md`](docs/plans/master_plan.md). 북극성 · 성공 판정: [`docs/PROJECT.md`](docs/PROJECT.md). 프로젝트 메타: [`nova.project.json`](nova.project.json).

## AI 축 — SOUL 레이어 (매 세션 자동으로 싣는다 — [ADR-007](docs/adr/ADR-007-soul-layer.md))
정체성(SOUL · IDENTITY) · 함께 일하는 사람(USER) · 응답 규칙(STYLE)을 아래에서 싣는다. 읽는 순서는 [`.claude/soul/MEMORY.md`](.claude/soul/MEMORY.md). **사람이 명시로 지시할 때만 바꾼다** — 바꿀 후보는 `/soul-review` 가 제안으로만 올린다. 응답이 끝날 때 Stop 훅(`.claude/hooks/persona_guard.py`)이 한국어 규칙 · 금지 첫머리를 검사하고, 도구를 부르기 직전에는 같은 훅의 `--pretool`(PreToolUse)이 직전 진행 알림 · 도구 설명의 영어 문장을 막는다(REQ-261105-01).

@SOUL.md
@IDENTITY.md
@.claude/soul/USER.md
@.claude/soul/STYLE.md

## 0. 언어 규칙 (최우선 — REQ-261103-05)
- **사용자와의 모든 대화는 한국어**로 한다. 작업 중 진행 알림 · 질문 · 요약 · 오류 보고도 예외 없음
- **화면에 보이는 모든 것이 한국어**: 생각(추론) 과정 · 도구 호출 설명(description) · 도구 사이의 짧은 한 줄 · 사과 · 서브에이전트에게 주는 지시와 받는 결과까지. 긴 작업 · 컨텍스트 요약 뒤에 영어로 미끄러지는 일이 반복됐다(사용자 지적 6회 — 2026-11-03 ~ 11-04) → 문장을 쓰기 전에 매번 한국어인지 확인한다
- 저장소 `.claude/settings.json` 의 훅(SessionStart · UserPromptSubmit)이 매 요청마다 이 규칙을 다시 알린다 — 지우지 않는다
- **모든 기록은 한국어**: 요구 · 계획 · task · 이력 · git 기록 · 세션 인수인계 · ADR · 검토 · 검증 · README · 규약 문서. `docs_index.py --check` 가 한글이 없는 문서를 실패로 잡는다
- **커밋 메시지 · 코드 주석 · docstring · API 오류 메시지 · 화면 문구 · 로그 설명은 한국어**
- 영어 그대로 두는 것: 식별자(변수 · 함수 · 클래스 · 파일 이름), 커밋 type 접두어(`feat(범위):`), 명령어 · 경로 · 설정 키, 외부 고유명사

## 세션 시작 · 종료
- 시작: `/session-start` — `docs/session/LATEST.md` 인수인계를 읽고 이어서 작업
- 컨텍스트가 많이 소모되면: `/session-end` — 인수인계 작성 · 기록 · 푸시

## 문서 규칙 (반드시 지킨다)
0. **제품 전체를 정할 때(새 프로젝트 · 큰 범위)** → 자료를 `docs/warehouse/inbound/<분류>/` 에 넣고 `/checklist`(자료를 역으로 분석해 요구 체크리스트 폼을 자동으로 채움 → 고객이 클릭으로 확인 · 보충, `python nova.py checklist`) → `/intake`(심층 분석 → `docs/product/intake.json`, 부족 항목) → `/req-interview`(부족한 것만) → `/prd`(`prd.json`, 승인) → `/foundation`(언어 · 프레임워크 / 아키텍처 · 배포 / DB / 횡단관심사 + 표준 판정 → ADR) → `/spec`(`spec.json`, 승인) → `/plan-new`. 정본은 `docs/product/*.json`, 사람에게 건네는 것은 `docs/warehouse/outbound/<분류>/`(생성물 — `warehouse.py out`, 손으로 고치지 않는다) — [product README](docs/product/README.md)
1. **새 요구** → 새 프로젝트 · 큰 기능의 입구는 `/kickoff`(북극성), 고객 인터뷰가 필요하면 `/req-interview`(psg05 이름 `/interview`)(`docs/requirement/interviews/interview_YYMMDD_NN.md`) → `/req-analyze`, 바로 기록할 수 있으면 `/req-new` (`uv run python scripts/docs_new.py req "<제목>"`) → `docs/requirement/requirement_YYMMDD_NN.md` + 인덱스. 원문은 사용자 말 그대로, 하위 ID `REQ-YYMMDD-NN-n`, 요구마다 확인 가능한 수용 기준
2. **계획 3층** — 마스터플랜 → 세부 계획 → task ([규칙](docs/plans/README.md)): 마스터플랜 중요 변경은 `drafts/` 초안 → 사용자 결정 확인 → 채택(버전 · `archive/` · changelog). 세부 계획은 `/plan-new` → `plan_REQ_NN.md`(§4 형식, 화면이면 목업 + **4.1 UX 점검**) + `tasks/tasks_REQ_NN.md`(한 줄 한 가지 일, ID `T<NN>-<단계>.<순번>`). 완료는 **코드 · 테스트로 확인 후** `- [x]`, 작업 중 생긴 일은 🆕
3. **작업 단위 종료** → `/history-new` → `docs/history/history_YYMMDD_NN.md` + 인덱스
4. **푸시마다**(그 사이 커밋 전부를 한 기록으로 — 범위를 주지 않으면 지난 기록 이후 전부) → `uv run python scripts/git_record.py "<요약>" <범위>` → `docs/git/git_YYMMDD_NN.md` + 인덱스. 커밋 규칙 [git.md](docs/conventions/git.md)
5. **결정** — 되돌리기 어려운 구조 결정은 `docs/adr/`(`docs_new.py adr`)
6. **검토 · 검증** — 코드 검토 결과는 `docs/reviews/`, 실환경 검증 결과는 `docs/verification/`
7. 사용자와는 **한국어**로 소통한다 (사용자는 기획 · 설계자) — 규칙 0
8. `uv run python scripts/docs_index.py --check` 가 인덱스 · 링크를 검사한다(lint 포함)
9. **기록 형식 — MD · JSON · JSONL 을 섞지 않는다**([ADR-004](docs/adr/ADR-004-ledger-formats.md)): 쌓이는 이력 · 원장(사건 한 줄씩 · 추가 전용)은 **JSONL**, 사람이 정하는 정본 · 기계용 현재 상태는 **JSON**, 사람이 읽는 보기는 **MD**(생성물이면 손으로 고치지 않는다). **MD 를 기계 입력으로 쓰지 않는다** — 스크립트가 읽고 세야 하는 원장을 새로 만들면 JSONL 원천 + MD 생성 보기로 둔다(교훈 원장 이전은 REQ-261105-02). 요구 · 계획 · 이력 같은 사람 문서는 MD 그대로
10. **README · 규약 문서는 코드와 같은 커밋에서 맞춘다** (2026-11-05 README 35개 심층 검증에서 어긋남 30여 곳 — REQ-261105-03)
    - **바뀌는 숫자를 박지 않는다**(명령 개수 · 대비 쌍 · 화면 수 · 단계 수): 정본(명령 출력 · 대장 · 스크립트 목록)을 가리킨다
    - **없는 것을 현재형으로 쓰지 않는다**: 아직 읽는 코드가 없는 규약 · 폴더는 `🗺` 를 붙인다
    - **공개 API · 환경 변수 · 명령 인자를 바꾸거나 더하면** 그 모듈을 설명하는 README 행을 같은 커밋에서 고친다(담당 에이전트에게도 지시한다)
    - **생성물 표시는 실제 생성기와 맞게**: 무엇이 생성물이고 원천이 어디인지(어느 명령이 만드는지)를 파일 종류마다 정확히
    - **되돌리기 · 실행 안내는 실제로 해 본 것만**: 적은 명령으로 원래대로 돌아가는지(새로 생긴 파일 포함) 확인한 뒤 쓴다
11. **기록 문서 머리 표에 추적 칸 다섯**(REQ-261105-04): `문서 ID` · `생성`(날짜 · 명령) · `위치` 는 생성기(`docs_new.py` · `git_record.py`)가 채우고, `원천`(무엇에서 나왔나) · `연결`(상위 · 하위 · 관련 문서 링크)은 사람이 채운다. 이 규칙 뒤에 만든 문서의 원천 · 연결이 없거나 자리표시 그대로면 `docs_index.py --check` 가 실패한다(앞선 문서는 소급하지 않는다)

## Superpowers — 일하는 방법 (방법은 Superpowers, 기록은 Nova — [superpowers.md](docs/conventions/superpowers.md) · [ADR-005](docs/adr/ADR-005-superpowers-workflow.md))
- 플러그인 `superpowers@claude-plugins-official` 을 `.claude/settings.json` 에서 켠다(`python nova.py doctor` 로 확인). 작업마다 맞는 스킬을 **먼저** 찾아 쓴다(`superpowers:using-superpowers`)
- 흐름: 고객 인터뷰 `/req-interview`(brainstorming) → 요구 분석 `/req-analyze`(빌더 점검 · **승인 관문** — 승인 전 구현 금지) → 계획 `/plan-new`(writing-plans — 전역 제약 · 검토 초점 · 자체 점검) → 실행 `/task-run`(subagent-driven-development 또는 executing-plans + **TDD**) → 검토 `/review-request`(requesting/receiving-code-review) → 마무리 `/finish`(verification-before-completion · finishing-a-development-branch). 버그는 `/debug`(systematic-debugging)
- **Nova 규칙이 우선**: `docs/superpowers/` 를 만들지 않는다 — 설계는 인터뷰 기록 · 요구 · `plan_REQ_NN`, 계획은 `plan_REQ_NN` + `tasks_REQ_NN`, 검토는 `docs/reviews/`. 스킬 본문이 영어여도 대화 · 기록 · 커밋은 한국어. `.superpowers/` · `.worktrees/` 는 커밋하지 않는다
- 증거 없이 "됐다"고 하지 않는다 — 완료 주장 전 `python nova.py test` · `lint` 출력 확인

## 끝이 있는 일 · 병렬 개발 · 릴리스 (신속성 · 효율성 — [ADR-008](docs/adr/ADR-008-parallel-bus-release.md) · [plans README §5 · §6](docs/plans/README.md))
- **목표 · 종료 조건(exit) · 하지 않는 것**: 요구 · 계획 · 마스터플랜 판본 · 릴리스마다 적는다. 종료 조건은 1~7개, 한 번 돌리거나 한 번 보고 답이 나오는 것만(소진형 금지). **모두 녹색이면 끝**(`python nova.py exit-check REQ-…`)
- **새로 보인 것은 세 갈래**: 종료 조건을 깸 · 치명적 → 지금 고친다 / 그 밖 → 새 요구 · 다음 판본으로. **이번 일을 넓히지 않는다**
- **개선이 개선을 낳지 않게**(리뷰 · 감사 · 교훈 · 작업 중 발견 — REQ-261105-03 · [plans README §5](docs/plans/README.md)): ① 고치기 전에 **목표 · 완료 조건 · 하지 않는 것**을 먼저 적는다(적지 않은 개선은 시작하지 않는다) ② 🆕 의 기본 행선지는 **다음 판본** — "작으니까 지금"은 이유가 아니다, 줄에 판정을 적는다 ③ **한 세대 규칙** — 개선 작업에서 새로 보인 것은 같은 회차에 다시 고치지 않는다. 이 규칙을 검사하는 게이트는 따로 만들지 않는다
- **병렬은 공통 영역이 끝난 뒤**: 공통 영역 = 모든 개발이 같은 것을 쓰게 하는 표준 · 공통 모듈(CI · 인증 · DB · 계약 · 화면 공통 모듈 · 공통 컴포넌트 · 공통 명명 규약 — 필수 7항목, lint 가 빠짐을 잡는다). 먼저 갈라지면 worktree 마다 화면 · 부품 · 이름이 달라진다. 마스터플랜 '공통 영역 완료 선언' 모두 완료(+증거) · '병렬 묶음' 2개 이상 · 경로 겹침 없음 → `python nova.py worktree-new <묶음>`(`/worktree-new`). 닫혀 있으면 직렬로 간다
- **단일 기록자**: 번호가 붙는 기록 · 인덱스는 본 작업 트리(main)만 쓴다. worktree 는 코드 · 테스트만, 병합은 main 이 `/converge`
- **메시지 버스**: worktree 세션끼리 `/send` · `/inbox`(본 트리 `.collab/` 하나, 커밋 안 함). 보낸 것은 고치지 않는다 · 끝낼 때 `--result` · 3번 넘게 오가면 main 에 escalation
- **릴리스**: `/release` — `docs/releases/releases.json` 판본의 종료 조건을 실제 판정해 녹색일 때만 낸다. 노트에 되돌리기 필수. 태그 원격 푸시는 사람 확인 뒤
- **마스터플랜 판본**: 채택은 `python nova.py masterplan adopt`(지난 판본 봉인 · 이력). 지난 판본은 고치지 않는다(lint 가 봉인 해시로 검사)

## 명령 · 스킬 · 에이전트 — 3층 작업 체계 ([ADR-009](docs/adr/ADR-009-commands-skills-agents.md) · 지도 [superpowers.md §2.1](docs/conventions/superpowers.md))
- **명령**(`.claude/commands/`)은 절차 · 관문, **스킬**(`.claude/skills/` — `nova-screen` 화면 조립 · `nova-ui-verify` 화면 확인 · `nova-masterplan` 판본 초안)은 요청 문장으로 발동되는 방법, **에이전트**(`.claude/agents/<폴더>/` — research · planning · development · quality · docs · ops · meta · domain 성격별 폴더, psg05 역할 대부분을 Nova 에 맞게 살림 · 빠른 찾기와 편제표는 [README](.claude/agents/README.md) · 도메인 팩마다 `domain/<팩>-specialist`)는 명령 · 스킬이 정한 자리에서 부르는 역할
- 운영 가이드(main 과 에이전트 · 지시와 피드백 고리 · 병렬 · 모델 등급 · 호출 기록): [agents.md](docs/conventions/agents.md)
- 에이전트는 재료를 내고 **판정은 main**. 읽기 전용 폴더(research · planning · quality · domain · ops 대부분)는 쓰기 도구가 없다. 번호 기록 · 원장 · 커밋 · 푸시는 main 만(단일 기록자). 비싼 병렬은 명령이 정한 자리에서만
- **운영 결함**은 `/issue`(재현 · 기대 · 실제 · 환경) → P0 `/hotfix`(회귀 테스트 먼저) → `/postmortem` → `/learn`(교훈 원장 `docs/memo/lessons.md`). **승인된 범위의 변경**은 `/change`(영향 `python nova.py impact` → 등급 L1~L3 → 승인)
- 에이전트 · 스킬 · 명령을 만들거나 고칠 때는 스킬 nova-subagent-creator · nova-skill-creator · nova-command-creator — 만들기 전 세 가지 확인 → 형식 → 압박 시나리오 시험 → `claude_check`(겹침 판정은 `agent-creator`). 결정 [ADR-010](docs/adr/ADR-010-agent-folders.md)(폴더형 편제)
- 검증은 `python nova.py check`(test · lint 동시). 형식은 `scripts/claude_check.py` 가 lint 에서 검사(한국어 · 도구 경계 · 반환 4절 · 단일 기록자 · 토큰 밖 값)

## 개발 규칙
- **UI/UX** — [ui.md](docs/conventions/ui.md)(토큰 → 컴포넌트 → 템플릿, 화면은 템플릿 호출 + 데이터 정의만, 서버 호출 버튼은 `useAction`/`rememberAction`) · [ux-heuristics.md](docs/conventions/ux-heuristics.md)(**닐슨 10대 휴리스틱** [자동]/[확인] 규칙 · 심각도 0~4 · 평가자 2명 · 사용성 테스트 · 실사용 데이터로 단점 보완) · 화면 조립은 `nova-screen`(nicomms 운영 콘솔 형태 요청은 `nicomms-screen` — 원본 값은 들이지 않고 대응표 · 갭으로), 화면 확인은 `nova-ui-verify` 스킬
- **디자인 시스템** — [README](docs/design-system/README.md): 색 · 간격 · 글꼴은 `design/tokens/brand.tokens.json` 에서만 바꾸고 `python nova.py tokens`(WCAG 2.2 AA 대비 자동 검사). 스타일은 의미 토큰 `var(--color-…)` 만
- **백엔드** — [backend.md](docs/conventions/backend.md): 서비스는 자기 DB 만, 서비스 간은 이벤트(아웃박스 · 멱등 소비) 또는 `/internal` 계약 API, 오류는 `{error:{code,message}}`, enum 하드코딩 금지, **DB 기본키 · 이벤트 ID 는 UUIDv7**(`id_column()` · `new_id()`, [ADR-003](docs/adr/ADR-003-uuid-v7-ids.md))
- **명명** — [naming.md](docs/conventions/naming.md)(선언 정본 `registry/naming.json` · lint `naming check`) · 개념 원장 `registry/entities.json`. **새 표 · 개체를 만들기 전에 `python nova.py naming lookup <개념>`** — 정확 · 별칭이면 만들지 않는다, 없음이면 사람 승인 후 `naming entity add`
- **단일 원천 → 생성** — 서비스 목록 `packages/common-py/nova_common/services.json`, 토픽 `infra/k3s/base/kafka-topics.txt`, 토큰, 프로젝트 메타 `nova.project.json`. 생성물은 손으로 고치지 않는다 → `python nova.py gen`, `lint` 가 `--check`
- **생성물 원장** — DB 테이블 · 화면 · API · 토픽 · UI 컴포넌트 · 서비스를 만들거나 지우거나 옮기면 `uv run python scripts/registry.py sync --by <이름> --note <사유>`. 삭제된 이름은 새로 만들지 말고 `restore <ID>`
- **대장 4종**([ADR-004](docs/adr/ADR-004-ledger-formats.md)) — [화면](docs/registry/screens.md) · [DB 사전](docs/registry/db-dictionary.md) · [권한](docs/registry/permissions.md) · [이벤트](docs/registry/events.md). 코드에서 파생(`uv run python scripts/ledgers.py`) — 손으로 쓰지 않는다. **계획을 세울 때(§0 영향분석 · §8 재사용) 먼저 대장을 조회**한다: 이 표를 쓰는 화면은? 이 권한을 가진 역할은? 이 이벤트의 구독자는? 새 컬럼은 `comment=`(의미), 새 화면은 머리 주석 `/** @screen 이름 · @status 기획|설계|개발|완료 */`, 새 역할은 `rbac.json` 에 먼저. 형식 규칙: 이력 JSONL · 선언/상태 JSON · 보기 MD(MD 를 기계 입력으로 쓰지 않는다)
- **표준(STD)** — [docs/std](docs/std/README.md): 멀티테넌시 · 도메인 팩 · AI 자동화 등급. 프로젝트마다 적용/면제를 `nova.project.json` `standards` 에 **판정**으로 남긴다(lint 가 판정 누락을 잡는다). 계획서 §0 에 해당 표준 체크
- **Python 환경은 uv** ([ADR-002](docs/adr/ADR-002-python-env-uv.md)) — `uv sync` · `uv run` · `uv add`. `pip install` 직접 사용 금지

## 명령 (Windows · Linux 공통 — `python nova.py help`)
| 명령 | 내용 |
|---|---|
| `python nova.py install` | `uv sync` — `.venv`(Python 3.12) + `uv.lock` 기준 설치 |
| `python nova.py test` | 전체 파이썬 테스트 |
| `python nova.py lint` | 토큰 · 인프라 생성물 · 원장 · 문서 인덱스 · 인프라 검증 |
| `/checklist` · `python nova.py checklist` | 요구 체크리스트 — 자동 채움 · 폼 만들기 · 저장 서버(`scripts/checklist.py build\|serve\|md\|import\|check`) |
| `/intake` · `/prd` · `/foundation` · `/spec` | 입고 분석 → PRD → 기반 4단계 질의 → SPEC (`uv run python scripts/warehouse.py scan\|gaps\|out\|check`) |
| `/req-interview` · `/req-analyze` · `/plan-new` · `/task-run` · `/review-request` · `/debug` · `/finish` | Superpowers 연동 작업 흐름 ([superpowers.md](docs/conventions/superpowers.md) §2) |
| `/sdd [full\|light\|fast] <이름>` | 명세 주도 개발 묶음 — 크기 판정 → 산출물로 지금 단계 판정 → 위 명령들을 승인 관문과 함께 차례로 |
| `/worktree-new <묶음>` · `/converge <묶음>` · `/worktree-sync`(psg05 이름 `/sync-common`) · `/send` · `/inbox` | 병렬 개발 — `python nova.py parallel-gate · worktree-new · worktree-list · converge · worktree-sync [--dry] · send · inbox · outbox · done · show` |
| `/docs-write` · `/round-close` · `python nova.py docs-write grade\|tasks\|facts` | 기록 분량 정하기(등급 → 기록 하한 · tasks 3갈래 · 판본 노트) · 회차 마감(사실 수집 → 기록 → 교훈 → check · git 기록 → 인계) |
| `/release` · `python nova.py release suggest\|ship\|publish\|changelog` · `python nova.py exit-check REQ-…` · `python nova.py masterplan adopt …` | 릴리스(판본 종료 조건 판정 → 태그 → 공개 · 번호 규칙 [versioning.md](docs/conventions/versioning.md)) · 종료 조건 판정 · 마스터플랜 채택(봉인) |
| `python nova.py check` · `quick` · `profile` · `progress` | test · lint 동시 실행(실패 축 이름 — 단계 관문 · 푸시 묶음) · 빠른 검사(바뀐 곳 · `--stage T<NN>-<단계>` — task 마다) · 규모 프로파일(lite · product · platform — `get|set|check|suggest`) · 진척 대조(계획 ↔ task ↔ 요구 ↔ 판본) |
| `/issue` · `/hotfix` · `/postmortem` · `/learn` · `/change` | 결함 원장(`python nova.py issue`) · 긴급 수정 · 사후기록 · 교훈(`learn`) · 변경 요청(영향 `impact`) |
| `/kickoff` · `/analyze` | 착수(북극성 PROJECT.md 고정 → `/req-interview`) · 현황 진단(→ `/deep-audit`) |
| `/handoff-start` · `/handoff-end` | worktree 세션 이어받기 · 마감(`python nova.py handoff close-check` 가 막으면 마감 안 함) |
| `/dispatch` · `/orchestrate` | 파도별 분배(`python nova.py dispatch plan\|next` — 병렬 게이트 먼저) · 진행 중 관측과 버스 지시(`handoff observe`) |
| `/verify` · `/test` · `/e2e-test` | 정적 검증(lint 단계별 + 바뀐 축 판정자) · 행동 테스트 · 실연동(ui-smoke · checklist-smoke · kmp-smoke · e2e-kafka) |
| `/masterplan` · `/plan` · `/build` · `/git-save` · `/interview` | psg05 이름 입구 — 마스터플랜 판본 · `/plan-new` · `/task-run` · 커밋 · 기록 · 푸시 · `/req-interview` |
| `/worktree-sync` · `/sync-upstream` | worktree 가 main 을 받기 · 복제본이 Nova 상류 판본을 받기(`python nova.py worktree-sync` · `upstream status\|plan\|apply`) |
| `/deep-audit [범위] [--only 축 \| --skip 축]` | 다축 병렬 심층 감사 — 15개 시각(연결성 · 로직 · 보안 · API · 에러 · 입력 검증 · 데이터 · 성능 · 접근성/토큰 · 테스트 실효 · 문서 정합 · 표준 · 한국어 · 생성물 · 운영)을 읽기 전용 에이전트로 동시에, 처분 5갈래 · 보고 `docs/reviews/`. 분모: `uv run python scripts/audit_scope.py` |
| `python nova.py run` | 로컬 실행(:8080 게이트웨이) |
| `python nova.py new-service <이름> --group <그룹> --scope <범위>` | 서비스 추가 |
| `python nova.py init --name "<이름>" --slug <영문>` | GitHub 템플릿(Use this template)으로 만든 저장소를 새 프로젝트로 초기화(브라우저는 Actions "Nova 프로젝트 초기화") — README "GitHub 템플릿으로 시작하기" |
| `python nova.py gen` | 생성물 전부 다시 만들기 |
| `python nova.py web` · `web-build` · `doctor` | 웹 · 도구 점검 |
| `python nova.py kmp-test` · `kmp-build` · `kmp-smoke` · `kmp-snapshots` | 모바일(KMP) 테스트 · 컴파일 · 실연동 · 화면 PNG (`JAVA_HOME`=JDK 21, Gradle 래퍼) |
| `python nova.py mockups` | 계획서 화면 목업 → PNG (`docs/plans/mockups/<REQ>/*.html`) |
| `python nova.py ui-smoke` | 웹 브라우저 스모크(로그인 → 생성 → 보관/실행 취소 → 권한 오류 …) — 화면을 바꾸면 돌린다. 앞뒤로 `stack up` · `stack down` |
| `python nova.py stack up\|status\|down` · `worktree-new --scratch <이름>` · `worktree-prune [--yes]` | 실행 스택(빈 포트 · 자식까지 정리) · 격리용 작업 폴더(버스 등록) · 병합 끝난 worktree 정리 |

## 이 PC 환경 (Windows)
- `make` 없음 → `python nova.py`. pytest 임시 폴더는 `.pytest_tmp/`(시스템 Temp 권한 문제)
- **셸에서 파일 고치기**: 셸 heredoc 안 파이썬 문자열로 파일을 고치지 않는다(`\n` · `\0` 이 실제 줄바꿈 · NUL 로 들어가 다른 담당의 테스트 수집까지 깨진 사고 2회) — Edit · Write 도구를 쓰고, 여러 곳이면 Write 로 스크래치 폴더에 스크립트를 만들어 실행한다. 셸에서 파이썬을 부를 때는 `< /dev/null` 과 `timeout` 을 붙인다(120초 멈춤 2회)
- 담당 에이전트가 낸 결과(테스트 통과 · 화면 확인)는 main 이 그 명령을 직접 다시 돌려 확인한 뒤 task 를 체크한다
- JDK 21 `C:\Users\han\tools\jdk-21.0.13+9` (명령마다 `JAVA_HOME` 지정) · Gradle 은 저장소 래퍼 `apps/kmp/gradlew`(8.14)
- 3000 포트는 다른 Node 프로그램이 쓰고 있다 → 웹 확인은 3100 포트 + `GW_CORS_ORIGINS=http://localhost:3100`
- Docker Desktop(kubectl 포함)
