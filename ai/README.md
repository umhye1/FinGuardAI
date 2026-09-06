# FinGuardAI AI 서버

Spring의 기존 내부 API 계약에 맞춘 FastAPI 서비스다. 문자 분류, pgvector 검색, 근거 기반 생성, 문서 인덱싱 CLI와 학습·평가 도구를 제공한다. 모델 성능이 검증된 운영 제품을 의미하지 않는다.

## 구현 범위

- `POST /internal/v1/classifications`: 로컬 TF-IDF 문자 n-gram + 로지스틱 회귀 또는 Gemini 구조화 분류. 모델 점수는 사기 확률로 표시하지 않는다.
- `POST /internal/v1/rag/answers`: 질문 임베딩 → 정확 코사인 검색 → JSON 구조화 답변 → 검색 후보 인용 검증 → 문서 재확인.
- 두 API는 `X-Service-Token`을 상수시간 비교로 검증한다. 미설정/32자 미만 토큰으로 서버를 시작할 수 없다.
- 10000자 입력, 64KiB HTTP body 한도, 동시 요청 한도, provider 응답 2MiB 한도, 타임아웃을 적용한다. 원문과 API 키를 로그에 남기지 않는다.
- `/health/live`는 프로세스 생존, `/health/ready`는 분류기 준비·생성 설정·DB 테이블 접근을 확인한다. 외부 제공자의 실제 응답 가능성이나 모델 품질을 보증하지 않는다. 분류만 사용할 때 readiness가 503이어도 local 분류 API는 사용 가능하다.
- 모델 미준비/외부 장애/잘못된 출력은 503. 잘못된 입력은 422, 미인증은 401, 용량 초과는 413/429.
- 개인정보 마스킹은 일부 패턴만 처리한다. 완전한 비식별화가 아니며 데이터 전송 동의·이용 조건 검토를 대신하지 않는다.

## 로컬 설치

Python 3.11 이상 권장. 아래 명령은 `ai/`에서 실행한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -c requirements.lock -e '.[test]'
```

`.env.example`을 참고해 쉘/실행 환경에 값을 설정한다. 파일을 자동 로딩하지 않으며, 비밀키는 커밋하지 않는다.

```bash
export AI_SERVICE_TOKEN='백엔드와-동일한-32자-이상의-무작위-비밀키'
export AI_CLASSIFIER_PATH='.artifacts/classifier.json'
uvicorn finguard_ai.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Spring에는 `ai.enabled=true`, `ai.server-url=http://localhost:8000`, 동일한 `ai.service-token`을 설정한다. 분류 타임아웃 기본 5초, RAG는 임베딩과 생성을 포함하므로 `ai.rag-timeout-ms=15000`으로 분리했다.

## 분류기 학습·평가

JSONL 행 형식:

```json
{"id":"sample-1","group":"original-message-1","text":"분석할 문자","label":"PHISHING","source":"원문 이용 근거","sourceType":"licensed"}
```

- label: NORMAL / PHISHING.
- sourceType: licensed / consented / synthetic. 문자열 표기는 이용 권한을 자동 검증하지 않는다.
- 원문을 바꿔 만든 변형은 같은 group으로 묶는다. 학습/평가에서 group과 정규화 텍스트 해시가 겹치면 평가를 중단한다. 근접 중복까지 자동 식별하지 않으므로 분리 기준은 사람이 검토한다.
- 학습은 양쪽 라벨을 요구한다. 평가 데이터는 학습·임계값 선택에 사용하지 않는 별도 holdout으로 유지한다.
- 개인정보·학습 데이터는 `data/private/`에, 모델·평가 결과는 `.artifacts/`에 보관한다(둘 다 Git 제외).
- 모델은 JSON 가중치로 저장하며 pickle/joblib를 로드하지 않는다. JSON 가중치에도 데이터에서 파생된 n-gram이 있으므로 공개 전에 확인해야 한다.

```bash
finguard-train --data data/private/train.jsonl --output .artifacts/classifier.json --version classifier-v1
finguard-evaluate --model .artifacts/classifier.json --data data/private/holdout.jsonl --output .artifacts/evaluation-v1.json
```

기본 pass/flag 문턱은 0.25/0.75이며 실험용 초기값이다. 검증셋으로 오탐/미탐/coverage를 비교해 선택해야 한다. 중간 점수 또는 입력에 알려진 특징이 없으면 ABSTAIN한다.

평가 결과에는 다음을 분리 기록한다.

- 특징이 존재하는 표본의 0.5 기준 혼동행렬·라벨별 Precision/Recall/F1
- 특징이 없는 표본 수
- 판단 보류 수와 coverage
- PHISHING이 PASS된 수, NORMAL이 FLAG된 수
- 모델·데이터 해시·표본 수·합성 데이터 여부

### 과금 없는 동작 확인용 예제

```bash
finguard-train --data data/examples/synthetic-train.jsonl --output .artifacts/classifier.json --version demo-v1 --allow-synthetic
finguard-evaluate --model .artifacts/classifier.json --data data/examples/synthetic-eval.jsonl --output .artifacts/demo-eval.json --allow-synthetic
export AI_ALLOW_DEMO_MODEL=true
```

예제 20개 학습/8개 평가 문장은 직접 작성한 합성 fixture다. 실사용 데이터 성능으로 제시하면 안 된다. 기본 문턱에서 예제 평가 전체가 ABSTAIN할 수도 있다. 합성 모델은 `AI_ALLOW_DEMO_MODEL=true` 없이는 서비스에서 거부한다.

## Gemini 분류·RAG

```bash
export AI_GEMINI_API_KEY='실제-키'
export AI_GENERATION_MODEL='계정에서-사용-가능한-구조화출력-지원-모델-ID'
export AI_EMBEDDING_MODEL='gemini-embedding-001'
# 로컬 모델 대신 LLM 분류를 선택할 경우:
export AI_CLASSIFIER_MODE=gemini
```

모델 ID는 사용 시점의 제공자 지원 목록을 확인해 지정한다. 키와 모델을 설정한 상태에서 분류/RAG/인덱싱 요청을 실행하면 외부 API 호출과 비용이 발생한다. 이번 자동 검증에서는 실제 제공자 호출을 하지 않았다.

API 구현은 [generateContent](https://ai.google.dev/api/generate-content)의 구조화 출력과 [batchEmbedContents](https://ai.google.dev/api/embeddings)의 검색용 task/768차원 설정을 따른다. 실제 계정·모델 호출은 별도 확인이 필요하다.

## 문서 인덱싱

1. Spring Flyway V6까지 적용한다. 서버에 pgvector 확장이 설치되어 있어야 한다.
2. 관리자 문서 업로드 후 기존 작업 조회에서 COMPLETED를 확인한다.
3. 같은 DB를 가리키는 `AI_DATABASE_URL` 또는 `AI_DATABASE_HOST/PORT/NAME/USER/PASSWORD`를 설정한다.
4. 인덱싱 CLI를 실행한다. 이 단계는 **외부 임베딩 API를 호출**한다.

```bash
finguard-index --document-id 1
```

- 768차원 벡터를 기존 `document_chunks`와 분리된 `document_embeddings`에 저장한다.
- 인덱싱 완료와 문서 텍스트 추출 완료는 별개다. 현재 인덱싱은 관리자 CLI 작업이며 HTTP 자동 재시도 작업은 아니다.
- 모델별로 저장하며, 같은 문서 재인덱싱은 upsert한다. 반복 실행은 저장 중복을 만들지 않지만 임베딩 API 비용은 다시 발생할 수 있다.
- provider 호출 중 DB 트랜잭션을 열어두지 않는다. 저장 직전에 문서 잠금과 청크 스냅샷을 대조한다. 변경/삭제되었으면 전체 저장을 거부한다.
- 요청 하나에서 최대 2000개 청크를 처리하고 batch는 32개다. 작업 중단 시 CLI 재실행이 필요하다.
- 재처리로 삭제된 청크의 벡터는 FK cascade로 삭제된다. 원문 해시가 달라진 벡터와 PROCESSING/FAILED 문서는 검색에서 제외한다.
- 초기 검색은 정확 검색이다. HNSW/혼합 검색/reranker는 검색 평가와 데이터 규모가 확보된 뒤 비교한다.

RAG는 검색 후보가 없거나 모델이 근거 부족을 반환하면 INSUFFICIENT_EVIDENCE를 반환한다. 실제 검색 후보 밖의 인용 ID는 거부한다. 인용 존재와 문서 변경 검증은 구현했지만, 답변과 인용의 의미적 일치·정책 최신성까지 자동 보장하지 않는다.

## 테스트

```bash
pytest -m 'not integration'
ruff check .
```

실제 DB 검증은 오직 `/finguard_ai_test` DB 이름을 허용하며, 테스트마다 별도 스키마를 생성·삭제한다.

```bash
TEST_DATABASE_URL='postgresql://test:TEST_PASSWORD@localhost:TEST_PORT/finguard_ai_test' pytest
```

합성 학습 fixture·HTTP 모의 제공자·격리 pgvector DB로 검증한다. 테스트는 실제 사용자 데이터를 전송하지 않는다. test client 의존성의 deprecation warning은 현재 동작 실패와 별개다.

## 남은 범위

실사용 가능한 라벨 데이터 확보와 모델 평가, 실제 제공자 연동 확인, 공식 문서 수집/출처·버전 승인, RAG 품질 평가셋, 인덱싱 관리자 작업 API, OCR, 프론트엔드는 후속 작업이다. Kafka·멀티에이전트는 추가하지 않았다.
