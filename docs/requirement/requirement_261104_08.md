# REQ-261104-08 · SOUL 레이어 · PROJECT · INTENT — psg05 를 Nova 에 맞게

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-04 |
| 요청자 | jongyeolhan |
| 원문 | "F:\project-nuri\project-start-guide-05\.claude\soul F:\project-nuri\project-start-guide-05\IDENTITY.md  과 F:\project-nuri\project-start-guide-05\SOUL.md과 PROJECT.md 그리고 INTEND.md등 프로젝트에 필요한  것들이 있는데 이것들을 참조해서 우리 시스템에 맞게 구성을 해서 만ㄷㄹ어주세요" |
| 입력 자료 | psg05 `SOUL.md` · `IDENTITY.md` · `.claude/soul/{USER,STYLE,MEMORY}.md` · `docs/state/PROJECT.md` · `docs/templates/INTENT.template.md`(원문의 INTEND = INTENT) · `.claude/commands/soul-review.md` · `CLAUDE.md` 의 `@` 가져오기 |
| 크기 | 작은 변경(문서 · 훅 · 도구 · 테스트) |
| 상태 | 적용됨(상시 규칙) |
| 계획 | [ADR-007](../adr/ADR-007-soul-layer.md) · [PROJECT](../PROJECT.md) |

## 의도 (INTENT — 해법을 적기 전에)
| 칸 | 내용 |
|---|---|
| 문제 | AI 가 세션마다 일반 조수로 다시 나타나 말투 · 판단 원칙이 흔들린다. 특히 한국어 규칙을 사용자가 여러 번 요구했는데도 계속 어겼다. 프로젝트의 북극성 · 성공 판정을 적는 자리가 없고, 요구를 열 때 "누가 왜 곤란한가"를 해법보다 먼저 적는 칸이 없다 |
| 결과 | 세션 첫 순간부터 같은 정체성 · 말투로 일한다. 한국어 규칙 위반을 기계가 그 자리에서 잡는다. 반복 교정이 규칙 후보로 올라온다. 성공 기준을 근거와 함께 판정한다. 요구마다 곤란함이 먼저 적힌다 |
| 영향 | CLAUDE.md(자동 로딩) · `.claude/settings.json`(Stop 훅) · 요구 템플릿 · `docs_index` 검사 · `new_project`(PROJECT 새로 쓰기) · 모든 세션의 응답 |
| 제약 | SOUL 5종은 사람의 명시 지시로만 바꾼다. 훅은 고장 나도 세션을 막지 않고 끝없이 되풀이하지 않는다. psg05 고유 장치(worktree 버스 · `.collab/memory` · tasks.json 원장 · 부트스트랩 예산 측정)는 옮기지 않는다 |
| 미해결 | 사용자 호칭("Nova"였던 것을 "사용자"로 바꿈)이 맞는지 사용자 확인 |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| 사용자 호칭 | Claude 판단 — psg05 는 사용자를 "Nova"로 불렀지만, 이 저장소에서 Nova 는 플랫폼 이름이므로 "사용자(한종열)"로 부른다(미해결로 확인 요청) |
| INTENT 형태 | Claude 판단 — 별도 파일 · JSON 원장 대신 **요구 문서 안의 '의도' 표**. 정본을 하나로 둔다 |
| 강제 수단 | Claude 판단 — psg05 persona-guard(Node)를 Python Stop 훅으로 다시 씀. 한국어 규칙 · 금지 첫머리만 기계로 본다 |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261104-08-1 | SOUL · IDENTITY | 루트 `SOUL.md`(성격 · 되돌림 원칙 · 일하는 법) · `IDENTITY.md`(역할 · 경계 · 세션 연속성)를 둔다 | ADR-007 |
| REQ-261104-08-2 | `.claude/soul` | `USER.md` · `STYLE.md`(언어 최우선 · 응답 형식 · 금지 첫머리 · 속도 표시) · `MEMORY.md`(읽는 순서 · 두 기록의 역할)를 둔다. CLAUDE.md `@` 가져오기 4종으로 매 세션 싣는다(`test_claude_md_imports_soul_layer`) | CLAUDE.md |
| REQ-261104-08-3 | 강제 | Stop 훅 `persona_guard.py` — 영어 문장 · 금지 첫머리를 잡고 다시 쓰게 한다. 코드 · 식별자는 통과, 되풀이 · 고장 시 막지 않는다(`tests/test_persona_guard.py` 6건) | 훅 |
| REQ-261104-08-4 | 진화 | `/soul-review` · `scripts/soul_review.py` — 대화 기록의 반복 교정을 규칙별로 세어 후보만 낸다. SOUL 파일을 쓰지 않는다(`test_soul_review_counts_repeats_and_never_writes`) | 명령 |
| REQ-261104-08-5 | PROJECT | `docs/PROJECT.md` — 북극성 2축 · 문제 · 사용자 · 판정형 성공 기준(🔎 · ⏳ · ⚠️) · 플랫폼 가치 4축. 새 프로젝트는 `_template_PROJECT.md` 로 새로 쓴다 | PROJECT |
| REQ-261104-08-6 | INTENT | 요구 템플릿에 '의도' 표(문제 · 결과 · 영향 · 제약 · 미해결). `docs_index --check` 가 자리표시 · 빈칸을 잡는다. 이 문서부터 적용 | 요구 템플릿 |
