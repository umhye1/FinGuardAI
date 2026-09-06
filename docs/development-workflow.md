# 모노레포와 브랜치 운영

## 폴더

- `backend/`: Spring Boot, 인증·업무 API·문서 작업·Flyway
- `ai/`: FastAPI, 분류·학습·평가·임베딩·RAG
- `infra/`: 컨테이너 실행 구성
- `contracts/`: Spring/AI 호출 계약
- `frontend/`: React + TypeScript 사용자·관리자 화면

`server`는 별도 영구 브랜치보다 `infra/` 디렉터리로 관리한다.

## 브랜치

```text
main                         검증된 릴리스
  └─ dev                     통합 기준
       ├─ codex/ai-classification-rag
       ├─ feat/frontend-analysis      (후속 예시)
       └─ feat/backend-ocr-inputs     (후속 예시)
```

Git에서 위 구조는 디렉터리 트리가 아니라 분기·통합 흐름이다. frontend/backend/ai를 영구 분리하면 API 변경이 서로 반영되지 않으므로 기능별 브랜치를 dev에서 만들고 완료 후 dev로 PR한다. 하나의 기능에 여러 폴더 변경을 함께 포함해도 된다.

이번 작업은 원격 main의 백엔드 PR #18 병합 커밋에서 로컬 main을 fast-forward하고, 같은 지점에 로컬 dev를 만든 후 AI 기능 브랜치를 분기했다. dev와 AI 브랜치는 자동 push하지 않았다. PR 생성 전 사용자가 dev와 기능 브랜치를 push해야 한다. 기능 PR의 base는 dev, 통합 검증 후 릴리스 PR의 base는 main으로 선택한다.

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

## 프론트엔드 브랜치

AI PR이 main에 병합된 뒤 로컬 main/dev를 해당 커밋으로 fast-forward하고 `codex/frontend-workspace`를 분기했다. Git 브랜치는 목록에서 나란히 표시되며 계층 폴더가 아니다. dev를 원격에 먼저 push한 뒤 프론트 PR의 base로 선택한다. main에 직접 통합하는 경우에는 base를 main으로 선택해도 된다. 실행·인증 정책·테스트는 frontend/README.md를 참고한다.
