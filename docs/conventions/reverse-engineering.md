# 대상 분석 규약 — REA(Reverse Engineer Anything)

> 한 줄 요약: 참고할 사이트 · 프로그램의 **동작**(라우트 · API · 데이터 흐름 · 바이너리 구조)을 REA 로 분석해 결과를 입고 자료(`docs/warehouse/inbound/etc/rea/<대상>/`)로 넣고 `/intake` 로 요구 · 설계 재료로 쓴다. 요구: [REQ-261106-03](../requirement/requirement_261106_03.md)

## 1. 쓰는 범위 (먼저 읽는다)
- **자기 소유이거나 분석 권한을 받은 대상만** — 남의 서비스 · 프로그램은 약관 · 계약으로 허용될 때만. DRM · 인증 · 봇 방어 우회, 독점 코드 · 자산 복제, 무단 수집은 하지 않는다(REA `DISCLAIMER.md` 와 같다)
- **클린룸** — 분석 결과는 *동작을 이해하는 재료*다. 디컴파일 · 번들 코드를 우리 저장소에 옮기지 않는다. 우리 규약(토큰 · 부품 · 계약)으로 새로 짠다
- **결과에 비밀값 · 개인정보가 섞일 수 있다**(스크립트 내용 · 쿼리 값 · 접근성 텍스트) — 커밋 전에 사람 확인. 로그인한 화면 관찰은 개인정보보호법상 수집이 될 수 있으니 시험 계정 · 시험 데이터로
- 분석 결과는 대화 모델에게 그대로 간다(REA 는 로컬 분석이지만 결과를 읽는 것은 에이전트) — 기밀 대상은 그 점을 전제로 고른다

## 2. 이 PC 의 설치 (저장소 밖 — 저장소에는 의존성이 없다)
| 자리 | 무엇 | 판 · 확인 |
|---|---|---|
| Windows `C:\Users\han\tools\node-v22.23.4-win-x64` | 휴대용 Node(REA 요구 ≥22.23.4) — hermes 의 Node 는 건드리지 않음 | SHASUMS256 확인 |
| Windows `C:\Users\han\tools\rea` | `rea-agents` 6.8.0(판 고정 · 전역 설치 아님) | `rea --version` |
| Windows `C:\Users\han\tools\ghidra_12.1.4_PUBLIC` | Ghidra(무료 · Apache-2.0, Windows 는 실험 단계 · 읽기 전용 · PE) — JDK 21 | sha256 확인 · `rea doctor --provider ghidra` healthy |
| WSL2 `Ubuntu-24.04` `/opt/rea` · `/opt/node-v22.23.4-linux-x64` | Linux 판 REA — Hopper · Kuna 는 Windows 에서 안 됨 | |
| WSL2 `/opt/kuna/kuna-v1.990-linux-x86_64/kuna` | Kuna(무료 · Apache-2.0, ELF · Mach-O 만) | GitHub digest 일치 · doctor healthy |
| WSL2 Hopper | `rea setup --install-hopper` — 공식 데모(세션 30분 · 저장 불가), PGP 확인 | doctor |
| IDA | **사용자 구입 뒤** — 상업 사용은 IDA Pro(Free · Home 은 비상업). REA 는 설치 · 활성화하지 않는다 | 🗺 |

## 3. 실행
Windows(Git Bash) — Ghidra 와 웹 · JS 분석:
```bash
export PATH="/c/Users/han/tools/node-v22.23.4-win-x64:$PATH"
export GHIDRA_INSTALL_DIR="C:/Users/han/tools/ghidra_12.1.4_PUBLIC" JAVA_HOME="C:/Users/han/tools/jdk-21.0.13+9"
REA=/c/Users/han/tools/rea/node_modules/.bin/rea
$REA doctor --provider ghidra --json        # 점검
$REA --help                                  # 분석 명령 목록(판마다 다르다 — 여기 박지 않는다)
```
WSL — Hopper · Kuna(Linux · macOS 실행 파일):
```bash
wsl -d Ubuntu-24.04 -u root
export PATH=/opt/node-v22.23.4-linux-x64/bin:$PATH REA_KUNA_COMMAND=/opt/kuna/kuna-v1.990-linux-x86_64/kuna
/opt/rea/node_modules/.bin/rea doctor --provider hopper --provider kuna --json
```
- 결과는 `--json` 으로 받아 `docs/warehouse/inbound/etc/rea/<대상>/` 에 둔다(대상마다 폴더 · 무엇을 · 언제 · 어떤 명령으로를 `README.md` 한 장에). 같은 성격이 3건 넘게 쌓이면 전용 분류로 올린다(inbound/etc README 규칙)
- 이어서 `/intake` — 지문(sha256)이 `docs/product/intake.json` 에 남는다
- MCP 로 에이전트에 붙이는 것(전역 등록)은 하지 않는다. 필요해지면 이 프로젝트 local 범위로만(`claude mcp add --scope local`, `.mcp.json` 커밋 금지)

## 4. 다른 도구와의 몫
| 도구 | 몫 |
|---|---|
| `design-researcher` 에이전트 | 밖의 화면 **형**(구조 · 밀도 · 위계)을 우리 토큰 · 부품 이름으로 |
| REA | 대상의 **동작** — 라우트 · API 후보 · 번들 청크 · IPC · 바이너리 구조, 증거와 함께 |
| `inbound-analyst` · `mockup-analyst` | 입고된 결과를 읽어 요구 후보로 |

## 5. 되돌리기
- Windows: `C:\Users\han\tools\rea` · `ghidra_12.1.4_PUBLIC` · `node-v22.23.4-win-x64` 폴더 삭제(레지스트리 · 전역 설정 변경 없음)
- WSL: `wsl --unregister Ubuntu-24.04`(배포판 통째로 — 안의 Hopper · Kuna · REA 포함)
