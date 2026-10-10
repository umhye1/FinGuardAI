# 증분 임베딩 오프라인 비교 — 2026-10-10 KST

이슈 #45. 실제 PostgreSQL/pgvector에 합성 100청크를 저장하고 최초 인덱싱 후 0/1/10/100개 본문을 변경했다. 같은 변경 후 snapshot에서 **증분 실행 → 강제 전체 실행** 순서로 각각 1회 비교했다. provider는 본문 SHA-256으로 위치를 고른 768차원 단위 벡터를 반환하며 외부 HTTP/생성/임베딩 API를 호출하지 않는다.

## 관찰 결과

| 변경 비율 | 증분 입력 수 | 전체 입력 수 | 증분 batch 호출 | 전체 batch 호출 | 증분 입력 문자 | 전체 입력 문자 | 벡터·검색 동일 |
|---|---:|---:|---:|---:|---:|---:|---|
| 0% | 0 | 100 | 0 | 4 | 0 | 790 | 통과 |
| 1% | 1 | 100 | 1 | 4 | 10 | 793 | 통과 |
| 10% | 10 | 100 | 1 | 4 | 100 | 820 | 통과 |
| 100% | 100 | 100 | 4 | 4 | 1090 | 1090 | 통과 |

문자 수는 마스킹 전 Python 문자열 길이이며 토큰 수가 아니다. 입력 수와 provider 인터페이스 batch 호출 수는 다르다. 예를 들어 10% 변경에서 처리 입력은 100→10개지만 batch 호출은 4→1회였다. 실제 청구액·토큰·공급자 지연·검색 품질 개선으로 환산하지 않는다.

저장된 벡터/본문 해시와 기존 exact cosine 검색의 전체 100개 결과를 비교해 같음을 확인했다. 동일 벡터 upsert가 updated_at을 변경하지 않는 것도 검증했다. 합성 벡터라 정확히 같은 결과를 기대할 수 있으며 실제 모델의 의미적 검색 품질을 평가한 것이 아니다.

경과시간도 원시 JSON에 남겼지만 시나리오별 표본 1개, 실행 순서 고정, 캐시 초기화 없음, 최종 측정 중 Spring 테스트 병행이므로 대표 속도 개선율이나 지연 분포로 사용하지 않는다.

원시 결과: [0%](change-0.json), [1%](change-1.json), [10%](change-10.json), [100%](change-100.json).
환경·이미지·소스/결과 해시: [environment.json](environment.json). 테스트 실행 당시 구현은 `4b4005e`, 최종 테스트 소스는 `49018b3`에 기록했다.

## 정확성·실패 검증

- 초기 V9 캐시는 비어 있고 기존 활성 벡터를 출처 불명 캐시로 역수입하지 않음.
- 무변경·청크 ID 재생성·메타데이터만 변경은 벡터 재사용. 문서 ID/모델/provider/revision/처리 버전별 격리.
- 65개 입력의 두 번째 batch에서 합성 실패: 활성 인덱스 unchanged, 최초 32개 cache commit 유지. 재실행 시 32개 재사용 + 33개 새 입력/2 batch.
- 최종 공개 실패 후 캐시만 남아도 활성 인덱스 보존, 재실행 provider 호출 0회.
- provider 응답 개수/차원/NaN/영벡터 오류는 캐시·활성 인덱스 쓰기 전에 거부.
- 호출 도중 본문/메타데이터/상태 변경 또는 문서 삭제 시 StaleDocument. 캐시만 사용한 zero-call 실행도 최종 메타데이터 변경을 다시 확인.
- 삭제된 청크는 검색에서 제외. 문서 삭제 시 캐시 FK cascade 삭제.
- metadata claim을 충돌하게 변경한 뒤 벡터를 0회 호출로 재사용해도 현재 근거 정책은 CONFLICTING_EVIDENCE로 판단.
- `--dry-run`은 provider를 생성하지 않고 캐시/활성 테이블을 쓰지 않음.

## 실행 결과와 재현

- AI ruff: 통과.
- AI offline: **197 passed**, integration 22개 제외.
- 실제 pgvector integration: **22 passed**, offline 197개 제외.
- Spring Java 21/Testcontainers: **31 passed**, skip 0. 처음에는 migration 기대값 8에 대해 실제값 9가 나와 1개 실패했다. V9 및 빈 신규 캐시 검증으로 갱신 후 전체 통과했다.
- 배포 스크립트 회귀: **3 passed**.
- Python에서 기존 Starlette/httpx 및 anyio deprecated API 경고 2개가 남는다. 이번 변경의 실패는 아니며 의존성 교체는 별도 범위다.

```bash
# 저장소 루트, 테스트 의존성 설치 후
ai/.venv/bin/ruff check ai
ai/.venv/bin/pytest -q ai/tests -m 'not integration'

# 테스트 전용 PostgreSQL/pgvector DB와 자격증명을 별도로 준비한다.
# TEST_DATABASE_URL의 DB명은 반드시 finguard_ai_test이어야 한다.
# 기존 사용자/운영 DB를 지정하지 않는다. 테스트마다 임시 schema 생성/삭제.
export TEST_DATABASE_URL='postgresql://TEST_USER:TEST_PASSWORD@127.0.0.1:TEST_PORT/finguard_ai_test'
INCREMENTAL_REPORT_DIR=ai/.artifacts/incremental-45 \
  ai/.venv/bin/pytest -q ai/tests -m integration
```

CI의 `AI offline evaluation / integration`도 pgvector 서비스에 마이그레이션을 적용한 뒤 동일 통합 테스트를 실행하고 원시 비교 결과를 artifact로 보존한다. CI 속도는 이 로컬 실행과 비교하지 않는다. 외부 API 자격증명 없이 실행한다.

구현·실행에는 Codex의 도움을 받았다. 사용자는 [운영 안내](../../ai/incremental-embedding.md)의 dry-run과 테스트를 직접 재현하고 처리 범위·한계를 확인할 수 있다.
