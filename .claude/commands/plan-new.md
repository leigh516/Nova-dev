---
description: 새 세부 계획 + task 체크리스트 만들기 (§4 형식)
argument-hint: <계획 제목> REQ-YYMMDD-NN
---

# /plan-new — 세부 계획 만들기

인자: `$ARGUMENTS` (제목과 요구 ID)

## 절차
0. **스킬 호출**: `superpowers:writing-plans` 의 원칙(파일 구조 · 인터페이스 · 전역 제약 · 검토 초점 · 자체 점검)을 따른다. 저장 위치는 `docs/superpowers/plans/` 가 아니라 아래 Nova 파일이다. 요구가 승인되지 않았으면(`/req-analyze` 승인 관문) 먼저 승인을 받는다
0-1. **자문**(`practice-advisor` 에이전트 — 켜진 팩이 있으면 0-2 와 같은 메시지에): ① 의뢰 충실도(원문과 다른 것을 넣지 않았나) ② 놓친 관점(운영 · 권한 · 감사 로그 · 마이그레이션 · 삭제/보존 · 장애 · 한국 규제) ③ 기회. 안 하는 관점은 §9 범위 밖에 이유와 함께, 기회는 `/req-new`
0-2. 켜진 도메인 팩(`nova.project.json` 의 `packs`)이 있으면 그 팩의 `<팩>-specialist`(팩 이름의 `_` 는 `-`) 에이전트를 같은 메시지에 함께 띄워 업무 규칙 · 용어 · 상태 흐름에 맞는지 본다 — 계획에 업종 규칙이 빠졌거나 코어에 업종 분기를 넣으려 하면 여기서 잡는다
1. `uv run python scripts/docs_new.py plan "<제목>" --req <REQ-ID>` → `plan_REQ_NN.md` + `tasks/tasks_REQ_NN.md` + `plan_index.md`
2. **영향분석(§0)부터**: `python nova.py impact <대상 낱말…>`(5줄 초안 — 대상 · 직접 · 간접 · 등급 힌트 · 갱신 산출물, 넓으면 `contract-auditor` 에이전트)로 시작하고, 관련 코드 · 원장(`docs/registry/README.md`) · **대장 4종**(`docs/registry/screens.md` · `db-dictionary.md` · `permissions.md` · `events.md`)을 조회해 대상 · 직접/간접 영향 · 등급을 쓰고, **표준 판정**(`docs/std` — 테넌시 · 도메인 팩 · AX 등급)을 적는다
2-1. **이름 조회**: 새 표 · 개체 · 토픽 · 권한이 있으면 `python nova.py naming lookup <개념…>` 결과(정확 · 별칭 · 유사 · 은퇴 · 없음)를 §0 · §7 에 인용한다 — 정확 · 별칭이면 새로 만들지 않고, 없음이면 사람 승인 후 등재([naming.md](../../docs/conventions/naming.md))
3. §8 재사용 — 새로 만들기 전에 원장에서 이미 있는 테이블 · API · 컴포넌트를 찾는다. 코드 · 외부 대안을 넓게 훑어야 하면 `researcher` 에이전트(결론과 근거만 돌려받는다)
4. 화면이 있으면(화면 목록 · 골격은 `screen-architect` 에이전트, 디자인 축이 넓으면 `design-director`, 밖의 사례는 `design-researcher`) `nova-screen` 스킬 §3 을 따라 §4 에 지금 화면 ↔ 목업 이미지(`docs/plans/mockups/REQ_NN/*.html` → `uv run python scripts/mockup_shots.py`)와 **4.1 UX 점검**(H1~H10 · 과업 시나리오)
5. §7 데이터 모델 mermaid erDiagram(표 설계는 `database-architect` 에이전트), §10 테스트 맵
6. task 분해(본문 초안은 `task-planner` 에이전트에 맡겨도 된다 — 파일은 1번에서 main 이 만든 것): 한 줄 한 가지 일, ID `T<NN>-<단계>.<순번>`, 끝난 기준 괄호
   - **검사 묶음 설계**(REQ-261104-17): ① 같은 테스트 파일 · 모듈을 건드리는 task 를 한 단계로 모은다(단계 = 검사 묶음, task 3~9개) ② 코드 task 의 끝난 기준에 테스트 경로나 이름(`tests/test_x.py::이름` · `test_이름` · KMP 는 `…Test.kt`)을 적는다 ③ 단계 끝에 `**단계 관문**` 한 줄(`quick --stage T<NN>-<단계>` → 전체 `check` → 커밋 묶음 · 푸시) — task 하위 줄에 커밋을 두지 않는다 ④ 하위 프로세스 · 저장소 복제 · 실제 DB 를 쓰는 테스트는 §10 테스트 맵에 `slow` 로 표시하고 처음부터 `@pytest.mark.slow` 로 쓴다. 형식은 lint `quick_check.py --check-tasks` 가 검사한다
7. 마스터플랜 §5 에 계획을 추가하는 초안을 `drafts/` 에 만들고(`nova-masterplan` 스킬 · 본문 초안은 `masterplanner` 에이전트) 사용자 확인 후 `python nova.py masterplan adopt …` 로 채택(README §1)
7-1. 요구의 **종료 조건 표**를 확인한다 — `python nova.py exit-check REQ-… --dry`. 계획의 task 가 종료 조건 밖으로 넓어지면 그것은 다음 요구다
8. §11.1 전역 제약 · §11.2 검토 초점을 채우고 §11.3 자체 점검을 한다. task 에는 파일 · 인터페이스 · TDD 하위 단계를 쓴다(작은 task 는 한 줄)
9. 사용자에게 계획 요약과 §4 화면 미리보기를 보여 주고, **실행 방식**(subagent / native — 추천 1개와 이유)을 물어 확인을 받은 뒤 `/task-run` 으로 착수
