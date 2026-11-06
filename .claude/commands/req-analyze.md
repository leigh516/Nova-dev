---
description: 요구 분석 — 인터뷰 · 요청을 요구 문서로 만들고 빌더 점검 · 승인 관문을 거친다(superpowers:brainstorming)
argument-hint: <INT-YYMMDD-NN 또는 REQ-YYMMDD-NN 또는 요구 제목>
---

# /req-analyze — 요구 분석

인자: `$ARGUMENTS`
규칙: [docs/conventions/superpowers.md §4](../../docs/conventions/superpowers.md)

## 절차
1. **스킬 호출**: `superpowers:brainstorming` 의 "Size the Work · The Written Design · Builder check · HARD-GATE" 부분을 따른다. 서면 설계의 위치는 Nova 요구 문서다(`docs/superpowers/specs/` 를 만들지 않는다)
2. 입력을 읽는다: 인터뷰 기록(INT) · 기존 요구(REQ) · 관련 대장(`docs/registry/*.md`) · 표준(`docs/std`)
3. **크기 판정**을 고객 말로 알린다: 빠른 일 · 작은 변경 · 프로젝트. 독립된 프로젝트가 여럿이면 나누고 순서를 정해 하나씩 진행한다
4. 요구 문서: 기존 REQ 가 없으면 `uv run python scripts/docs_new.py req "<제목>"`. 채울 것:
   - 원문(고객 · 사용자의 말 그대로), 입력 자료에 인터뷰 기록 링크
   - **목적과 이유**, **목표 · 비목표 · 반목표**, 사용자(역할 · 기기 · 장소)
   - 요구사항 분해: 하위 ID `REQ-YYMMDD-NN-n`, 요구마다 **확인 가능한 수용 기준**
   - 고객이 정한 방법 / 맡긴 방법 — Claude 가 정한 것은 "Claude 판단"으로 표시
   - 표준 판정 후보(테넌트 · 도메인 팩 · AX 등급)
5. **빌더 점검**: `req-analyst` 에이전트(빌더 점검 모드)에게 Superpowers `brainstorming/builder-check-prompt.md` 형식으로 요구 문서 경로만 주고 "이 문서만으로 계획을 세울 수 있나, 무엇을 물어야 하나"를 받는다. 답은 한국어로 받는다. 받은 질문은 셋으로 나눈다:
   - 이미 답이 있음 → 문서에 채운다
   - 사소함 → Claude 가 정하고 "Claude 판단"으로 표시
   - 고객 몫 → **한 메시지에 중요한 순서로 모아** 묻는다(이 점검에서 묻는 것은 이 한 번뿐)
5-0. 켜진 도메인 팩(`nova.project.json` 의 `packs`)이 있으면 그 팩의 `<팩>-specialist`(팩 이름의 `_` 는 `-`) 에이전트를 같은 메시지에 함께 띄워 업무 규칙 · 용어 · 상태 흐름에 맞는지 본다(업종의 빠진 상태 · 예외 · 규제)
5-1. 같은 쟁점이 질의 · 답을 거쳐도 맴돌면 요구 충돌이다 — Claude 가 정하지 않고 고객 몫으로 넘긴다. 답 과정에서 드러난 가정은 요구 문서 '미결 질문' 또는 '확인한 결정'에 남긴다
6. 답을 "확인한 결정" 표에 남기고, 요구 문서와 "Claude 판단" 목록을 사용자에게 건넨다
7. **승인 관문**: 사용자가 요구 문서를 승인하기 전에는 코드 · 골격 · 설치 · 프로젝트 생성을 하지 않는다. 승인은 "확인한 결정"에 `승인 | YYYY-MM-DD 사용자` 한 줄로 남긴다
8. 인터뷰 기록의 `요구` 칸 · 인터뷰 인덱스의 `요구` 칸을 채우고 `uv run python scripts/docs_index.py --check`
9. 다음: 프로젝트 크기면 `/plan-new "<제목>" REQ-YYMMDD-NN`, 작은 변경이면 기존 tasks 에 🆕 task 를 추가한다
