# 관리자 문서 임베딩 상태 조회 (#41)

텍스트 추출 완료(`documents.status=COMPLETED`)만으로 선택한 모델의 벡터가 모두 저장됐다고
판단할 수 없다. 관리자 화면의 **공식 문서 → 임베딩 상태 확인**에서 모델명을 입력해 조회한다.
기본 입력값은 `text-embedding-3-small`이며 실제 AI 서버의 현재 모델 설정을 자동 감지한 값은 아니다.

## API

`GET /api/admin/documents/{documentId}/index-status?model=text-embedding-3-small`

ADMIN만 허용한다. 익명은 401, 일반 사용자는 403, 없는/삭제된 문서는 404,
0 이하 ID·모델 생략·빈 문자열·100자 초과·영숫자/점/밑줄/하이픈 이외 문자는 400이다.
응답은 기존 CommonResponse의 `data`에 아래 필드를 담는다.

```json
{
  "documentId": 1,
  "documentStatus": "COMPLETED",
  "embeddingModel": "text-embedding-3-small",
  "status": "STALE",
  "totalChunks": 3,
  "currentChunks": 1,
  "missingChunks": 1,
  "staleChunks": 1
}
```

- `totalChunks`: 실제 document_chunks 행 수. documents.chunk_count 캐시를 사용하지 않는다.
- `currentChunks`: 선택한 모델의 벡터가 있고 현재 본문 UTF-8 SHA-256과 content_hash가 일치하는 수.
- `missingChunks`: 선택한 모델의 벡터가 없는 수. 다른 모델의 벡터가 있어도 누락으로 센다.
- `staleChunks`: 선택한 모델의 벡터는 있지만 현재 본문 해시가 다른 수.
- 항상 total = current + missing + stale. 응답에는 본문·벡터·해시·로컬 파일 경로를 포함하지 않는다.

| 상태 | 조건 (위에서부터 우선 판정) |
|---|---|
| TEXT_NOT_READY | 텍스트 추출 상태가 COMPLETED가 아님 |
| NO_CHUNKS | 추출 완료지만 실제 문단 0개 |
| STALE | 내용 불일치 1개 이상 (누락도 함께 존재 가능) |
| NOT_INDEXED | 모든 문단에서 선택 모델의 벡터가 없음 |
| PARTIAL | 일부 문단만 벡터가 없음, 불일치는 없음 |
| INDEXED | 1개 이상의 모든 문단에 본문 해시가 일치하는 벡터가 있음 |

## 일관성과 비용

문서·현재 청크·선택 모델 벡터를 한 SQL의 LEFT JOIN/조건부 집계로 읽는다. 따라서 없는 문서와
문단 없는 문서를 구분하고, 원자적으로 교체되는 인덱스를 여러 쿼리 시점으로 나눠 읽지 않는다.
기존 `(chunk_id, embedding_model)` 기본키를 활용하며 새 마이그레이션은 없다.
조회 중 본문 해시를 계산하므로 문단 수·본문 길이에 비례한 비용이 있다. 목록 전체를 자동 폴링하지 않고
문서 한 개를 선택해 명시적으로 조회/새로고침한다. 이후 쓰기로 상태가 바뀔 수 있는 시점 조회다.

LLM/임베딩 공급자를 호출하거나 DB를 변경하지 않는다. 실제 인덱싱은 기존 `finguard-index` CLI 작업이다.
모델명 변경 시 이전 결과를 숨기고 새 조회를 요구한다. 조회 오류가 나면 이전 성공 결과를 표시하지 않는다.

## 해석의 한계

INDEXED는 저장된 벡터와 본문 해시의 일치만 뜻한다. 벡터 품질·공급자 모델 버전·의미 정확도·문서 공식성·
유효기간·근거 정책 통과·RAG 답변 가능 여부는 보장하지 않는다. 키워드 검색은 벡터 없는 문서에서도
가능하므로 NOT_INDEXED를 검색 불가와 동일시하지 않는다. 해시가 원래 잘못 기록된 경우까지 탐지하지 못한다.
새 AI 인덱싱 작업 API·자동 재시도·유료 재인덱싱 버튼은 포함하지 않는다.

## 검증

실제 Testcontainers PostgreSQL/pgvector에서 다른 모델의 벡터 격리, 잘못된 캐시 count,
한글/줄바꿈 본문 해시, 누락→부분→완료→본문 변경/누락 혼합, 미추출 상태를 검사한다.
동일 환경의 MockMvc로 ADMIN/USER/익명 권한, 입력 오류, 없는/삭제된 문서 응답을 확인한다.
Playwright는 모의 API로 데스크톱/모바일에서 모델 변경·누락/불일치 표시·실패 후 결과 숨김을 검사한다.
모의 UI 검증을 실제 운영 배포나 유료 임베딩 품질 검증으로 해석하지 않는다.

2026-09-30 로컬 실행: Spring 전체 31 passed(실패/skip 0), 프론트 단위 5 passed,
기존 화면 Playwright 4 passed 및 신규 진단 화면 2 passed(각 desktop/mobile), 프론트 production build 통과.
공급자 호출 0회. 임시 Testcontainers DB로 검증했으며 실제 사용자 데이터와 배포 환경은 변경하지 않았다.
