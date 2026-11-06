# REQ-261104-16 · nicomms 갭 채택 — 토큰 5 · 부품 7 · DashboardPage (v0.2.0)

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-04 |
| 요청자 | jongyeolhan |
| 원문 | "nicomms 갭 17건(토큰 8 · 부품 9) 중 무엇을 Nova 에 실제로 더할지. 토큰 원천을 바꾸는 일이라 승인합니다 /docs-write로 기록하고 v0.2.0 판본에 묶을 감사 후속 요구(REQ-261104-10~12)를 시작해주세요" |
| 입력 자료 | `.claude/skills/nicomms-screen/references/style-map.md` 의 갭 G1~G8 · C1~C9 |
| 크기 | 프로젝트 |
| 상태 | 완료(2026-11-05 — exit-check 4/4 녹색) · v0.2.0 대상 |
| 계획 | 착수 시 /plan-new · 디자인 시스템 [README](../design-system/README.md) |

## 의도 (INTENT — 해법을 적기 전에)
"누가 왜 곤란한가"를 해법보다 먼저 적는다. 이것이 이미 해법을 담고 있으면 문제 진술이 아니다. `미해결` 은 비우지 않는다(없으면 "없음") — `docs_index --check` 가 검사한다.

| 칸 | 내용 |
|---|---|
| 문제 | 운영 콘솔(보안관제 · AI 서버 모니터링)을 Nova 로 만들 때 경보 상태 강조 · 짙은 사이드바 · AI 실행 확인 · 대시보드 차트 · 분할 화면 · 설정 화면 같은 nicomms 화면 형태를 쓸 부품 · 토큰이 없어 화면마다 직접 짜게 된다 |
| 결과 | nicomms-screen 스킬이 갭 없이 조립할 수 있는 토큰 5묶음 · 부품 7 · DashboardPage 가 생기고, 모두 토큰 원천 · WCAG 검사 · ui-smoke 를 거친다 |
| 영향 | design/tokens/brand.tokens.json · 생성물(tokens.css · DesignTokens.kt) · web/packages/ui · apps/kmp/uikit · ui.md §3 · §5 · nicomms-screen 갭 표 · ui-smoke |
| 제약 | 값은 토큰 원천에서만 · 모든 새 색 쌍은 WCAG AA 검사 대상 · 상태색과 도메인 식별색을 섞지 않는다 · AI 확인 카드는 STD-AX 와 서버 require_human 이 짝 |
| 미해결 | 없음 — 미룬 5건(G1 · G3 · G8 · C2 · C6)은 이유와 함께 '하지 않는 것'에 둔다 |

## 목적과 이유
nicomms-screen 스킬을 들였지만 Nova 에 대응 토큰 · 부품이 없어 갭 17건이 남았다. 사용자가 토큰 원천 변경을 승인했고, 업무(관제 · 모니터링 콘솔)에 쓰이는 것부터 넣는다.

## 종료 조건 (exit)
이 요구가 **끝나는** 조건. 1~7개, 한 번 돌리거나 한 번 보고 답이 나오는 것만(소진형 금지). 모두 녹색이면 닫고, 새로 보인 것은 새 요구로 — `python nova.py exit-check REQ-261104-16` · [plans README §5](../plans/README.md).
| ID | 확인 | 기대 | 방식 | 판정 |
|---|---|---|---|---|
| E1 | python nova.py test | 통과 | 명령 | 충족 2026-11-05 — 저장소 434 · 공통 120 · 게이트웨이 43 · 샘플 18 통과(관문 check) |
| E2 | python nova.py lint | 통과(새 토큰 쌍 WCAG AA 포함) | 명령 | 충족 2026-11-05 — lint 통과 · WCAG 2.2 AA 대비 148쌍 |
| E3 | python nova.py ui-smoke | 통과(새 부품 화면 포함) | 명령 | 충족 2026-11-05 — 브라우저 시나리오 통과 15단계(main 직접 실행) |
| E4 | 디자인 갤러리에서 새 부품 · DashboardPage 를 라이트 · 다크로 열어 본다 | 깨짐 없음 | 사람 | 충족 2026-11-05 — 사용자가 /design · /design/dashboard 를 라이트 · 다크로 확인 |

## 목표 · 비목표 · 반목표
| 구분 | 내용 |
|---|---|
| 목표 | nicomms 운영 콘솔 형태를 Nova 토큰 · 부품만으로 조립 |
| 비목표(하지 않을 것) | G1 형 축(neo · glendale — ADR 감, 소비 프로젝트 둘 이상일 때) · G3 그라데이션(대비 검사 쌍 정의 불가) · G8 제목 글꼴(한국어 라이선스 확인 먼저) · C2 MDI 탭(무겁고 웹 흐름과 충돌) · C6 밀러 칼럼 · 트리(소비 화면 없음) |
| 반목표(돌아가도 실패인 것) | 화면 · 스킬에 색 값이 직접 들어가는 것 · 다크에서 대비가 깨지는 것 |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| 계획 판단 포인트 — A 도메인 식별색 | 번호 슬롯 `domain.1~6.mark/text`, 모듈 → 번호 매핑은 데이터 (권고 채택 2026-11-04) |
| 계획 판단 포인트 — B 솔리드 상태색 | 다크 전용 값(밝은 단계 + 검은 잉크, 모드별 onSolid) (권고 채택 2026-11-04) |
| 계획 판단 포인트 — C 테넌트 전환 | 부품 자리(tenants · onSwitch)만, 서버 재발급 API 는 새 요구 (권고 채택 2026-11-04) |
| 계획 판단 포인트 — D AI 확인 카드 보증 | 부품 계약 + 기존 서버 require_human 테스트(정적 검사기는 새 요구) (권고 채택 2026-11-04) |
| 계획 판단 포인트 — E 모바일 범위 | 토큰 + 부품 4(Badge solid · AiMark · AiConfirmCard · DomainTag) (권고 채택 2026-11-04) |
| 계획 판단 포인트 — F 구체 값 | 계획 §1.1 후보를 기본값으로(프로젝트 브랜드에서 바꾼다) · G4 토큰 6개(요구 16-2 수용 기준에 반영) · lint 검사 확장(분리 · 토큰 밖 색) 승인 (권고 채택 2026-11-04) |
| 갭 17건 중 무엇을 넣나 | 토큰 5 · 부품 7 · DashboardPage 채택, 5건 미룸 — Claude 권고를 사용자가 승인한 범위(토큰 원천 변경 승인 2026-11-04) |

## 요구사항 분해
하위 ID 는 `REQ-261104-16-n` 형식으로 쓴다.

| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261104-16-1 | G2 솔리드 상태 배경: color.status.<상태>Solid · onSolid | 대비 검사 통과 | (착수 시) |
| REQ-261104-16-2 | G4 딥 사이드바 톤: color.bg.nav · text.onNav · onNavMuted + AppShell navTone | side 레이아웃에서 두 모드 | (착수 시) |
| REQ-261104-16-3 | G5 + C9 AI 표식 · 실행 확인 카드: color.ai.* · 표식 부품 · 확인 카드(대상 · 범위 · 되돌림 · 취소) | STD-AX L2 화면에서 서버 require_human 과 짝 | (착수 시) |
| REQ-261104-16-4 | G6 도메인 식별색: color.domain.<모듈> · <모듈>Text + 상태색과 섞지 않는 규칙 | 규칙 검사 | (착수 시) |
| REQ-261104-16-5 | G7 + DashboardPage: color.chart.1~6 · Stat · 차트 블록 템플릿 | ui.md §5 ✅ | (착수 시) |
| REQ-261104-16-6 | C1 헤더 유틸: 알림 · 테넌트 전환(STD-TENANCY) · 헤더 검색 | AppShell 슬롯 | (착수 시) |
| REQ-261104-16-7 | C3 목록 내보내기: ListPage 내보내기(CSV) 행동 | 권한 · 개인정보 가림 | (착수 시) |
| REQ-261104-16-8 | C4 스플릿 뷰 · C5 설정형 슬롯 템플릿: SplitPage · SettingsPage | ui.md §5 ✅ | (착수 시) |
| REQ-261104-16-9 | C7 폼 모달 · 크기 단계: FormDialog(useDialogFocus) | 포커스 가두기 · Esc | (착수 시) |
| REQ-261104-16-10 | C8 로그인 확장: 아이디 저장 · 찾기 · 전환 링크(LoginPage 설정) | 운영 빌드 데모 계정 없음 유지 | (착수 시) |

## 방법 — 고객이 정한 것 / 맡긴 것 / Claude 판단
| 항목 | 정한 사람 | 내용 |
|---|---|---|

## 미결 질문
| 질문 | 누구 몫 | 답 |
|---|---|---|

## 추가 요청 (같은 날)
| 원문 | 반영 |
|---|---|

## 적용 · 결과
- 2026-11-05 완료 — plan_REQ_05 0~6단계(진척 44 / 54, 남은 것은 다음 판본 🆕 T05-9.01~9.08)
  - 토큰 5묶음(솔리드 · 딥 사이드바 · AI · 도메인 · 차트, 대비 148쌍) · 웹 부품 · 템플릿(DashboardPage · SplitPage · SettingsPage · 헤더 유틸 · FormDialog · AiConfirmCard · 로그인 확장 · CSV 내보내기) · 모바일 부품 4 · 갤러리 · ui.md 규칙 11~13 · nicomms 갭 12건 해소
  - `python nova.py exit-check REQ-261104-16` → E1~E4 모두 충족(E1 test 는 tasks_REQ_04 담당 4명이 동시에 편집하던 중에 돈 결과 — 다음 관문 check 가 다시 본다)
  - 이력: [history_261105_01](../history/history_261105_01.md) · [history_261105_02](../history/history_261105_02.md)
