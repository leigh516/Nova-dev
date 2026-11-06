# REQ-261106-03 · 리버스 엔지니어링 도구 REA 도입 — 대상 분석 결과를 입고 자료로

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-06 |
| 요청자 | jongyeolhan |
| 원문 | "https://github.com/morluto/rea 여기에서 rea와 관련된 모든것을 설치하고 우리 프로젝트에서 이것을 사용해서 대상 사이트나 프로그램을 분석하고 그것을 바탕으로 우리시스템 개발에 활용할수도 있도록 해주면서 관련된부분이 있으면 같이 고려해서 개선해줘" · "REA설치시 HOPPER GHIDRA IDA KUNA도 같이 사용할수있도록해야합니다" |
| 입력 자료 | 2026-11-06 세션 researcher 조사 2건(REA 정체 · 신뢰 · 법 경계 / 엔진 4종 Windows · 라이선스) |
| 크기 | 작은 변경 (superpowers.md §4) |
| 상태 | 진행 중 |
| 계획 | (이 문서 분해표로 직행) |
| 문서 ID | REQ-261106-03 |
| 생성 | 2026-11-06 · `docs_new.py req` |
| 위치 | `docs/requirement/requirement_261106_03.md` |
| 원천 | 2026-11-06 세션 사용자 원문 · 조사 결과 |
| 연결 | 입고 규약 [inbound README](../warehouse/inbound/README.md) · 관련 [REQ-261106-02](requirement_261106_02.md) |

## 의도 (INTENT — 해법을 적기 전에)
| 칸 | 내용 |
|---|---|
| 문제 | 참고할 사이트 · 프로그램이 어떻게 동작하는지(라우트 · API · 데이터 흐름 · 바이너리 구조)를 소스 없이 알아내는 도구가 없어 설계 재료를 손으로 모은다 |
| 결과 | REA 와 분석 엔진으로 대상을 분석한 결과(JSON)가 입고 자료(`docs/warehouse/inbound/`)로 들어가 `/intake` → 요구 · 설계의 재료가 된다 |
| 영향 | 이 PC 도구(`C:\Users\han\tools\` · WSL2 Ubuntu-24.04 `/opt`) · 입고 흐름 · 에이전트(design-researcher 와 보완) |
| 제약 | 저장소 안에 의존성을 넣지 않는다(저장소 밖 도구) · 전역 MCP 등록은 하지 않는다 · 판본 고정(rea-agents 6.8.0) · 자기 소유 · 권한 받은 대상만 · 분석 결과 코드를 옮기지 않는다(클린룸 — 동작을 이해하고 새로 짠다) · 결과의 비밀값 · 개인정보는 커밋 전 확인 |
| 미해결 | IDA Pro 구입 여부(상업 사용은 Free · Home 불가) · 예전 전역 등록(config_drift)을 고칠지 지울지 |

## 목적과 이유
설계 재료를 증거(파일:경로 · 엔드포인트 · 호출 흐름)로 모으면 요구 · SPEC 의 근거가 짧아진다. 관련 개선(입고 흐름 · 에이전트)은 같은 회차에 맞춘다.

## 종료 조건 (exit)
| ID | 확인 | 기대 | 방식 | 판정 |
|---|---|---|---|---|
| E1 | `rea doctor --provider ghidra --json`(Windows) | healthy | 명령 | 녹색 2026-11-06 |
| E2 | WSL `rea doctor --provider hopper --provider kuna --json` | 두 엔진 healthy | 명령 | 녹색 2026-11-06 |
| E3 | 입고 규약에 REA 결과 자리 · 허용 대상 · 비밀값 확인 규칙이 있고 docs_index 통과 | 통과 | 명령 | |
| E4 | 견본 대상(우리 저장소의 웹 빌드) 하나를 분석해 결과가 입고 자리에 들어감 | 파일 있음 | 사람 | |

## 목표 · 비목표 · 반목표
| 구분 | 내용 |
|---|---|
| 목표 | REA + Ghidra(Windows) · Hopper · Kuna(WSL) 사용 가능 · IDA 연결 자리 준비 · 입고 흐름 연결 |
| 비목표(하지 않을 것) | 유료 도구 구입 · 크랙판 · 남의 서비스 무단 분석 · 저장소에 REA 의존성 추가 |
| 반목표(돌아가도 실패인 것) | 분석 결과의 비밀값 · 개인정보가 커밋되는 것 · 디컴파일 코드를 그대로 옮기는 것 |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| 설치 범위 | 안 A(저장소 밖 CLI · 판본 고정 · 결과를 입고로) — "진행해주세요" |
| 엔진 | Hopper · Ghidra · IDA · Kuna 모두 쓸 수 있게 — Ghidra 는 Windows, Hopper · Kuna 는 WSL2 Ubuntu 24.04(설치 승인), IDA 는 사용자 구입 뒤 연결 |
| Node | hermes 가 쓰는 Node 는 그대로, 휴대용 Node 22.23.4 를 따로 |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261106-03-1 | Windows: 휴대용 Node 22.23.4(해시) · rea 6.8.0(`C:\Users\han\tools\rea`) · Ghidra 12.1.4(해시) | E1 | |
| REQ-261106-03-2 | WSL2 Ubuntu-24.04: Node 22.23.4 · rea 6.8.0(`/opt/rea`) · Kuna 1.990(공식 digest 일치) · Hopper 데모(PGP 확인) | E2 | |
| REQ-261106-03-3 | IDA 연결 자리 — 구입 뒤 `REA_IDA_MCP_CONFIG` 와 `ida-free-mcp`/IDA Pro 방식 안내 | 규약 문서 | |
| REQ-261106-03-4 | 입고 규약 · 실행 안내(명령 · 환경 변수 · 허용 대상 · 결과 자리 · 비밀값 확인) | E3 | |
| REQ-261106-03-5 | 견본 분석 1건 | E4 | |

## 방법 — 고객이 정한 것 / 맡긴 것 / Claude 판단
| 항목 | 정한 사람 | 내용 |
|---|---|---|
| Ghidra 판 12.1.4 | Claude 판단 | 12.2 는 JDK 25 필요 · rea 6.8.0 태그 문서가 12.1.x |
| Kuna 판 1.990 | Claude 판단 | 조사가 찾은 검증 판(rea doctor 문구는 1.833 — 실제 doctor 는 1.990 을 healthy 로 판정) |

## 미결 질문
| 질문 | 누구 몫 | 답 |
|---|---|---|
| IDA Pro 구입 | 사용자 | |
| 예전 전역 등록(config_drift) 처리 | 사용자 | |

## 추가 요청 (같은 날)
| 원문 | 반영 |
|---|---|

## 적용 · 결과
- 2026-11-06 Windows: Node 22.23.4(SHASUMS OK) · rea 6.8.0 · Ghidra 12.1.4(sha256 OK) — `rea doctor --provider ghidra` 전 항목 healthy
- 2026-11-06 WSL2 Ubuntu-24.04 설치 · Node 22.23.4(OK) · rea 6.8.0 · Kuna 1.990(digest 일치 · doctor healthy)
- 2026-11-06 WSL Hopper 데모 — `rea setup --install-hopper --yes`(계획 확인 뒤 · 동작은 Hopper 설치 하나 · PGP 7C2D73BA…9B1BCD) → `/opt/hopper/bin/Hopper` · doctor hopper · hopper-version · hopper-demo-runtime · kuna-installation · kuna-cache healthy
- 2026-11-06 규약 [reverse-engineering.md](../conventions/reverse-engineering.md) · 입고 `etc/rea/<대상>/` 자리(inbound/etc README) — E3 docs_index 통과
