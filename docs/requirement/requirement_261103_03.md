# REQ-261103-03 · Python 가상환경은 uv 로 관리

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-03 |
| 요청자 | jongyeolhan |
| 원문 | "가상환경은 uv를 사용하게 해주세요" |
| 상태 | 적용됨(상시 규칙) |
| 계획 | [ADR-002](../adr/ADR-002-python-env-uv.md) · [plan_REQ_01](../plans/plan_REQ_01.md) 1단계(🆕 T01-1.13) |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261103-03-1 | 가상환경 생성 · 의존성 설치를 uv 로 | `python nova.py install` = `uv sync`, 루트 `pyproject.toml` · `uv.lock` · `.python-version` 존재 | T01-1.13 |
| REQ-261103-03-2 | 모든 실행이 uv 가상환경에서 | `nova.py` 가 `.venv`(uv) 를 쓰고, 문서 명령 예시가 `uv run …` | T01-1.13 |
| REQ-261103-03-3 | 생성된 프로젝트도 uv | `new_project.py` 결과물에서 `uv sync` 후 테스트 통과 | 8단계 |

## 적용 · 결과
- 루트 `pyproject.toml`(uv 워크스페이스, dev 그룹 pytest · pyyaml), `.python-version`=3.12, `uv.lock` 커밋
- `nova.py install` → `uv sync --all-packages`, uv 없으면 설치 안내 후 종료
- 검증: `uv sync` → Python 3.12.14 가상환경, `python nova.py test` 통과
