# Git 규칙

## 커밋 메시지 — Conventional Commits (한국어 본문)
```
<type>(<범위>): <요약 — 무엇을 했나, 50자 안팎>

<본문 — 왜, 무엇이 바뀌었나. task ID(T01-2.03) 와 REQ ID 를 적는다>
```
- type: `feat` 기능 · `fix` 버그 · `docs` 문서 · `refactor` · `test` · `chore` 설정 · `build` · `ci` · `perf`
- 범위: 서비스 · 패키지 이름(`common`, `gateway`, `web-ui`, `kmp`, `infra`, `docs`)
- 한 커밋 = 한 가지 의도. 테스트가 통과하는 상태로만 커밋
- **요약 · 본문은 한국어**(REQ-261103-05). type 접두어와 범위만 영어

## 흐름
1. 작업 → 테스트 녹색 → 커밋
2. 푸시: `git push origin <브랜치>`
3. 기록: `uv run python scripts/git_record.py "<요약>" <범위>` → `docs/git/git_YYMMDD_NN.md` + 인덱스
4. 기록 파일은 **다음 커밋에 함께** 넣는다(기록만을 위한 커밋을 따로 만들지 않아 이력이 두 배가 되지 않게). 세션 마지막에는 기록 커밋 하나를 따로 푸시해도 된다

## 브랜치
- `main` 은 항상 테스트 녹색
- 기능 단위 작업은 `feat/<계획>-<요약>` 브랜치 → PR → 병합. 혼자 하는 초기 단계는 `main` 직접 커밋 허용

## 금지
- `.env` · 비밀번호 · 토큰 커밋
- `--no-verify` 로 훅 건너뛰기, 강제 푸시(`--force`) — 사용자 확인 없이 금지
