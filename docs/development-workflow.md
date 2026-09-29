# 모노레포와 브랜치 운영

## 폴더

- `backend/`: Spring Boot, 인증·업무 API·문서 작업·Flyway
- `ai/`: FastAPI, 분류·학습·평가·임베딩·RAG
- `infra/`: 컨테이너 실행 구성
- `contracts/`: Spring/AI 호출 계약
- `frontend/`: React + TypeScript 사용자·관리자 화면

`server`는 별도 영구 브랜치보다 `infra/` 디렉터리로 관리한다.

## 브랜치와 이슈·PR 규칙

1. GitHub 이슈를 먼저 생성한다. 제목은 `[Feat] 작업명` 또는 `[Fix] 수정명`으로 쓴다.
   문제·목표, 구현 범위, 완료 조건을 본문에 작성한다.
2. 실제 생성된 이슈 번호로 `feat/#번호-짧은-설명` 또는 `fix/#번호-짧은-설명`을 만든다.
   설명 없는 `feat/#번호`, `fix/#번호`도 허용한다. `codex/`, `feature/`, `bugfix/`는 사용하지 않는다.
3. 기능 단위로 커밋한다. `feat(ai): 문맥 분류 평가 추가 (#29)`처럼 영문 타입/scope,
   한글 설명, 마지막 이슈 번호를 사용한다. fix/docs/test/refactor/chore/ci 등 커밋 타입은
   허용하지만 **작업 브랜치 접두사는 feat/fix 두 종류**다. 문서·CI 개선은 feat에 포함한다.
4. 적절한 테스트와 diff 확인을 마친 뒤 push한다.
5. PR 제목은 `[#29] AI 문맥 분류 및 RAG 평가 체계 구축` 형식으로 쓴다.
   본문은 `.github/PULL_REQUEST_TEMPLATE.md`의 개요·변경 사항·검증·관련 이슈·리뷰 메모를
   채우고, 관련 이슈에 동일 번호의 `close #29`를 단독 줄로 작성한다.
6. 자동 merge하지 않고 리뷰 후 사용자가 병합한다. 과거 완료 이슈 번호를 새 작업에 재사용하지 않는다.

현재 원격 통합 브랜치는 main이다. dev를 실제 운영하기 전까지 최신 origin/main에서 분기하고
main으로 PR한다. dev를 도입하면 기능 PR의 base를 dev로 통일하고 dev → main 릴리스만
`[Release] 설명` 제목의 예외를 허용한다. 디렉터리별 frontend/backend/ai 영구 브랜치는 두지 않는다.

```bash
git fetch origin
git switch -c 'feat/#29-ai-performance-evaluation' origin/main
# 기능별 구현·검증·커밋
git push -u origin 'feat/#29-ai-performance-evaluation'
```

번호는 예시이며 새 작업은 먼저 이슈를 발급받는다. `#`이 있는 브랜치명은 항상 따옴표로 감싼다.
브랜치 변경 전 `git status`, `git branch -vv`, 원격 PR과 stash를 확인해 사용자의 변경을 보존한다.

`Branch convention / validate`는 PR 브랜치 형식, 제목·close 번호 일치, 템플릿 항목,
실제 이슈 존재와 Feat/Fix 제목을 검사한다. PR 제목/본문 수정에도 재실행한다.
Actions는 잘못된 브랜치의 **push 자체를 막지 못한다**. 실패한 PR의 병합을 강제 차단하려면
GitHub main/dev ruleset에서 이 검사를 required status check로 설정해야 한다.
이 저장소 변경만으로 서버 ruleset이 설정됐다고 간주하지 않는다.

## 새 로컬 통합 환경

`infra/compose.yml`은 **새 `finguard-dev` Compose 프로젝트와 별도 볼륨**을 사용한다. 기존 `backend/docker-compose.yml`의 DB를 자동 이동하거나 기존 DB 볼륨을 재사용하지 않는다.

1. `infra/.env.example`을 참고해 `infra/.env`에 독립적인 DB 비밀번호·JWT 키·32자 이상 서비스 토큰을 설정한다.
2. 로컬 모델을 사용하면 `ai/.artifacts/classifier.json`을 준비한다. 합성 예제 모델은 `AI_ALLOW_DEMO_MODEL=true`로 명시적으로 허용한다. 실제 데이터 학습·평가는 ai/README.md를 따른다.
3. 저장소 루트에서 실행한다.

```bash
docker compose --env-file infra/.env -f infra/compose.yml up --build -d
```

- frontend: localhost:3000 (변경 가능)
- backend: localhost:8080 (변경 가능)
- postgres: localhost:55432 (기존 5432 충돌 회피)
- AI와 Redis는 Compose 내부 네트워크에서만 접근
- 백엔드가 Flyway를 적용한다. DB가 준비되어도 AI 모델·스키마가 준비되지 않은 짧은 구간에는 AI 호출 실패가 부분 결과로 표시될 수 있다.
- 모델·Gemini 키·공식 문서 인덱스가 없으면 AI/RAG가 준비되지 않은 상태가 정상이다. 설정만으로 모델 품질이 확보되는 것은 아니다.
- 모델 파일 교체 후 AI 프로세스를 재시작한다. 모델은 startup 시 한 번 로드한다.

관리자가 Spring API로 문서를 업로드해 텍스트 추출이 완료된 뒤 실행:

```bash
docker compose --env-file infra/.env -f infra/compose.yml exec ai finguard-index --document-id 1
```

이 인덱싱은 외부 임베딩 API 비용이 발생한다. Gemini 키가 필요하다. 작업 완료 후 같은 내부 API로 RAG 질문을 처리한다.

중단 시 `docker compose --env-file infra/.env -f infra/compose.yml down`을 사용한다. `-v`는 DB·파일 볼륨을 삭제하므로 정상 종료에 사용하지 않는다.

## 기존 환경 유지

기존 DB에 적용할 때는 docs/backend/backend-upgrade.md의 baseline 절차를 먼저 확인한다. V6부터 PostgreSQL 서버의 pgvector 확장과 확장 생성 권한이 추가로 필요하다. 기존 로컬 application.properties와 사용자 DB는 이번 작업에서 변경하지 않았다.

## 프론트엔드 작업에도 같은 규칙 적용

프론트엔드·백엔드·AI 모두 이슈 번호 기반 기능 브랜치를 사용한다. Git 브랜치 목록은
디렉터리 트리가 아니며 브랜치명의 suffix로 작업 영역을 구분한다. 현재 PR base는 main으로
통일한다. 실행·인증 정책·테스트는 `frontend/README.md`를 참고한다.
