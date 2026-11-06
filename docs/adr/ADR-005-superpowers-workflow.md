# ADR-005 · Superpowers 를 작업 방법론으로 채택

| 항목 | 내용 |
|---|---|
| 일자 | 2026-11-04 |
| 상태 | 채택 |
| 대체 | - |
| 요구 | [REQ-261104-01](../requirement/requirement_261104_01.md) |

## 배경
Nova 에는 기록 체계가 있다(요구 → 3층 계획 → task · 이력 · git · 세션). 하지만 **어떻게 일하는지**는 그때그때 달랐다. 고객에게 무엇을 어떻게 묻는지, 계획을 얼마나 자세히 쓰는지, 테스트를 언제 쓰는지, 검토를 누가 하는지, 완료를 무엇으로 증명하는지가 정해져 있지 않았다. 사용자는 Superpowers 플러그인(v7.0.0, 스킬 15종)을 설치해 고객 요구 분석 · 인터뷰를 포함한 기능 전부를 쓰기를 요청했다.

Superpowers 기본값 가운데 일부는 Nova 와 맞지 않는다.
- 산출물 위치: `docs/superpowers/specs` · `docs/superpowers/plans`
- 언어: 영어
- 커밋 형식: `feat: add`

## 결정
**방법은 Superpowers, 기록은 Nova.** 각 스킬을 Nova 단계와 명령에 연결하고, 산출물은 Nova 문서 위치에 한국어로 남긴다. 규약은 [superpowers.md](../conventions/superpowers.md)에 둔다.
- 설치: 저장소 `.claude/settings.json` `enabledPlugins` 로 팀 공통 설치, `new-project` 로 상속, `doctor` 로 확인
- 새 문서 종류: 고객 인터뷰 기록 `docs/requirement/interviews/interview_YYMMDD_NN.md`(INT-YYMMDD-NN, 인덱스 · lint 검사)
- 새 명령: `/req-interview` · `/req-analyze` · `/task-run` · `/review-request` · `/debug` · `/finish`
- 기존 명령 보강: `/req-new` · `/plan-new` · `/history-new` · `/session-start`
- 템플릿 보강: 요구(목적 · 목표/비목표/반목표 · 방법 · 미결 질문 · 크기), 계획(§11.1 전역 제약 · §11.2 검토 초점 · §11.3 자체 점검 · 실행 방식), task(파일 · 인터페이스 · TDD 하위 단계)
- 우선순위: CLAUDE.md 가 스킬보다 우선한다. Superpowers 가 스스로 정한 규칙이기도 하다

## 검토한 대안
| 대안 | 장점 | 단점 | 버린 이유 |
|---|---|---|---|
| Superpowers 기본값 그대로(`docs/superpowers/`) | 설정이 없다 | 정본이 둘(요구 · 계획 vs specs · plans), 영어 기록, 인덱스 · lint 밖 | 규칙 0 · 단일 정본 원칙 위반 |
| 스킬을 Nova 용으로 복사해 고쳐 쓰기(`.claude/skills`) | 완전히 맞춤 | 상위 개선을 못 받는다, 15종 유지 부담 | 연결 규약만으로 충분 |
| 쓰지 않음(Nova 명령만) | 단순 | 인터뷰 · TDD · 검토 · 디버깅 방법이 사람마다 다르다 | 요청과 어긋남 |

## 결과
- 좋아지는 것: 고객 인터뷰 방식이 하나로 정해진다(질문 하나씩, 되읽기, 추측 구분). 승인 관문이 있어 승인 전에는 구현하지 않는다. 계획에는 검토 초점이 들어가고, 구현은 TDD 로, 완료는 증거로 확인한다
- 감수하는 것:
  - 서브에이전트 실행 방식은 비용이 더 든다. 그래서 실행 방식을 사용자가 고른다
  - 플러그인 버전이 바뀌면 스킬 이름과 경로가 바뀔 수 있다. `doctor` 로 확인하고 규약 §2 를 갱신한다
- 지킬 것: `docs/superpowers/` 를 만들지 않는다. `.superpowers/` · `.worktrees/` 는 커밋하지 않는다. 스킬 본문이 영어여도 산출물은 한국어로 쓴다
