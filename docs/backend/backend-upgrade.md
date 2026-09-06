# 백엔드 AI 기반 확장

## 범위

기존 Spring Boot 구조를 유지한다. 이 문서의 API는 구현된 범위이며, AI 모델 학습·OCR·벡터 검색 실행은 별도 AI 서버의 후속 작업이다. 기존 작업 중이던 청크 검색 기능을 포함해 잘못된 Param import, 중복 검색, chunkId/응답 chunkCount를 보완했다.

## 인증

- 회원가입/로그인 입력을 Bean Validation으로 검증한다.
- `/api/admin/**`는 ADMIN만 접근한다. 익명 요청은 401, 일반 회원의 관리자 요청은 403이다.
- Access와 Refresh에 `type`, `sid`, `jti`를 발급한다. 기존 용도 없는 토큰은 다시 로그인해야 한다.
- Redis에는 세션별 Refresh Token SHA-256 해시만 저장한다. TTL은 Refresh 만료시간이다.
- 로그인은 새로운 세션을 만든다. 여러 기기의 세션은 독립적이다.
- Refresh는 Lua 비교·교체로 한 번만 사용할 수 있다. 재사용은 401이며 새 토큰을 반환하지 않는다.
- Access 인증에서도 세션 존재를 확인한다. 로그아웃은 같은 세션·사용자의 Access/Refresh를 확인하고 세션을 삭제한다. 해당 세션에서 발급한 모든 Access가 무효화된다.
- 회전 이전 Access는 만료 또는 로그아웃까지 유효하다. 동시 Refresh 실패 시 클라이언트는 재시도 루프를 돌리지 않는다.
- Redis 장애는 인증 우회 없이 503으로 처리한다. Redis 재시작으로 세션이 사라지면 재로그인한다.

### POST /api/auth/refresh

인증 헤더 없이 호출. 요청 `{"refreshToken":"..."}`. 성공 200, data는 기존 LoginResponse와 동일한 `accessToken`, `refreshToken`, `user`. 잘못된 요청 400, 만료·재사용·폐기 401.

## 문서 처리

### POST /api/admin/documents

기존 multipart `file`, `title`, `source`, 선택 `sourceUrl` 유지. PDF/TXT, 최대 10MB. 성공을 **201에서 202로 변경**했다. 기존 data 필드를 유지하고 `jobId`를 추가했다. 요청 완료는 텍스트 추출 완료가 아니다. `documentStatus`는 PROCESSING이다.

### POST /api/admin/documents/{documentId}/processing-jobs

관리자가 기존 문서를 재처리한다. 202, `data: {"jobId":"UUID"}`. 처리 중 중복 요청은 409, 없는 문서는 404. 실패한 문서 또는 완료된 문서를 새 작업으로 처리할 수 있다.

### GET /api/jobs/{jobId}

로그인 필요. 작업 소유자 또는 ADMIN만 조회하며 다른 사용자에게는 404.

```json
{"statusCode":200,"message":"작업 조회에 성공했습니다.","data":{"jobId":"UUID","documentId":1,"status":"RUNNING","attempts":1,"errorCode":null,"createdAt":"ISO-8601","updatedAt":"ISO-8601"}}
```

상태: PENDING → RUNNING → COMPLETED/FAILED. 만료된 RUNNING 작업은 재획득 가능하다.

- 현재 worker는 Spring 스케줄러이며 `jobs.worker.enabled`, `jobs.worker.delay-ms`로 제어한다. PDFBox/TXT 전처리를 실행한다. 향후 Python 작업자로 옮길 때도 DB 상태 계약을 유지할 수 있다.
- 작업 lease는 300초이며, 재획득마다 token이 바뀐다. 이전 작업자의 늦은 완료/실패는 반영하지 않는다.
- 프로세스 중단으로 만료된 작업은 최대 3회 실제 처리 후 RETRY_EXHAUSTED. 일반 추출/저장 실패는 FAILED로 기록하고 관리자 재처리로 복구한다.
- 청크 교체·문서 완료·작업 완료는 한 트랜잭션이다. 실패 기록은 분리된 트랜잭션이다.
- 빈 텍스트는 실패다. 스캔 PDF는 OCR을 아직 지원하지 않으므로 텍스트가 없으면 실패한다.
- 업로드 DB 롤백 시 파일 정리를 시도하고, 삭제는 DB commit 이후 파일을 정리한다. 프로세스 강제 종료/파일시스템 실패로 남은 orphan 파일은 별도 운영 정리가 필요하다.
- 처리 중 문서 삭제는 409. 완료/실패 문서를 삭제하면 관련 작업과 청크도 삭제된다.
- 청크 검색은 COMPLETED 문서만 대상으로 한다. 현 단계는 부분 문자열 검색이며 벡터 검색이 아니다.

## 분석과 AI 계약

### POST /api/analysis

`{"text":"문자 내용"}`. 1~10000자. 기존 `riskScore`, `riskLevel`, `detectedKeywordRespons` 등 필드는 호환성을 위해 유지한다. 점수는 규칙 점수이며 확률이 아니다.

추가 data 필드:

```json
{
  "modelResult": {"status":"COMPLETED","label":"PHISHING","decision":"FLAG","modelVersion":"classifier-v1","errorCode":null},
  "ruleVersion":"keyword-snapshot-v1",
  "explanationSource":"RULE_TEMPLATE"
}
```

- ruleVersion은 현재 **규칙 알고리즘 포맷 버전**이다. 키워드 DB 전체의 변경 버전은 아니다. 탐지된 키워드·점수는 기존 JSONB에 분석 당시 값으로 저장한다.
- 모델 결과는 기존 규칙 등급을 덮어쓰지 않는다.
- `modelResult.status`: COMPLETED / NOT_REQUESTED / FAILED.
- `decision`: FLAG / PASS / ABSTAIN. FLAG는 PHISHING, PASS는 NORMAL이어야 한다. ABSTAIN은 label=null을 허용한다.
- AI 비활성은 NOT_REQUESTED. 연결 실패는 AI_UNAVAILABLE, HTTP 오류는 AI_HTTP_ERROR, 스키마·모순 응답은 AI_INVALID_RESPONSE.
- AI 실패도 규칙 분석과 함께 200으로 저장한다. DB 저장 자체의 실패까지 성공으로 처리하지 않는다.
- `/api/analysis/{id}`도 같은 모델·버전 정보를 반환한다. 기존 데이터는 NOT_REQUESTED다.
- 현재 aiSummary/recommendedAction은 규칙 문구다. 모델 설명 생성이 구현되었다고 표시하지 않는다.
- 외부 호출 중 DB 트랜잭션을 유지하지 않는다. 자동 AI 재시도를 하지 않아 비용 중복을 피한다.

### POST /internal/v1/classifications (AI 서버가 구현해야 하는 계약)

헤더 `X-Service-Token`. 요청 `{"text":"마스킹된 문자"}`. 응답은 CommonResponse로 감싸지 않는 modelResult JSON이다. 모델 버전 필수, 최대 100자. Backend ai.enabled=false가 기본이다.

환경 설정: `ai.enabled`, `ai.server-url`, `ai.service-token`, `ai.timeout-ms`(기본 5000, 1~60000). enabled=true일 때 service-token 필수. AI 서버도 토큰을 검증하고 내부 네트워크 또는 TLS로 배포해야 한다.

외부 전송 전 이메일·일부 전화번호·주민번호/숫자 패턴을 마스킹한다. 이름·주소·모든 계좌번호 등을 포괄하는 완전한 PII 탐지기는 아니다. **기존 분석 원문 DB 저장은 유지**한다. 원문 저장 동의·보관 기간·암호화·완전한 비식별화는 후속 과제다. 사용자 데이터를 학습셋으로 자동 전환하지 않는다.

## RAG 채팅

기존 POST `/api/chat/sessions/{sessionId}/messages`에 실제 내부 AI 호출 경로를 연결했다. 질문은 1~10000자이며 현재 한 번의 질문만 전송한다. 대화 이력 기반 질의 재작성은 아직 없다.

### POST /internal/v1/rag/answers (AI 서버가 구현해야 하는 계약)

요청 `{"question":"마스킹된 질문"}`, X-Service-Token 헤더.

```json
{"status":"ANSWERED","answer":"근거 기반 답변","chunkIds":[1,2],"modelVersion":"model-v1","promptVersion":"prompt-v1"}
```

- ANSWERED는 1~10개 청크 ID, 답변, 모델·프롬프트 버전 필수.
- 근거 부족 응답은 `{"status":"INSUFFICIENT_EVIDENCE"}`. 임의 답변을 노출하지 않고 백엔드의 보류 문구를 사용한다.
- 백엔드는 청크가 실제 존재하고 문서가 COMPLETED인지 확인한다. 위조·삭제된 청크는 FAILED로 처리한다.
- 인용 제목·원문은 AI 응답이 아닌 DB에서 가져와 메시지에 스냅샷으로 저장한다.
- 이 검증은 인용 존재 검증이다. 답변의 의미적 일치·공식 기관 여부 자동 검증·최신 문서 버전 관리는 후속 과제다. 업로드는 신뢰된 관리자가 수행해야 한다.
- aiMessage에 `generationStatus`(ANSWERED/INSUFFICIENT_EVIDENCE/NOT_REQUESTED/FAILED), modelVersion, promptVersion을 추가했다. 기존 메시지는 null이다.
- 사용자 질문·AI 결과 저장 전에 세션 소유권과 삭제 여부를 다시 확인한다.

## 피드백·검토

### POST /api/analysis/{analysisId}/feedback

자신의 분석에만 제출. 요청:

```json
{"type":"FALSE_POSITIVE","comment":"정상 안내인데 피싱으로 나왔습니다."}
```

201. 유형 FALSE_POSITIVE/FALSE_NEGATIVE/INCORRECT_GUIDANCE/OTHER. comment 선택·최대 1000자. 분석당 사용자 피드백 1개, 중복 409, 다른 사용자 분석 404.

### GET /api/admin/reviews?status=PENDING&page=0&size=20

ADMIN만. status=PENDING/REVIEWED, page>=0, size=1~100. data는 content/page/size/totalElements. reviewId, analysisId, feedbackType, comment, status, label, reason, reviewedBy, createdAt, reviewedAt, version 반환.

### PATCH /api/admin/reviews/{reviewId}

```json
{"version":0,"label":"NORMAL","reason":"공식 예방 안내 문구로 확인했습니다."}
```

200. label=PHISHING/NORMAL/UNCERTAIN. reason 필수·1000자 이하. 목록에서 받은 version 필수. 동시 수정·오래된 버전 409. 검토를 수정하면 최신 검토자로 갱신되며 전체 수정 이력을 별도 보존하는 기능은 아직 없다.

검토 데이터의 학습셋 내보내기·동의 확인·데이터셋 버전·자동 학습·모델 배포는 이 변경에 포함하지 않는다.

## Flyway와 기존 DB

V1은 기존 엔티티 구조, V2는 문서 작업, V3 이후는 AI 결과·검토·채팅 메타데이터다. 신규 빈 PostgreSQL에서는 자동 적용한다. `ddl-auto=validate`, `baseline-on-migrate=false` 권장.

**기존 DB에는 자동 baseline을 켜지 않는다.** 실행 전:

1. DB를 백업하고 복원 가능한지 확인한다.
2. 현재 DB와 V1의 테이블·컬럼·sequence 구조를 대조한다. 차이가 있으면 먼저 조정한다.
3. 청크의 `(document_id, chunk_index)` 중복을 확인한다. V2의 unique index 전에 검토·정리해야 한다.
4. V1과 동등한 기존 DB에만 Flyway CLI 등으로 명시적으로 baseline version 1을 기록한다.
5. V2 이후 migrate 후 Hibernate validate로 확인한다.

실제 로컬 기존 DB를 변경하거나 baseline하지 않았다. 테스트는 격리된 새 PostgreSQL을 사용한다. pgvector 설치·embedding 필드·문서 버전 마이그레이션은 AI 구현 단계에서 추가한다.

## 실행·테스트

- Java 21과 Docker 필요.
- `backend/src/main/resources/application-example.properties`를 참고하여 로컬 설정을 작성한다. 기존 개인 application.properties를 덮어쓰지 않는다.
- JWT_SECRET는 적어도 32바이트의 충분히 긴 무작위 비밀키로 설정한다.
- `cd backend` 후 `./gradlew test` 실행. Testcontainers가 별도 PostgreSQL 16/Redis 7을 만들고 종료한다. 기존 서비스 DB/볼륨을 사용하지 않는다.
- AI client 테스트는 로컬 HTTP 서버로 마스킹·계약·실패를 검사한다. 실제 LLM을 호출하거나 과금하지 않는다.
- Flyway 적용·인가·Redis 회전·문서 실패/재시도·lease fencing·AI 비활성 분석 저장·검토 소유권·인용 검증을 검사한다.

## 다음 기능

1. AI 분류 서버와 데이터셋/모델 평가 구현
2. 문서 임베딩·검색·생성·의미적 인용 평가 구현
3. 이미지 입력/OCR 작업과 확인·수정 API
4. 검토 이력·학습 동의·데이터셋 내보내기
5. 목록 페이지네이션 확대·N+1 개선·문서 버전·파일 정리 작업
6. 비용·지연 관측, 서비스별 컨테이너/CI

Kafka는 도입하지 않았다. 현재 DB 작업 큐로 재시도·중복 제어를 검증한다.
