# 디자인 시스템

업계 모범 사례를 Nova 의 웹(Next.js) + 모바일(KMP) 구성에 맞게 고른 것. 화면 구성 규약은 [ui.md](../conventions/ui.md), UX 원칙은 [ux-heuristics.md](../conventions/ux-heuristics.md).

## 1. 도입한 모범 사례
| # | 모범 사례 | 근거 | Nova 적용 |
|---|---|---|---|
| 1 | **토큰 단일 원천 + 표준 형식** | W3C Design Tokens Community Group 형식 2025.10 안정판(JSON, `$value` · `$type`, `{참조}`) | `design/tokens/brand.tokens.json` 하나에서 웹 CSS · KMP Kotlin 생성(`scripts/gen_tokens.py`). 생성물은 손으로 고치지 않는다 |
| 2 | **3계층 토큰**(원시 → 의미 → 컴포넌트) | 컴포넌트가 의미 토큰만 참조해야 테마 변경이 한 곳에서 끝난다 | `primitive.*`(팔레트 · 간격 · 반경 · 글꼴) → `semantic.*`(`color.text.primary`, `color.action.primary`, `color.status.dangerFg` …) → 컴포넌트는 의미 토큰만 |
| 3 | **역할(의도) 이름** | 값이 아니라 용도로(`text.muted` ✓, `gray500` ✗) | 의미 토큰은 모두 역할 이름 |
| 4 | **모드(라이트 · 다크)는 의미 계층에서** | 원시 팔레트는 하나, 모드별로 의미 토큰이 다른 원시값을 가리킴 | `$extensions["nova.modes"].dark` — 웹은 `prefers-color-scheme` + `data-theme`, 모바일은 `LightColors` / `DarkColors` |
| 5 | **접근성 기준을 토큰 단계에서 강제** | WCAG 2.2 AA: 본문 대비 4.5:1, 큰 글자 · UI 경계 · 포커스 3:1(1.4.3 · 1.4.11), 대상 크기 최소 24×24px(2.5.8), 모바일 터치 44pt/48dp | 생성기가 `contrast` 쌍을 라이트 · 다크 모두 계산해 미달이면 실패. `size.target.web`=24, `size.target.touch`=44. 전역 `:focus-visible` 링, `prefers-reduced-motion` |
| 6 | **간격 · 크기 척도(4pt 격자) · 타입 스케일** | 정해진 단계만 → 화면 간 리듬 통일 | `space` 0 · 4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48, `radius` sm · md · lg · xl · pill, `font.size` xs ~ 3xl |
| 7 | **컴포넌트 API 일관성** | 같은 개념은 같은 이름 · 속성 | `variant`(primary · secondary · ghost · danger) · `size`(sm · md · lg) · 상태(default · hover · pressed · focus · disabled · loading · error) |
| 8 | **아토믹 계층** | 화면은 조립만 | 토큰 → 컴포넌트 → 템플릿 → 화면 |
| 9 | **문서 · 카탈로그** | 한 화면에서 보고 비교해야 재사용된다 | 웹 샘플 앱 `/design` 갤러리(`/design/dashboard` · `/design/split` · `/design/settings` 포함)(컴포넌트 전부) |
| 10 | **상태색 ≠ 식별색** | 색 하나에 뜻 하나 — 위험(빨강 · 주황)과 '모듈 3번'이 같은 색이면 운영자가 경보를 잘못 읽는다(WCAG 1.4.1 색만으로 뜻 전달 금지와 같은 뿌리) | `gen_tokens` 가 두 가지를 lint 로 막는다: ① **분리 검사**(`check_separation`) — 도메인 식별색(`color.domain.*`) · 차트색이 상태색(`color.status.*`)과 같은 값 · 같은 원시 참조를 쓰면 실패 ② **사용 검사**(`scan_usage`) — 한 CSS 규칙 · 한 줄에 상태 토큰과 도메인 토큰을 섞으면 실패, 토큰 밖 색(hex · rgb 하드코딩)도 실패(허용 목록 `ALLOW_RAW`). 솔리드 상태색(`*Solid` + `onSolid`)은 경보 강조에만 — 화면당 한 곳 권장 |
| 11 | **거버넌스** | 정기 감사 · 변경 이력 · 폐기 절차 | 토큰 변경은 `gen_tokens.py --check` 통과 필수(lint), 폐기 토큰은 한 릴리스 동안 유지 후 삭제, 변경은 history 에 기록 |

## 2. 프로젝트 브랜드 입히기
1. `design/tokens/brand.tokens.json` 의 `primitive.color.brand` · `accent` 팔레트 값을 브랜드 색으로 바꾼다(의미 토큰 · 이름은 그대로)
2. `font.family` 를 브랜드 글꼴로
3. `uv run python scripts/gen_tokens.py` — 대비 검사에서 실패하면 단계(50~900) 값을 조정
4. 화면 코드는 바꿀 필요가 없다(의미 토큰만 쓰므로)

## 2.1 디자인 킷 — 토큰 한 벌을 골라 채택 (REQ-261106-04 · [ADR-016](../adr/ADR-016-nicomms-g1.md))
킷 = **토큰 한 벌**(`brand.tokens.json` 위에 덮는 부분 트리) + **부품 갭**(그 킷이 원하는데 Nova 에 없는 부품). 원본 CSS · JS 는 들이지 않고 색 · 반경 · 글꼴 값만 옮긴다. 화면 코드는 의미 토큰만 쓰므로 킷을 바꿔도 화면 코드는 그대로다.

| 파일 | 원천 / 생성물 | 내용 |
|---|---|---|
| `design/tokens/kits/catalog.json` | 원천(손으로) | 킷 목록 — `id` · `label` · `desc` · `tokens`(덮어쓰기 파일, 기본 킷은 `null`) · `preview`(체크리스트 미리보기 — `hex` · `radius` 반경 토큰 이름 · `gap` 간격 토큰 번호 · `dark`) · `gaps`(`scripts/checklist_form/tree.json` `parts.need` 보기 ID) · `status` |
| `design/tokens/kits/<id>.tokens.json` | 원천(손으로) | 덮어쓰기 부분 트리 — `brand.tokens.json` 과 같은 경로 · 같은 의미 토큰 이름. 사전은 재귀로 합치고 값은 킷 값으로 바꾼다 |
| `nova.project.json` `design` | `kit use` 가 쓴다 | `{kit, date, by, source}` — `source` 는 `checklist`(체크리스트 import) · `manual`(`kit use`) · `default`(새 프로젝트 기본). 키가 없으면 `nova` |
| `tokens.css` · `DesignTokens.kt` | 생성물(`python nova.py tokens`) | 고른 킷으로 만든다. 킷이 `nova` 면 킷 기능 전과 같은 바이트 |

**고르는 흐름 — 체크리스트에서 설정 → `/foundation` 에서 확인 · 다시 설정**
1. 요구 체크리스트 디자인 절에서 킷을 고르면 import 가 `kits.use(<id>, source="checklist")` 로 설정한다(대비 통과 킷만)
2. `/foundation` 5단계는 이 설정을 **건너뛰지 않는 확인 관문**이다 — `python nova.py kit show` 로 킷 · 출처 · 날짜 · 부품 갭을 보이고 사용자가 확인한다. 바꾸려면 `python nova.py kit use <id>`, 설정이 없으면(체크리스트를 안 했으면) 이 단계에서 고른다
3. `python nova.py kit list` — 목록 · 지금 고른 킷(●)

**대비 · 분리 검사** — `gen_tokens.py --check`(lint)는 고른 킷의 생성물이 최신인지에 더해 **목록의 모든 킷**을 라이트 · 다크로 대비(`contrast` 쌍) · 분리(상태 ↔ 도메인) · **정보 ↔ 성공 상태색 겹침**(`infoFg/Bg/Solid` ↔ `successFg/Bg/Solid` 이 같은 값 · 같은 원시 참조면 실패 — 브랜드가 초록이면 정보색이 성공색과 겹친다)으로 검사한다. 미달 킷이 목록에 있으면 고르지 않았어도 lint 가 실패하고, `kit use` 는 미달 킷 · 목록에 없는 id 를 거부한다.

**새 킷 더하기**
1. 원본 자료에서 색 · 반경 · 글꼴 값을 뽑아 `design/tokens/kits/<id>.tokens.json` 에 덮어쓰기로 적는다 — 반투명(rgba) 색은 놓일 바탕 위에 합성한 불투명 hex 로(대비를 계산할 수 있게), 값마다 원본 변수를 `$description` 에
2. `catalog.json` 에 항목을 더한다(`gaps` 는 `tree.json` `parts.need` 의 실제 보기 ID)
3. `uv run python scripts/gen_tokens.py --check` — 미달 쌍이 나오면 그 값을 조정하고 조정 전 → 후를 `$description` 에 남긴다
4. 원본 자료는 저장소 밖에 두고 출처(파일 이름 · sha256)만 적는다

**되돌리기** — `python nova.py kit use nova`(생성물이 기본 킷 바이트로 돌아간다 · `nova.project.json` `design` 은 `kit: nova` 로 남는다). 2026-11-06 `kit use newtype` → `kit use nova` 뒤 `git diff --stat` 으로 생성물 차이 0 을 확인했다.

| 킷 | 모습 | 부품 갭 | 조정 |
|---|---|---|---|
| `nova` | 인디고 · 중립 회색 | 없음 | — |
| `newtype` | 초록 콘솔(짙은 초록 사이드바 · 초록 강조) · 정보는 파랑 | `datepick` · `daterange` | 컨트롤 경계 line-2 `#C9D3CF`(1.53) → `#7A8682`(라이트 3.48 · 다크 4.15) · 사이드바 보조 글자 → `#CFE7DC` · 다크 soft 색은 표면 `#1D2522` 위 합성 hex. 출처 첨부 assets.zip(sha256 4e0406bc…) `newtype.css` |

## 3. 사용법
```bash
uv run python scripts/gen_tokens.py          # 토큰 수정 후 생성 + 대비 검사
uv run python scripts/gen_tokens.py --check  # lint: 생성물 최신 여부 + 목록의 모든 킷 대비 · 분리 · 상태색 겹침
python nova.py kit list | show | use <id>     # 디자인 킷(2.1절)
```
- 웹: `@nova/ui/styles.css` 가 `tokens.css` 를 불러온다. 스타일은 `var(--color-…)` · `var(--space-…)` 만
- 모바일: `<kt_package>.uikit.LightColors / DarkColors / Dimens` (생성물 `DesignTokens.kt`)

## 4. 출처
- [Design Tokens specification reaches first stable version (W3C DTCG, 2025-10-28)](https://www.w3.org/community/design-tokens/2025/10/28/design-tokens-specification-reaches-first-stable-version/)
- [Design Tokens Format Module 2025.10](https://www.w3.org/community/reports/design-tokens/CG-FINAL-format-20251028/)
- [WCAG 2.2 — Understanding Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
- [Nielsen Norman Group — 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)
