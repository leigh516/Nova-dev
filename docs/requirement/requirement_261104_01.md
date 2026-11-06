# REQ-261104-01 · Superpowers 설치 · 활용 — 고객 인터뷰 · 요구 분석부터 전 과정

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-04 |
| 요청자 | jongyeolhan |
| 원문 | "Superpowers를 설치하고 우리 프로젝트에서 활용을해 고객의 요구사항분석이나 인터뷰등 superpowers가 가지고있는 기능을 전부활용할수있게해주세요" |
| 입력 자료 | Superpowers 플러그인 v7.0.0(`superpowers@claude-plugins-official`, 사용자 범위에 이미 설치됨) — 스킬 15종 |
| 크기 | 작은 변경(규칙 · 명령 · 템플릿 — 제품 코드 변경 없음) |
| 상태 | 적용됨(상시 규칙) |
| 계획 | [superpowers.md](../conventions/superpowers.md) · [ADR-005](../adr/ADR-005-superpowers-workflow.md) |

## 목적과 이유
고객 인터뷰부터 마무리까지 매번 같은 방법으로 일하게 한다. 묻는 방법, 계획을 쓰는 방법, TDD, 검토, 디버깅, 완료 증명이 모두 포함된다. Superpowers 가 이 방법들을 가지고 있으므로 Nova 의 기록 체계에 연결한다.

## 목표 · 비목표 · 반목표
| 구분 | 내용 |
|---|---|
| 목표 | Superpowers 스킬 15종을 모두 Nova 단계 · 명령에 연결한다. 특히 고객 인터뷰와 요구 분석을 명령과 문서로 만든다 |
| 비목표 | 스킬 본문을 복사해 고치지 않는다(상위 개선을 받기 위해) |
| 반목표 | 정본이 둘로 갈리는 것(`docs/superpowers/` 와 Nova 문서), 영어 기록 — 동작해도 실패로 본다 |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| 설치 범위 | Claude 판단 — 사용자 범위 설치는 이미 있었다(v7.0.0). 팀 · 새 프로젝트에 퍼지도록 저장소 `.claude/settings.json` 에서도 켠다 |
| 산출물 위치 | Claude 판단 — Nova 문서 위치를 쓴다(CLAUDE.md 가 스킬보다 우선, ADR-005) |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261104-01-1 | Superpowers 설치 | `.claude/settings.json` `enabledPlugins` 에 켜짐. `python nova.py doctor` 에 `✓ superpowers 설치됨 v7.0.0 · 저장소 설정 켜짐`. 새 프로젝트도 설정을 물려받음(테스트) | [superpowers.md §0](../conventions/superpowers.md) |
| REQ-261104-01-2 | 고객 인터뷰 | `/req-interview` 명령에 방식 3가지(실시간 · 질문지 · 회의록 분석). 인터뷰 기록 문서 종류 `INT-YYMMDD-NN`(`docs_new.py interview`, 인덱스 · lint 검사, 새 프로젝트에서는 비움) | §3 |
| REQ-261104-01-3 | 요구 분석 | `/req-analyze` 에 크기 판정 · 빌더 점검(세 갈래 분류) · 승인 관문. 요구 템플릿에 목적 · 목표/비목표/반목표 · 방법 · 미결 질문 | §4 |
| REQ-261104-01-4 | 나머지 기능 전부 | 15개 스킬 각각을 단계 · 명령 · 산출물 위치에 연결한 표(§2). `/task-run` · `/review-request` · `/debug` · `/finish`. 계획 템플릿 §11.1~11.3, task 템플릿 TDD 하위 단계 | §2 · §5 |
| REQ-261104-01-5 | 규칙으로 지키기 | CLAUDE.md 에 Superpowers 절. `docs/superpowers/` 금지. `.superpowers/` · `.worktrees/` 는 gitignore 에 | CLAUDE.md |

## 방법 — 고객이 정한 것 / 맡긴 것 / Claude 판단
| 항목 | 정한 사람 | 내용 |
|---|---|---|
| 인터뷰 진행 방식 3가지 | Claude 판단 | 고객이 대화에 직접 참여하지 않는 경우(대면 · 회의록)도 다루기 위해 |
| 인터뷰 ID 접두어 `INT` | Claude 판단 | 요구 ID `REQ` 와 구분 |

## 미결 질문
| 질문 | 누구 몫 | 답 |
|---|---|---|
| 첫 실제 고객 인터뷰는 언제 · 누구와 하나 | 사용자 | (다음 프로젝트에서) |

## 적용 · 결과
- 규약 [superpowers.md](../conventions/superpowers.md), 결정 [ADR-005](../adr/ADR-005-superpowers-workflow.md), 인터뷰 기록 [interviews](interviews/interview_index.md)
- 명령: `.claude/commands/` req-interview · req-analyze · task-run · review-request · debug · finish (새로 만듦) / req-new · plan-new · history-new · session-start (보강)
- 코드: `nova.py doctor`(superpowers 점검) · `scripts/docs_new.py interview` · `docs_index.py` 인터뷰 인덱스 검사 · `new_project.py`(인터뷰 기록 비움 · `.superpowers` 제외)
