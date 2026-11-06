# ADR-007 · SOUL 레이어 — 정체성 · 말투를 저장소에 두고 자동 로딩 · 훅으로 강제

| 항목 | 내용 |
|---|---|
| 일자 | 2026-11-04 |
| 상태 | 채택 |
| 대체 | - |
| 요구 | [REQ-261104-08](../requirement/requirement_261104_08.md) |

## 배경
- AI 가 세션마다 '일반 조수'로 다시 나타나 말투 · 판단 원칙이 흔들렸다
- 한국어 규칙(CLAUDE.md 규칙 0)은 이번 작업 중에만 여섯 번 넘게 어겨졌다. 규칙을 적고 훅으로 알리는 것만으로는 뚫렸다
- project-start-guide-05 에는 이를 다루는 SOUL 레이어가 있다
  - 파일 5종: `SOUL.md` · `IDENTITY.md` · `.claude/soul/{USER,STYLE,MEMORY}.md`
  - `CLAUDE.md` 의 `@` 가져오기
  - 응답 검사 훅 persona-guard
  - `/soul-review`
  - `PROJECT.md` · `INTENT`

## 결정
- **5종을 Nova 에 맞게 다시 썼다**: 되돌림 원칙 · 증거 우선 · 방법은 Superpowers / 기록은 Nova · 한국어 규칙을 최우선으로 둔다
- **저장소 안에 둔다**(홈 `~/.claude/` 가 아님) — 다른 프로젝트 세션을 바꾸지 않고, `new-project` 로 물려준다
- **자동 로딩**: `CLAUDE.md` 의 `@SOUL.md` · `@IDENTITY.md` · `@.claude/soul/USER.md` · `@.claude/soul/STYLE.md`. `MEMORY.md` 는 읽는 순서 정본이라 `/session-start` 가 따른다
- **강제**: Stop 훅 `.claude/hooks/persona_guard.py` 가 응답이 끝날 때 다음을 검사하고, 어기면 다시 쓰게 한다
  - 한국어가 아닌 문장 · 금지 첫머리를 본다
  - 코드 · 식별자 · 경로는 검사하지 않는다
  - `stop_hook_active` 면 막지 않고(무한 반복 방지), 고장 나도 세션을 막지 않는다
- **진화는 사람 승인**: `/soul-review`(`scripts/soul_review.py`)는 대화 기록에서 반복 교정을 세어 후보만 낸다. SOUL 파일은 쓰지 않는다
- **사용자 호칭**: psg05 는 사용자를 "Nova"로 불렀지만, 이 저장소에서 Nova 는 플랫폼 이름이므로 "사용자"로 부른다
- **PROJECT · INTENT**
  - `docs/PROJECT.md`: 북극성 2축 · 문제 · 판정형 성공 기준(🔎 · ⏳ · ⚠️)
  - 새 프로젝트는 `docs/_template_PROJECT.md` 로 새로 쓴다
  - INTENT 는 별도 파일이 아니라 **요구 문서의 '의도' 표**(문제 · 결과 · 영향 · 제약 · 미해결)로 넣고, `docs_index` 가 빈칸을 잡는다

## 검토한 대안
| 대안 | 장점 | 단점 | 버린 이유 |
|---|---|---|---|
| CLAUDE.md 에만 규칙 추가 | 단순 | 이미 뚫렸다(실측) | 강제가 없다 |
| 홈 `~/.claude/` 에 SOUL | 모든 프로젝트 공통 | 다른 프로젝트 세션까지 바뀐다 · 새 프로젝트로 안 간다 | 저장소별 정체성이 필요 |
| psg05 persona-guard 그대로(Node) | 검증됨 | Nova 는 Python 도구 체계 · 규칙 집합이 다름 | Python 으로 다시 씀 |
| INTENT 를 별도 파일 · JSON 원장 | psg05 와 같음 | Nova 에는 tasks.json 원장이 없다 · 정본이 둘 | 요구 문서 안의 표로 |

## 결과
- 좋아지는 것: 세션 첫 순간부터 같은 정체성 · 말투로 일한다. 한국어 규칙 위반을 기계가 그 자리에서 잡는다. 반복 교정이 규칙 후보로 올라온다
- 감수하는 것: 응답마다 훅 한 번(짧은 Python 실행). 영어 문장 판정은 휴리스틱이라 드물게 틀릴 수 있다 → 테스트로 경계를 고정하고, 틀린 판정은 기능어 목록으로 고친다
- 지킬 것: SOUL 5종은 사람의 명시 지시로만 바꾼다. 훅을 끄거나 약하게 하려면 요구(REQ)로 남긴다
