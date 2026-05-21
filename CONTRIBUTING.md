# 기여 가이드 (Contributing)

## 브랜치 전략 — GitHub Flow

- `main` 은 **항상 동작하는 상태**여야 합니다.
- 작업은 브랜치를 따서 시작합니다. 혼자 작업하더라도 동일.
  - `feat/<이름>` — 새 기능 (예: `feat/google-calendar-sync`)
  - `fix/<이름>` — 버그 수정 (예: `fix/wake-loop-cpu`)
  - `chore/<이름>` — 빌드/의존성/설정 (예: `chore/ruff-config`)
  - `docs/<이름>` — 문서
  - `refactor/<이름>` — 동작 변경 없는 정리
- `main` 으로의 머지는 **PR로만**. 직접 push 금지.
- 머지 방식: **Squash merge**
  - feature 브랜치의 여러 커밋이 main 에 하나로 합쳐짐
  - PR 단위 = 커밋 단위가 되어 추적이 쉬워짐
  - feature 브랜치 안에서는 자유롭게 WIP 커밋 OK (어차피 squash 됨)

## 커밋 메시지 — Conventional Commits

```
<type>(<scope>): <subject>

<body — optional>
```

### type

| type | 용도 |
|---|---|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `refactor` | 동작 변경 없는 코드 정리 |
| `docs` | 문서만 |
| `style` | 포맷팅/세미콜론/공백 등 |
| `test` | 테스트 추가/수정 |
| `chore` | 빌드/의존성/설정/잡일 |
| `ci` | CI 설정 |
| `perf` | 성능 개선 |

### scope

영향 받는 모듈명. 한 줄 안에서 한 개만:
`llm`, `speech`, `skills`, `server`, `ui`, `calendar`, `core`, `config`, `state`, `tests`, `docs`

스코프 잡기 애매하면 생략 가능: `chore: .gitignore 업데이트`

### subject

- **한국어 OK** (type/scope 는 영어 유지)
- 명령형: "추가", "수정", "삭제", "정리"
- 50자 이내, 마침표 없음
- 소문자로 시작 (타입 뒤 콜론부터)

### body (선택)

- 한 줄 띄우고 작성
- **"왜"** 위주로. "무엇" 은 코드 diff 가 말함
- 한 줄 72자 권장

### 예시

```
feat(calendar): 로컬 이벤트 저장소 + CRUD 스킬 추가

음성으로 일정 등록/조회/삭제할 수 있게 ~/.jarvis/events.json 기반 저장소를
만들었다. external_id 자리는 차후 Google Calendar 양방향 싱크를 위해 비워둠.
```

```
fix(stt): 빈 오디오 청크에서 무한 루프 방지
```

```
refactor(server): Hub 클래스를 hub/routes/ws로 분리
```

```
docs(readme): 설치 단계에 brew portaudio 안내 추가
```

## 코드 스타일

- 포맷팅 + 린트: **`ruff`** (라인 길이 100, double quotes)
- 타입 힌트 권장 — 강제는 아니지만 공개 함수/메서드에는 붙이는 게 좋음
- docstring 짧게, 한국어 OK
- 함수/변수: `lower_snake_case`, 클래스: `PascalCase`, 상수: `UPPER_SNAKE_CASE`

향후 도입 예정:
- `pre-commit` 훅으로 자동 포맷
- `pytest` 테스트 디렉토리 (`tests/`)
- GitHub Actions CI (PR 마다 lint + test)

## Pull Request

- 제목도 Conventional Commits 형식 — squash 머지 시 그대로 커밋 메시지가 됨
- 본문에 포함:
  - **변경 요약** (3~5줄)
  - **테스트 방법** (수동 확인이라도)
  - (있다면) 관련 이슈 번호: `Closes #12`
- 본인 self-review 한 번 돌리고 머지
- CI 통과 필수 (CI 도입 후)

## 의문 사항

설계 의사결정이 헷갈리면 PR 본문이나 이슈에 적어두고 진행. 나중에 봤을 때 "왜 이렇게 했지?" 사라지게.
