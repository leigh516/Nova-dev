# REQ-261104-09 · 병렬 개발 · 메시지 버스 · 종료 조건(exit) · 버전 릴리스 · 마스터플랜 판본 봉인

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-04 |
| 요청자 | jongyeolhan |
| 원문 | "위의 작업과 병렬로 F:\project-nuri\project-start-guide-05\CLAUDE.md의 내용을 심층분석을 해서 이것을 바탕으로 F:\project-nuri\project-start-guide-05\ 프로젝트의 구조와 기능등을 파악해서 우리시스템에 필요한것들을 우리시스템에 맞게 구성을 해서 활용할 수 있 수엉을 해주세요   F:\project-nuri\project-start-guide-05\ 이 시스템이 너무 복잡하고 이에따라서 개발을 위한 시간이 너무 많이 소요되어서 이점을 보완하기 위해서 우리ㅣ시스템을 다시 만들고 있는 중입니다 특히 guide06에서 버전릴리스 기능이나 마스터플랜에  공통으로사용하는 플랫폼의 공통역영역이 완성되기 전까지는 worktree로 분기를 해서 병렬개발에 들어가지 않게 하는 기능이나 메시지버스기능 그리고 마스터플랜과 플랜에서 목표를 정확하게 정하고 목표가 달성되면 exit로 처리해서 나오면서 하지않는것을 정확히해서 계속 진화관리에 의해 무한히 작업을 파고들어 계속하는것을 방지하는것들을 채택해주세요 프로그램개발을 효율화하기위해 병렬처리기법으로 github와 같이 wortree를 생성하여 사용 각각 생성된 worktree 브랜치는 메시지통신으로 서로 소통을 합니다  이부분은 F:\project-nuri\project-start-guide-05\.collab를 참고해서 우리도 만들어 주세요  우리 공통개발플랫폼은 프로그램개발의 신속성과 효율성 을 중요시합" |
| 입력 자료 | psg05 `CLAUDE.md` · `.collab/` · `collab.mjs` · `parallel-gate.mjs` · `releases.mjs` · `masterplan.mjs` · `tasks.mjs` · `/worktree-new` · `/converge` · `/release` · ADR-0065 · 0066 · 0148(분석 담당 보고) |
| 크기 | 프로젝트(도구 · 명령 · 규칙 · 테스트) |
| 상태 | 적용됨(상시 규칙) |
| 계획 | [ADR-008](../adr/ADR-008-parallel-bus-release.md) · [plans README §5 · §6](../plans/README.md) |

## 의도 (INTENT — 해법을 적기 전에)
| 칸 | 내용 |
|---|---|
| 문제 | psg05 는 복잡해서 개발이 느리다. 병렬로 빨리 가고 싶지만, 공통부가 서기 전에 갈라지면 병합이 지옥이 된다. 갈라진 세션끼리 소통할 길이 없다. 목표가 흐려 작업이 끝없이 넓어진다. 판본 · 릴리스의 끝이 없다 |
| 결과 | 공통 영역 완료 뒤에만 병렬로 가고, worktree 세션끼리 버스로 소통한다. 요구 · 판본 · 릴리스가 종료 조건으로 끝나고 새 발견은 다음으로 간다. 지난 마스터플랜이 몰래 바뀌지 않는다 |
| 영향 | 계획 규칙(`docs/plans/README.md`) · 요구 템플릿 · 새 프로젝트 마스터플랜 · 기록 도구(단일 기록자) · `nova.py` 명령 · lint |
| 제약 | 신속성 · 효율성이 우선 — psg05 의 군살(상태 원장 · 관제 · 이월 사유 강제 등)은 옮기지 않는다. 태그 원격 푸시 · worktree 삭제는 사람 확인 뒤 |
| 미해결 | 없음 — 마스터플랜 v1.2 초안은 사용자 지시로 2026-11-04 채택했다(`masterplan adopt`) |

## 종료 조건 (exit)
| ID | 확인 | 기대 | 방식 | 판정 |
|---|---|---|---|---|
| E1 | uv run pytest tests/test_parallel.py -q | 통과 | 명령 | |
| E2 | uv run python scripts/masterplan.py check | 통과 | 명령 | |
| E3 | uv run python scripts/release.py check | 통과 | 명령 | |
| E4 | python nova.py lint | 통과 | 명령 | |

## 하지 않는 것
- psg05 의 버스 상태 원장 · 정체 알림 · 관제 · 데스크 회수, 병렬 게이트 F6~F10, 릴리스 트랙 · 이월 사유 강제
- 다른 PC 와 버스 공유(로컬 파일 버스만)
- Nova 자신의 마스터플랜 개정(초안만 — 채택은 사용자 결정)

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261104-09-1 | 메시지 버스 | `collab.py` send · inbox · done · outbox · show. 본 트리 하나 · 받는 이만 끝냄 · `--result` 필수 · 3홉 넘으면 escalation(`test_worktree_bus_single_writer_and_converge`) | 도구 · `/send` · `/inbox` |
| REQ-261104-09-2 | 공통 영역 완료 전 병렬 금지 | `parallel.py gate` 세 조건 · 닫힌 이유를 말한다(`test_gate_reasons`) | `/worktree-new` |
| REQ-261104-09-3 | worktree 병렬 + 소통 | `worktree-new` 가 게이트 → worktree → 버스 인계 카드. worktree 에서 번호 기록 거부(단일 기록자). `converge` 가 병합 · 검증 | `/worktree-new` · `/converge` |
| REQ-261104-09-4 | 목표 · exit · 하지 않는 것 | 요구 템플릿 · 새 프로젝트 마스터플랜에 종료 조건 · 하지 않는 것. `goals.py` 가 형식(1~7 · 방식 · 소진형 금지) · 실제 판정. 발견 세 갈래 규칙(`test_exit_rules`) | plans README §5 |
| REQ-261104-09-5 | 버전 릴리스 | `release.py` draft · ship · check. ship 은 노트(되돌리기) · 묶인 요구 완료 · 종료 조건 녹색이어야(`test_release_ship`). v0.1.0 draft | `/release` |
| REQ-261104-09-6 | 마스터플랜 판본 개선 | `masterplan.py` adopt(봉인 → 정본 → 이력) · seal · check(정본 하나 · 판본 = 이력 · 봉인 불변 · 초안 정식 불가)(`test_masterplan_adopt_seal_and_tamper`) | plans README §1 |
