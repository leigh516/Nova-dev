# REQ-261104-07 · 다축 심층 감사 명령 /deep-audit — psg05 를 Nova 에 맞게

| 항목 | 내용 |
|---|---|
| 요청일 | 2026-11-04 |
| 요청자 | jongyeolhan |
| 원문 | "위의 작업과 병렬로 F:\project-nuri\project-start-guide-05\.claude\commands\deep-audit.md 를 참조해서 우리시스템에 맞게 커맨드를 만들어서 다축심층검사를 할 수 있게 여러시각을 검사를 하는 커맨드를 만들어주세요" |
| 입력 자료 | psg05 `.claude/commands/deep-audit.md`(11축 · 처분 5갈래 · 입력 유효성 정본 표) |
| 크기 | 작은 변경(명령 · 도구 · 테스트) |
| 상태 | 적용됨(상시 규칙) |
| 계획 | `.claude/commands/deep-audit.md` · `scripts/audit_scope.py` |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| psg05 고유 장치(issues.mjs · proposals.mjs · 에이전트 편제 · 버스)를 옮길지 | Claude 판단 — 옮기지 않는다. Nova 에서는 ② 기록이 tasks 🆕 · REQ, ⑤ 제안이 REQ · drafts, 보고가 `docs/reviews/`, 축 에이전트가 읽기 전용 Explore + `superpowers:dispatching-parallel-agents` 다 |
| 축 수 | Claude 판단 — psg05 11축 + Nova 고유 4축(표준 · 테넌시 · AX / 한국어 규칙 / 생성물 · 단일 원천 / 운영 · 인프라) = 15축 |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| REQ-261104-07-1 | 여러 시각에서 동시에 검사하는 명령 | `/deep-audit [범위] [--only · --skip]`. 축 15개 표(Nova 기준 질문)가 있고, 읽기 전용 에이전트를 한 메시지에 동시에 띄운다. 위임 프롬프트 계약(분모 · 게이트 제외 · 세는 법 · 반환 4절 · 한국어). 축 이름은 명령 표와 도구가 같아야 한다(`test_axes_match_command_doc`) | 명령 |
| REQ-261104-07-2 | 분모 · 게이트 밖을 겨누기 | `scripts/audit_scope.py` 가 축별 대상 파일 수, 제외(생성물 · 잠금 · 캡처)와 사유, lint 단계별로 잡는 것을 낸다. lint 단계와 게이트 표가 같아야 한다(`test_gates_table_matches_lint`). 생성물 판정은 gen_k3s 생성 목록 + 머리 표시 + 알려진 경로로 한다(`test_generated_files_are_excluded_with_reason`) | 도구 |
| REQ-261104-07-3 | 처분까지 | 통합(확정 · 반증 · 이미 알려짐 · 범위 밖 · 상충) → 처분 5갈래(즉시 고침 · 기록 · 의도적 미실행 · 판정 불가 · 제안)를 Nova 기록 위치에 남긴다. 고칠 때는 회귀 테스트를 먼저 쓰고 형제를 전수로 본다. 5파일 이상이면 레일(`/req-new` → `/plan-new`)로 보낸다 | 명령 §4~§6 |
| REQ-261104-07-4 | 보고 | `docs/reviews/review_YYMMDD_NN.md` 에 분모 · 축별 결과 · 통합 판정 · 처분 · 고친 것 · 남은 것을 남긴다 | 명령 §7 |
