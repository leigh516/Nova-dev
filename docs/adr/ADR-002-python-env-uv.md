# ADR-002 · Python 환경 관리 도구 uv

| 항목 | 내용 |
|---|---|
| 일자 | 2026-11-03 |
| 상태 | 채택 |
| 대체 | - (ADR-001 의 Python 기준을 구체화) |
| 요구 | [REQ-261103-03](../requirement/requirement_261103_03.md) |

## 배경
dayroom2 는 `python -m venv .venv` + `pip install -e` 로 손수 관리해 PC 마다 Python 버전(로컬 3.14 · Docker 3.12)과 의존성 버전이 달랐다. 잠금 파일이 없어 재현이 어렵다.

## 결정
- 가상환경 · 의존성 · Python 버전은 **uv** 로 관리한다
- 루트 `pyproject.toml` 이 uv 워크스페이스. 멤버: `packages/common-py`(nova-common). 개발 도구는 `[dependency-groups] dev`
- `.python-version` = 3.12 (Docker 이미지와 같은 버전). uv 가 없으면 자동 내려받기
- `uv.lock` 을 커밋한다 — 모든 PC · CI · Docker 가 같은 버전
- 명령: `uv sync`(설치) · `uv run <명령>`(실행) · `uv add [--package nova-common] <pkg>`(추가). `python nova.py install` 은 `uv sync --all-packages`
- `pip install` 직접 사용 금지(잠금 파일과 어긋난다)

## 검토한 대안
| 대안 | 장점 | 단점 | 버린 이유 |
|---|---|---|---|
| venv + pip | 기본 내장 | 잠금 없음 · 느림 · Python 버전 관리 없음 | 재현성 |
| Poetry | 잠금 · 성숙 | 느림, Python 설치는 별도 | uv 가 더 빠르고 Python 버전까지 관리 |
| conda | 과학 패키지 | 무겁다, PyPI 와 이중 관리 | 범위 밖 |

## 결과
- 좋아지는 것: `uv sync` 한 번으로 같은 환경, 설치 속도
- 감수하는 것: 개발 PC 에 uv 설치 필요(`nova.py doctor` 가 점검)
- Docker 이미지도 uv 로 설치한다(4단계 Dockerfile.service)
