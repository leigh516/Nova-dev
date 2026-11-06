# ADR-001 · 플랫폼 기준 스택과 원칙

| 항목 | 내용 |
|---|---|
| 일자 | 2026-11-03 |
| 상태 | 채택 |
| 대체 | - |
| 요구 | [REQ-261103-01](../requirement/requirement_261103_01.md) |

## 배경
Nova 는 모든 신규 프로젝트의 출발점이다. dayroom2 에서 검증된 구성(FastAPI MSA + Kafka + k3s + Prometheus/Grafana, Next.js, KMP)과 문서 프로세스를 기준으로 삼는다.

## 결정
- 백엔드: Python 3.12+(uv — ADR-002) · FastAPI · SQLAlchemy 2 · Pydantic 2. 공통 라이브러리 `nova_common`
- 서비스 간: 이벤트(Kafka, 아웃박스 · 멱등 소비 · DLQ) + 계약 API(httpx). 서비스별 DB
- 배포: 서비스 목록 단일 원천(`services.json`) → k3s · Helm · compose · Prometheus 설정 생성
- 프론트: Next.js 15 · React 19 웹, Kotlin Multiplatform 모바일, DTCG 토큰 단일 원천
- 문서: 요구 → 마스터플랜 → 세부계획 → task, 이력 · git · 세션 기록, 생성물 원장
- 모든 작업 명령은 `python nova.py <명령>`(Windows · Linux 공통)
- 이름 · 레지스트리 · 도메인은 `nova.project.json` 에서 읽는다(코드에 프로젝트 이름을 쓰지 않는다)

## 검토한 대안
| 대안 | 장점 | 단점 | 버린 이유 |
|---|---|---|---|
| Makefile 진입점 | 관례 | Windows 기본 환경에 make 없음 | 개발 PC 가 Windows |
| cookiecutter 템플릿 | 표준 도구 | 템플릿 문법이 코드에 섞여 저장소 자체를 실행 · 테스트할 수 없음 | 플랫폼 저장소가 그대로 동작하는 샘플이어야 함 |
| 서비스마다 독립 저장소 | 독립 배포 | 공통 규칙 · 생성기 적용이 어렵다 | 모노레포로 단일 원천 유지 |

## 결과
- 좋아지는 것: 새 프로젝트가 첫날부터 동작하는 골격 · 같은 규칙
- 감수하는 것: 스택이 다른 프로젝트(예: Java 백엔드)는 문서 프로세스 · 디자인 시스템만 쓰고 나머지는 ADR 로 대체
- 이후 규칙: 기준을 바꾸는 결정은 새 ADR 로
