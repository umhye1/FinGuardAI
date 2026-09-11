# 실행 검증 결과

검증일: 2026-09-11. 관련 이슈: https://github.com/umhye1/FinGuardAI/issues/23

| 검증 | 결과 | 실행 환경과 범위 |
| --- | --- | --- |
| AI pytest | 52 passed | 별도 `finguard_ai_test` pgvector DB 포함. 공식 요약 등록·중복 등록·검색·충돌·최신성·인용 변경 검사 |
| Spring Gradle test | 22 passed | Java 21, Testcontainers pgvector/Redis. V7 마이그레이션과 인용 스냅샷·보류 응답 검증 |
| 프론트 Vitest | 5 passed | API 클라이언트 테스트 |
| 프론트 Playwright | 4 passed | 데스크톱/모바일에서 출처 링크·게시일·요약 표기·충돌 보류 문구 확인. API 응답은 모의 응답 |
| 프론트 빌드 | 성공 | TypeScript 및 Vite production build |
| Ruff / git diff --check | 통과 | AI 코드·테스트 정적 검사 및 공백 오류 검사 |
| 공식 manifest 검증 | 5개 통과 | 스키마·내용 SHA-256·경로·ID 중복 검증 |
| 출처 기반 검색 비교 | 8/8 기대 동작 | [상세 JSON](retrieval-evaluation.json). 로컬 TF-IDF 벡터를 사용한 검색 비교이며 실제 Gemini 성능 수치가 아님 |

실행 명령:

```sh
# 별도 테스트 DB 연결 문자열만 지정. 테스트는 finguard_ai_test DB 이름을 강제한다.
TEST_DATABASE_URL='postgresql://TEST_USER:TEST_PASSWORD@127.0.0.1:TEST_PORT/finguard_ai_test' ai/.venv/bin/pytest ai/tests -q
ai/.venv/bin/ruff check ai/src ai/tests
ai/.venv/bin/python -m finguard_ai.corpus --manifest ai/data/official/manifest.json
# backend/에서 Java 21 환경으로
./gradlew test --no-daemon
# frontend/에서
npm test -- --run
npm run build
npx playwright test
```

실제 외부 임베딩·생성 API는 호출하지 않았다. 인용 ID/내용/메타데이터의 검증과 공식 요약의 검색은 확인했지만 생성 답변의 의미적 정확도 개선을 주장하지 않는다. 최종 생성 품질을 검증하려면 실제 제공자 설정 후 별도 평가가 필요하다.

기존 로컬 `finguard` DB에는 Flyway 이력 테이블이 없어 자동으로 V7이나 corpus를 넣지 않았다. 기존 DB의 스키마 이관은 [백엔드 업그레이드 안내](../backend/backend-upgrade.md)를 따라 먼저 진행해야 한다. 이번 자료는 저장소에 준비했고, 등록·검색 동작은 기존 데이터와 분리된 DB에서 검증했다. 기존 사용자 업로드·DB 데이터는 수정하지 않았다.

테스트 경고는 FastAPI/Starlette 의존성의 deprecation, Java CDS 및 Node 색상 환경변수 경고이며 테스트 실패는 없었다.
