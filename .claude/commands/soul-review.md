---
description: SOUL 진화 검토 — 사용자가 반복해서 한 교정을 세어 SOUL · STYLE · 규칙의 개정 후보로 낸다. 감지는 자동, 반영은 사람 승인. SOUL 파일을 스스로 고치지 않는다
argument-hint: (선택) --min-repeats N · --transcript <파일>
---

# /soul-review — SOUL 진화 검토

같은 교정을 사용자가 **몇 번이나 다시 말하게 했는가**를 세어, 규칙으로 올릴 후보를 낸다. 산출은 **제안**이지 SOUL 파일 편집이 아니다.
결정: [ADR-007](../../docs/adr/ADR-007-soul-layer.md) · 규칙: `.claude/soul/review-rules.json`

> 🔴 이 명령은 `SOUL.md` · `IDENTITY.md` · `.claude/soul/{USER,STYLE,MEMORY}.md` 를 **쓰지 않는다**. 정체성은 사람이 명시로 지시할 때만 바뀐다. `tests/test_soul.py` 가 도구가 파일을 바꾸지 않는지 검사한다.

## 절차
1. `uv run python scripts/soul_review.py` 를 실행한다. 한 번만 기준을 낮추려면 `--min-repeats 2`, 대화 하나만 보려면 `--transcript <파일>` 을 쓴다
2. 후보마다 세 가지를 묻는다(판단은 사용자)
   | 물음 | 갈래 |
   |---|---|
   | 말투 · 정체성 축인가, 절차 축인가 | SOUL · STYLE ↔ CLAUDE.md · 명령 |
   | 규칙이 **없는가**, 있는데 **안 실렸는가**, 실렸는데 **안 지켜지는가** | 새로 씀 ↔ 싣기(`@` 가져오기) ↔ 강제(훅 · 게이트) |
   | 지금 고칠 것인가 | 제안 ↔ 기각(이유를 남긴다) |
   - 예: "한국어로"가 여러 번 나왔다면 규칙은 이미 있고 실려 있다. 그런데도 안 지켜졌다면 → **강제** 갈래(`persona_guard.py` 의 판정 보강)
3. 사용자에게 후보를 한국어로 보여 준다: 반복 수 · 인용 · 어느 파일에 무엇을 바꿀지(변경 전 → 후) · 비용
4. **승인을 받은 것만** 고친다. 고친 뒤 `/req-new` 로 남기고(원문 = 사용자의 반복 교정), 강제가 필요하면 훅 · 테스트를 함께 바꾼다
5. 승인하지 않은 후보는 이유와 함께 보고에만 남긴다

## 관련
- 응답 검사 훅: `.claude/hooks/persona_guard.py`(Stop) · 테스트 `tests/test_persona_guard.py`
- 개인 기억(저장소 밖): `~/.claude/projects/<이 저장소>/memory/` — 반복되면 이 명령으로 저장소 규칙 후보가 된다
