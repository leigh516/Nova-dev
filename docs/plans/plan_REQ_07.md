# plan_REQ_07 · 공통개발플랫폼 적합성 보강 v1.0

**대상 시스템** `nova_common` · 게이트웨이 · `scripts/gen_k3s.py` · `infra/` · `.github/workflows` · `web/packages/ui` · `web/packages/sdk` · `apps/kmp/uikit` · 명령 · 규약
**변경점** 전체 분석(review_261105_02)의 P0 · P1 을 고쳐, 복제본이 운영 규모에서 안전한 기본값 · 접속기록 · 원격 CI · 폼 · 파일 · 모바일 골격을 물려받게 한다

> **한 줄 요약** — 견본 집이 한 채일 때는 괜찮던 배선을, 같은 단지에 일곱 채가 들어서도 서로 엉키지 않게 바꾼다.

| 항목 | 값 |
|---|---|
| 문서 ID | plan_REQ_07 |
| 생성 | 2026-11-05 · `docs_new.py plan` |
| 위치 | `docs/plans/plan_REQ_07.md` |
| 원천 | 전체 분석 [review_261105_02](../reviews/review_261105_02.md) |
| 연결 | 요구 [REQ-261105-05](../requirement/requirement_261105_05.md) · [tasks_REQ_07](tasks/tasks_REQ_07.md) |
| 버전 | **v1.0** · 기준 마스터플랜 v1.3 |
| 요구 | [REQ-261105-05](../requirement/requirement_261105_05.md) |
| task | [tasks/tasks_REQ_07.md](tasks/tasks_REQ_07.md) — 진행 상황의 정본 |
| 원칙 | 단계마다 관문 check · 생성물은 원천에서 · README 같은 커밋(CLAUDE.md 문서 규칙 10) |
| 실행 방식 | subagent — 단계 안에서 파일이 겹치지 않는 묶음은 병렬 |

> **진척 (2026-11-05, tasks 기준)** — 11 / 33

## 0. 영향분석 (착수 전 조회)
```
1) 대상: 위 '대상 시스템'
2) 직접 영향: 모든 서비스 기동 · 발행 · 소비 경로(1단계), 운영 매니페스트(2단계), 폼 · SDK · 모바일(3단계), 명령 · CI(4단계)
3) 간접 영향: 복제본 전부(상류 받기 upstream 으로 전달), tasks_REQ_04 와 파일이 겹치는 곳(게이트웨이 · web/ui · sdk · kmp)
4) 등급: 큼 — 공통부 기본값이 바뀐다. 단계마다 되돌릴 수 있게 작게 나눈다
5) 갱신 산출물: 생성물(gen) · 원장(registry sync) · 대장(ledgers) · README · ui.md · deploy.md · backend.md
6) 대장 조회: 새 표 없음(감사 표 p0005 는 5단계 결정 D4) · 새 API 없음 · 새 토픽 없음 · 화면은 모바일 대장 편입(F3)
7) 표준 판정: 테넌시(접속기록에 tenant) · AX(접속기록에 actor_type) · 도메인 팩 해당 없음
```

## 1. 설계의 중심축
> **핵심 인사이트** — 문제의 대부분은 '기능이 없다'가 아니라 '한 벌일 때만 맞는 기본값'이다(잠금 없음 · 이름 접두 없음 · 기본 dev · 로컬 검사만). 기본값을 운영 쪽으로 바꾸되, 로컬 개발은 설정 한 줄로 지금처럼 돌게 한다.

## 4. 표면 (화면 · API)
| 화면 | API | 표 | 권한 |
|---|---|---|---|
| 웹 폼(입력 종류 확장) · 모바일 템플릿 | 없음(새 API 없음 — 서비스 간 오류 봉투 전달만) | 없음 | 없음 |

### 4.1 UX 점검
| 원칙 | 이 화면에서 어떻게 지키나 | 남는 위험 (심각도 0~4) |
|---|---|---|
| H4 일관성 | 모바일 템플릿 이름을 웹과 같게(ListScreen ↔ ListPage — ui.md 규칙 9) | 1 |
| H5 에러 방지 | 폼 select · date 는 고를 수 있는 값만 | 0 |
| H9 에러 복구 | 서비스 간 4xx 가 사용자에게 원래 문구로 전달(B4) | 0 |

## 6. 핵심 분기
| 실패 지점 | 동작 | 이유 |
|---|---|---|
| 마이그레이션 잠금을 못 얻음 | 기다렸다가 진행(시간 초과면 기동 실패) | 두 파드 동시 DDL 방지 |
| 아웃박스 행이 다른 복제본에 잠김 | 건너뜀(SKIP LOCKED) · SQLite 는 잠금 없이 | 중복 발행 방지 |
| `NOVA_ENV` 없음(운영 매니페스트) | 기동 거부 | 설정 누락으로 개발 로그인이 켜지는 것 방지 · 로컬은 `.env` |

## 9. 범위 밖
| 안 하는 것 | 이유 · 어디서 |
|---|---|
| D1~D9 | 사용자 결정 — 5단계 표 |
| 쿠키 인증 · CSRF | tasks_REQ_04 8단계 |
| 부품 단위 테스트 틀 | 의존성 결정 — T04-9.10 · T05-9.02 |

## 10. 테스트 맵
| 단계 | 코드 경로 | 테스트 | slow | 수용 기준 |
|---|---|---|---|---|
| 0 | `scripts/gen_k3s.py` · `infra/helm` | `tests/test_infra.py` | 아니오 | S1 |
| 1 | `nova_common/service.py` · `migrate.py` · `clients.py` | `packages/common-py/tests/test_*.py` | 일부(MariaDB 잠금은 SQLite 에서 건너뜀 표시) | B1~B5 |
| 2 | `gen_k3s.py` · `Dockerfile.service` · `service.py` · `deploy.md` | `tests/test_infra.py` · 공통 테스트 | 아니오 | B6~B11 |
| 3 | `web/packages/ui` · `sdk` · `apps/kmp/uikit` · `ledgers.py` · ui.md | ui-smoke 단계 · kmp-snapshots · `tests/test_ledgers.py` | 아니오 | F1~F4 |
| 4 | `.github/workflows` · `nova.py` · `quick_check.py` · `docs_write.py` · 명령 문서 | `tests/test_quick_check.py` · `test_profile.py` | 아니오 | P1~P3 |

## 11. 후속 · 예외
### 11.1 전역 제약
| 제약 | 값 · 출처 |
|---|---|
| 언어 | 한국어(CLAUDE.md 규칙 0) |
| 순서 | tasks_REQ_04 와 파일이 겹치는 단계(게이트웨이 · web/ui · sdk · kmp)는 T04 담당이 끝난 뒤 |
| 개선 범위 | 이 작업 중 새로 보인 것은 다음 판본(plans README §5 한 세대 규칙) |

### 11.2 검토 초점
| 입력 · 상황 | 기대 동작 | 테스트를 넣은 task |
|---|---|---|
| 로컬 `python nova.py run`(설정 없음) | 지금처럼 dev 로 뜬다 | T07-2.02 |
| 복제본 2개가 동시에 기동 | 마이그레이션 한 번만 | T07-1.01 |
| 상대 서비스가 404 를 냄 | 호출한 서비스도 404 봉투로 전달 | T07-1.04 |

## 12. 체크리스트
- [ ] 0단계 · 보안 치명(Helm 네트워크 정책)
- [ ] 1단계 · 다중 복제본 안전장치 · 이벤트 루프
- [ ] 2단계 · 운영 기본값(접속기록 · NOVA_ENV · 키 주입 · TLS · 정책 · 경보 · 첫 배포 안내)
- [ ] 3단계 · 화면 공통(폼 · SDK 파일 · 모바일 템플릿 · ui.md 정합)
- [ ] 4단계 · 프로세스 · 원격 CI
- [ ] 5단계 · 갈림길 결정 받기(D1~D9)

### 12.1 실측으로 정정된 자리
- (1단계) 이벤트 루프 넘기기(T07-1.03)는 메모리 SQLite(StaticPool — 연결 하나를 나눠 씀)에서는 하지 않는다 — 요청 스레드와 동시에 쓰면 트랜잭션이 섞이는 것을 sample 간헐 실패로 실측. 메모리 DB 는 테스트 · 게이트웨이뿐이라 운영 영향 없음. 서비스 간 오류: 상대 5xx 는 502 `upstream_error`, 연결 실패 502 `upstream_unavailable`, 시간 초과 504 `upstream_timeout`(봉투에 `service`). 마이그레이션 잠금 시간 `NOVA_MIGRATE_LOCK_TIMEOUT`. 다음 판본 후보: 종료 취소 때 릴레이 조회 · close 스레드가 같은 세션을 잠깐 겹쳐 쓰는 경계

## 13. task 분해
[tasks/tasks_REQ_07.md](tasks/tasks_REQ_07.md)

---
## 변경 이력
- v1.0 · 2026-11-05 · 최초 작성(사용자 승인 2026-11-05)

> **다시 한 줄 요약** — 한 벌일 때만 맞던 기본값을 일곱 벌에 맞게 바꾸고, 되돌리기 어려운 갈림길은 사람이 고르게 남긴다.
