# 증분 임베딩과 배치 재개 (#45)

기존 `finguard-index`는 문서 전체를 매번 임베딩했다. 이제 기본 실행은 문서별 캐시에서 같은 본문·임베딩 프로필의 벡터를 재사용하고 누락된 입력만 최대 32개씩 생성한다. **실제 실행의 캐시 누락은 유료 provider 호출**이다. 이번 검증에는 결정적 모의 공급자만 사용했다.

## 실행과 계획 확인

1. Spring을 먼저 업데이트해 Flyway **V9**를 적용한다. 기존 V1~V8 파일을 수정하거나 운영 DB를 테스트에 사용하지 않는다.
2. AI 코드/이미지도 업데이트한다. 같은 DB를 가리키는 기존 `AI_DATABASE_*`, 공급자/모델 설정을 사용한다.
3. 관리자 문서 상태가 COMPLETED인지 확인하고 읽기 전용 계획을 조회한다.

```bash
# Compose 예시. 계획은 DB 읽기만 수행하며 provider 객체도 생성하지 않는다.
docker compose --env-file infra/.env -f infra/compose.yml exec ai \
  finguard-index --document-id 1 --dry-run

# 실제 실행: 계획에 남은 입력이 있으면 비용 발생
# 운영자가 비용과 실행 대상을 확인한 뒤 사용한다.
docker compose --env-file infra/.env -f infra/compose.yml exec ai \
  finguard-index --document-id 1

# 비교/재생성: 캐시를 우회해 모든 청크를 다시 호출하므로 주의
finguard-index --env-file ai/.env --document-id 1 --full --dry-run
```

명령의 `--env-file`은 해당 AI 프로세스에서 읽을 경로다. 위 독립 CLI 예시는 저장소 루트의 로컬 실행이며, 컨테이너에는 호스트의 env 파일이 자동 마운트되지 않는다. Compose의 env-file 옵션과 AI CLI의 env-file 옵션을 구분한다.

성공 결과의 `chunkCount`/`embeddingModel`은 유지하며 다음 필드를 추가했다.

| 필드 | 의미 |
|---|---|
| profile / profileHash | 재사용 조건 전체와 식별 해시 |
| cachedChunks | 이번 시작 시 캐시에서 재사용 가능한 현재 청크 수 |
| deduplicatedChunks | 캐시 누락 중 동일 본문을 한 번만 호출해 절약한 중복 수 |
| plannedEmbeddingInputs / plannedProviderCalls | 계획 입력 수 / 32개 batch 기준 호출 수 |
| plannedInputCharacters | 마스킹 전 Python 문자열 문자 수. 토큰이 아님 |
| embeddedInputs / providerCalls / inputCharacters | 완료된 실행의 공급자 인터페이스 입력/호출/문자 수 |
| inputTokens / cost | 현재 null. 공급자 usage·실제 청구액을 계측하지 않음 |
| published | 전체 활성 인덱스 공개 성공 여부. dry-run은 false |
| elapsedSeconds | 계획 또는 실행 함수 전체 경과시간 |

증분 성공 시 `cachedChunks + deduplicatedChunks + embeddedInputs == chunkCount`다.
`--full`은 중복 본문도 포함해 모든 청크를 호출한다. `--dry-run`은 실행 수치가 0이며 DB를 변경하지 않는다.
계획 후 문서나 다른 작업의 캐시가 변경될 수 있으므로 계획이 향후 실행 비용을 예약하거나 보장하지는 않는다.
실패 시 CLI는 nonzero로 종료한다. 성공 JSON을 만들지 않으며 실패/재시도를 합친 실제 HTTP 호출·비용 계측은 후속 과제다.

## 재사용 조건과 기존 데이터

캐시 키는 `(document_id, profile_hash, content_hash)`다. content_hash는 **저장된 청크 본문의 UTF-8 SHA-256**이며 원문을 추가 저장하지 않는다. 기존 Spring은 공백 정규화 후 800자 청크를 만든다. 이 인덱서는 청크를 재분할/정규화하지 않는다. 공급자 어댑터의 기존 마스킹과 정규화는 그대로 적용한다.

프로필에는 provider, model, revision, processing_version, dimensions(768), task(RETRIEVAL_DOCUMENT), implementation(mask-v1-l2norm-v1)이 포함된다.

```dotenv
AI_EMBEDDING_REVISION=unversioned
AI_EMBEDDING_PROCESSING_VERSION=chunker-v1-raw-utf8
```

- 모델/공급자 변경은 설정에서 자동으로 다른 프로필을 만든다. 같은 모델명의 공급자 내부 교체는 자동 감지하지 못하므로 필요 시 revision을 명시적으로 바꾼다.
- 청커/본문 전처리 정책 변경 시 processing version을 올린다. `raw-utf8`은 인덱서가 저장된 청크를 추가 변형 없이 해시한다는 뜻이다. 마스킹/벡터 처리 구현 변경 시 implementation 버전도 올려야 한다.
- 문서 ID를 유지한 재처리에서 청크 ID가 모두 바뀌어도 같은 본문은 재사용한다. 다른 문서 ID 사이에는 캐시를 공유하지 않는다.
- **기존 document_embeddings는 캐시로 자동 역수입하지 않는다.** provider/revision 출처가 없어 잘못된 재사용을 피하기 위해 V9 도입 후 최초 실행에서는 다시 생성한다. dry-run으로 먼저 확인한다.
- 내용이 같은 메타데이터 변경은 다시 임베딩하지 않는다. 최신 메타데이터를 snapshot에 포함해 공개 직전에 재확인하고, 검색의 기존 근거 정책은 현재 문서 메타데이터로 평가한다.
- 동일한 활성 벡터/본문은 upsert의 조건절로 UPDATE를 생략해 updated_at을 불필요하게 바꾸지 않는다.

## 실패·동시 변경·공개 경계

```text
현재 청크 snapshot → 문서/프로필별 캐시 조회 → 변경·누락 입력 계획
→ provider batch → 응답 개수/768차원/유한값/비영벡터 검증
→ 문서 잠금 + snapshot 대조 → batch 캐시 commit (검색에 노출 안 됨)
→ 다음 batch
→ 문서 잠금 + 전체 본문/ID/제목/메타데이터/상태 대조
→ 활성 document_embeddings 전체 upsert → 한 transaction commit
```

provider 호출 중 DB transaction/문서 잠금을 유지하지 않는다. 기존 Spring 재처리·삭제와 같은 부모 문서 잠금으로 짧은 DB 작업을 직렬화한다. 직접 SQL로 청크를 수정하는 외부 작성자도 이 잠금 규칙을 따라야 한다.

65개 입력 중 첫 32개 성공 후 두 번째 batch가 실패하면 활성 인덱스는 부분 갱신하지 않는다. 같은 프로필로 재실행하면 성공한 32개 캐시를 재사용해 나머지 33개만 요청한다. `--full`로 재시도하면 캐시를 무시하므로 이 이점이 사라진다. 최종 공개가 실패해도 검증 후 저장한 캐시는 재실행에 사용할 수 있다.

단, 이것은 **자동 작업 큐·자동 retry·exactly-once 과금 보장**이 아니다. 응답 수신 후 DB 캐시 저장 전 프로세스가 죽으면 다음 실행에서 재호출할 수 있다. 같은 문서를 동시에 인덱싱하면 중복 provider 호출이 가능하다. CLI를 같은 문서에 동시에 실행하지 않는다.

문서 본문/상태/메타데이터가 도중에 바뀌면 StaleDocument로 중단한다. 문서 변경을 끝낸 후 dry-run부터 다시 확인한다. 잘못된 캐시 벡터는 조용히 통과하지 않고 실패하며, 프로필을 올리거나 명시적인 `--full` 실행으로 재생성할 수 있다.

## 보존과 검색의 한계

- 캐시는 활성 검색 테이블과 분리돼 삭제된 청크의 캐시 벡터가 직접 검색되지 않는다. 문서 삭제는 FK cascade로 캐시도 삭제한다.
- 같은 문서의 이전 본문/프로필 캐시는 재개·재사용을 위해 남는다. TTL/용량 제한/GC는 이번 범위 밖이므로 반복 갱신 시 저장량이 증가한다. 문서당 실행 상한은 기존처럼 2,000청크다.
- 기존 Spring 재처리는 PROCESSING 상태로 바꾸고 완료 시 옛 청크/활성 벡터를 삭제한다. 따라서 **문서 재처리 전체의 무중단 이전 버전 제공은 보장하지 않는다.** 이 변경은 인덱싱 도중의 부분 공개를 막는 범위다.
- 캐시 프로필은 재사용을 위한 키다. 기존 검색/관리자 진단은 모델명·본문 해시 기준이며 revision/processing version별 검색 전환 상태를 보여주는 API는 추가하지 않았다. 같은 모델명의 revision 전환 중에는 직전 성공 인덱스를 조회할 수 있다.
- 관리자 [임베딩 진단](../backend/document-index-status.md)은 실제 활성 벡터를 기준으로 한다. 캐시가 있다는 이유만으로 INDEXED가 되지 않으며 성공 후 새로고침한다. 유료 실행 버튼·작업 큐·사용량 대시보드는 별도 후속이다.

[오프라인 비교 결과](../evidence/incremental-embedding-v1/README.md)에서 검증 범위와 실측을 확인한다.
