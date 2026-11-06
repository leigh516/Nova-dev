# ADR-016 · 디자인 킷 축 — 토큰 한 벌 덮어쓰기 · nicomms G1 해소

| 항목 | 내용 |
|---|---|
| 일자 | 2026-11-06 |
| 상태 | 채택(사용자 2026-11-06 "디자인킷을 권고로 구현해주세요") |
| 대체 | 없음 |
| 요구 | [REQ-261106-04](../requirement/requirement_261106_04.md) |
| 문서 ID | ADR-016 |
| 생성 | 2026-11-06 · `docs_new.py adr` |
| 위치 | `docs/adr/ADR-016-nicomms-g1.md` |
| 원천 | 2026-11-06 사용자 원문("첨부한 것을 심층분석해서 우리 디자인킷에서도 표준킷으로 선정하면 사용할수있도록 하고 checklist.html에 …") · 사용자 결정(안 A · 원본 값은 킷 경로만 예외 · 체크리스트에서 설정 → /foundation 에서 확인 · 다시 설정) · 첨부 assets.zip(sha256 4e0406bc9351151e192a53fcd450f21ac522c5600047ebd337dc60781cacceb6) newtype.css · 같은 날 design-asset-keeper 판정(newtype 대비 통과 · 경계선 line-2 1.53 미달) |
| 연결 | 상위 [REQ-261106-04](../requirement/requirement_261106_04.md) · 해소하는 갭 nicomms style-map G1(`.claude/skills/nicomms-screen/references/style-map.md`) · 디자인 시스템 [README 2.1절](../design-system/README.md) · 규약 [ui.md](../conventions/ui.md) · 기록 형식 [ADR-004](ADR-004-ledger-formats.md) · 명령 `/foundation`(`.claude/commands/foundation.md` 5단계) · 도구 `scripts/gen_tokens.py` · `scripts/kits.py`(`python nova.py kit`) |

## 배경
- Nova 는 브랜드 한 벌(`design/tokens/brand.tokens.json`)만 받는다. 고객이 쓰고 싶은 디자인 킷(이번에는 초록 콘솔 newtype)이 있어도 고르는 길이 없고, 체크리스트에서 골라도 채택되지 않았다
- nicomms 스킬 style-map 은 형 축(neo · glendale 같은 '분위기 한 벌')을 **갭 G1** 로 남겨 두었다 — 받을 자리가 없어 '구조 변경이라 ADR 감'으로 미뤘다
- 제약: 원본 CSS · JS 는 들이지 않는다(jQuery · CDN · 접근성 결함) · 화면은 의미 토큰만 쓴다 · WCAG 2.2 AA 를 자동 검사한다 · 기본 모습(nova)의 생성물은 바뀌면 안 된다 · nicomms '원본 값 금지' 원칙

## 결정
**안 A — 킷 = 토큰 한 벌(`brand.tokens.json` 위에 덮는 부분 트리) + 부품 갭 목록.** 의미 토큰 이름은 그대로 두고 원시값(필요하면 의미 토큰의 참조)만 덮는다. G1 의 '형 축'을 별도 `nova.styles` 확장 대신 이 킷 축으로 받는다.
- 목록 `design/tokens/kits/catalog.json`(id · label · desc · tokens · preview · gaps · status), 킷 파일 `design/tokens/kits/<id>.tokens.json`
- 선택은 `nova.project.json` `design: {kit, date, by, source}` — 없으면 `nova`. 생성기 `gen_tokens.py` 가 고른 킷을 합쳐 `tokens.css` · `DesignTokens.kt` 를 만든다. `nova` 면 킷 기능 전과 같은 바이트
- **채택 흐름**: 요구 체크리스트에서 고르면 import 가 `kits.use(…, source="checklist")` 로 설정 → `/foundation` 5단계가 `python nova.py kit show` 로 킷 · 출처를 보여 **확인받는 관문**(건너뛰지 않는다 — 놓침 방지) → 바꾸려면 `python nova.py kit use <id>`, 설정이 없으면 그 단계에서 고른다
- **검사**: `gen_tokens.py --check`(lint)가 목록의 **모든 킷**을 대비 · 분리 · 정보 ↔ 성공 상태색 겹침으로 검사한다. 미달 킷은 고르지 않았어도 lint 실패, `kit use` 는 미달 킷 · 모르는 id 를 거부한다
- **원본 값 예외는 킷 경로만**: nicomms '원본 값을 들이지 않는다'는 그대로이고, 예외는 `design/tokens/kits/*.tokens.json` 에 **토큰 값**(hex · px · 글꼴 이름)으로 옮기는 것뿐이다. 값마다 원본 변수를 적고, 대비 미달 값은 조정해 조정 전 → 후를 남긴다(newtype: 경계선 line-2 `#C9D3CF` 1.53 → `#7A8682` 3.48). 반투명 색은 바탕 위에 합성한 불투명 hex 로 옮긴다. 원본 자료는 저장소 밖에 두고 출처(파일 · sha256)만 적는다
- 새 프로젝트(`new-project` · 템플릿 init)는 원본이 고른 킷을 물려받지 않고 `nova` 로 시작한다

## 검토한 대안
| 대안 | 장점 | 단점 | 버린 이유 |
|---|---|---|---|
| A. 킷 = 토큰 한 벌 덮어쓰기 + 부품 갭(채택) | 화면 코드 그대로 · 대비 검사 · 다크 · 모바일이 따라온다 · 되돌리기 한 줄 | 킷의 그림자 · 유리 질감 같은 형(form)은 의미 토큰이 없어 옮기지 못한다 | — |
| B. 원본 CSS · JS 를 그대로 들여 킷별 스타일시트로 | 원본과 똑같은 모습 | jQuery · CDN · 접근성 결함을 함께 들인다 · 토큰 밖 색 · 대비 검사 불가 · 모바일 없음 | 제약(원본 이식 금지 · 의미 토큰) 위반 |
| C. G1 원안 — 의미 반경 · 표면 · 그림자 토큰 + `nova.styles` 모드 확장 | 형 축까지 표현 | 의미 토큰 체계 · 생성기 · 모든 부품을 바꾸는 큰 구조 변경, 소비 프로젝트가 아직 하나 | 지금 필요한 것(색 · 반경 한 벌 고르기)보다 크다 — 형이 둘 이상 필요해지면 다시 연다 |
| D. 프로젝트마다 `brand.tokens.json` 을 손으로 고친다 | 새 장치 없음 | 고르는 목록 · 체크리스트 연결 · 되돌리기가 없고 킷이 프로젝트 사이에서 재사용되지 않는다 | 요구('표준 킷을 선택하면 채택') 미충족 |

## 결과
- 좋아지는 것: 체크리스트 → `/foundation` 확인 → 생성물까지 한 줄로 이어진다 · 대비 미달 킷이 고를 수 있는 상태로 남지 않는다 · 브랜드가 초록인 킷의 정보 = 성공 색 겹침을 기계로 잡는다 · nicomms G1 이 '킷 축'으로 닫힌다
- 감수하는 것: 그림자 · 유리 질감 · 글자 크기 단계 같은 형은 옮기지 않는다(newtype 의 `--nt-glass` · `--nt-sel` 등) · 원본 값 일부를 조정해 원본과 조금 다르다 · 부품 갭(newtype: `datepick` · `daterange`)은 따로 만들어야 한다
- 이후 지킬 규칙: 킷은 의미 토큰 이름을 새로 만들지 않는다(필요하면 기본 원천에 먼저 · 대비 쌍과 함께) · 킷 파일 밖에 원본 값을 두지 않는다 · 킷을 더하거나 고치면 `gen_tokens.py --check` 녹색 · 상태 '채택'은 사용자 확인 뒤
- 되돌리기: 프로젝트는 `python nova.py kit use nova`(생성물이 기본 바이트로 돌아간다 — 2026-11-06 `git diff --stat` 차이 0 확인). 장치 자체를 걷으려면 `design/tokens/kits/` · `scripts/kits.py` 와 `gen_tokens.py` 의 킷 합치기를 되돌린다(기본 킷 생성물은 바뀌지 않으므로 생성물 재생성 없이 끝난다)
