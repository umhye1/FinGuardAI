# 통합신고 안내 의도와 피해 주제 분리 — #37

기준: `origin/main`의 `1f94335`에서 `fix/#37-reporting-intent`로 분기. 검증일 2026-09-29.

## 문제와 선택

`보이스피싱 통합신고 센터가 무엇인가요?`는 기존 평가에 정답 문서가 있지만
주제 탐지가 비어 `NEEDS_CLARIFICATION`을 반환했다. 검토된 통합신고 안내의 metadata는
`topics=[transfer]`, `family=integrated-reporting`이다. 단순히 신고라는 말을 transfer에
추가하면 신고 안내에도 송금 피해 지침을 강제하고 세금·분실 신고까지 잘못 연결할 수 있다.

질문의 **reporting 의도**를 기존 피해 주제와 분리했다. 검토된 원문 요약·manifest·hash는
수정하지 않는다. reporting은 검색 요청 내부의 의도이며 새로운 metadata topic이 아니다.

## 변경된 처리

- 같은 문장에 보이스피싱/금융사기와 신고/접수가 함께 있을 때 reporting 의도를 추가한다.
  NFKC·format 문자·공백 정규화를 적용한다. 단독 신고/112/통합신고센터는 범위가 불명확해
  추가 질문으로 남는다. 세금·분실 등 명시적인 다른 신고 표현도 제외한다.
- 기존 피해 주제(송금/문자·앱/소액결제)는 유지한다. 복합 질문은 reporting과 피해 주제를
  동시에 갖고 각 필수 문서계열을 요구한다.
- PostgreSQL 후보 조회는 기존 피해 topic OR 신고 문서계열 조건을 사용한다. reporting을
  transfer로 치환하거나 DB에 새로운 topic을 저장하지 않는다. 신고만 물으면 송금 문서가
  섞이지 않는다. 원래의 완료 상태·모델·내용 해시 조건 및 201건 조회 상한을 유지한다.
- 정책은 신고 의도에 `integrated-reporting`을 필수로 요구한다. 이 문서계열의 검토된
  `transfer/report_channel` claim도 요구해 다른 송금 문서의 claim으로 대체하지 않는다.
  claims의 기존 topic/value는 재작성하지 않고 충돌 검사에 사용한다.
- 같은 기관·계열 최신판, 검토기한·해시·출처·충돌 검사, 필수 인용 누락 보류,
  생성 전후 전체 후보 집합 대조와 저장 전 스냅샷 검사를 유지한다.
- 명확화 문구에 보이스피싱 신고 안내 선택지를 추가한다.

## Python ↔ Spring 정책 계약 수정

기존 Python은 v2를 반환했지만 `RagClient`와 `ChatAnswerWriter`가 v1만 허용했다.
각 서비스 테스트가 자신의 이전 버전 fixture로 통과해도 실제 ANSWERED 저장은 거부될 수 있었다.
이번에는 Python/OpenAPI/Java를 `evidence-policy-v3`로 맞추고 Java 검증 상수를 공유했다.
Python CI에도 언어 간 정책 버전·명확화 문구·문서 계약 일치 검사를 추가했다.

AI와 Spring을 **같은 릴리스로 갱신**해야 한다. 새 Spring은 v1/v2/알 수 없는 버전의 새
ANSWERED 응답을 거부한다. 이미 저장된 과거 대화의 정책 기록은 변경하지 않는다.
INSUFFICIENT_EVIDENCE는 기존처럼 서버 소유 문구로 안전하게 표시하고 지원하지 않는
policyVersion은 저장용 결과에서 제거한다. API 스키마·DB migration·기존 corpus 재등록은 없다.
이번 작업에서는 실행 중인 서비스 교체나 실사용 DB 작업을 수행하지 않았다.

## 재현과 결과

저장소 루트에서:

```sh
ai/.venv/bin/python -m pytest ai/tests -m 'not integration' -q
ai/.venv/bin/ruff check ai/src ai/tests ai/scripts
ai/.venv/bin/python ai/scripts/topic_routing_report.py --output /tmp/issue37-topic-v2.json
ai/.venv/bin/python ai/scripts/reporting_intent_report.py --output /tmp/issue37-reporting-v3.json
```

새 보고서 경로를 사용한다. reporting 보고서는 기존 파일 덮어쓰기를 거부한다.
CI는 외부 API·DB·키 없이 두 회귀 보고서를 artifact로 남긴다.

| 검증 | 결과 | 범위 |
| --- | --- | --- |
| 신규 대비 fixture 24개 | 수정 전 13/24 → 수정 후 24/24 | 의도 집합, 보류 여부, 필수 문서계열을 함께 검사 |
| 신규 테스트 최초 실행 | 19 failed / 19 passed | 수정 전 오류 재현. 이후 경계/claim 검사 3개 추가 |
| 기존 주제 fixture 28개 | 28/28 유지 | #31 송금·스미싱·소액결제 회귀 |
| AI 비통합 테스트 | 181 passed / DB 7개 제외 | 모의 생성, 누락·만료·충돌·변경, 복합 인용, 정책 계약 포함 |
| PostgreSQL repository 테스트 | 6 passed | 임시 `finguard_ai_test` DB에서 실제 pgvector·신고 계열 SQL 검사 |
| 격리 평가 스키마 정리 | 1 passed | 실패 후 임시 스키마 제거 확인. DB 통합 총 7개 통과 |
| Spring Gradle 전체 | 29 passed, skip/failure 0 | Java 21, Testcontainers PostgreSQL/Redis, v3 HTTP 수락·DB 저장 및 구버전 거부 |
| Ruff / diff 공백 검사 | 통과 | 코드·테스트 정적 검사 |

`before.json`과 `after.json`은 같은 fixture/manifest SHA-256과 기준일 2026-09-29를 사용한다.
수정 전 보고서는 main 코드를 실행해 먼저 저장했다. 최종 수정 후 별도 경로로 재실행한
보고서가 `after.json`과 동일한 것도 확인했다. 보고서의 24개와 테스트 개수는 분모가 다르다.
실제 DB 검사는 격리 컨테이너에서 실행하며 사용자 DB·공식 승인 metadata는 수정하지 않는다.

## 한계와 다음 순서

이 결과는 이미 관찰한 오류에 대해 작성한 합성 회귀이며 실사용 정확도나 독립 holdout
성능이 아니다. reporting은 문장 단위 키워드 조합으로 부정·인용·복잡한 다중 의도를
완전히 이해하지 못한다. 보이스피싱 교육과 다른 신고가 복잡하게 섞이면 추가 질문이 필요하다.
아무 사기나 모든 112 신고를 지원한다고 주장하지 않는다.

통합신고 문서는 개소 안내의 검토된 요약이다. 임의 원문 전체 최신성, 모든 대응 절차,
즉시 지급정지·환급 보장, 생성 답변의 의미적 정확도를 보장하지 않는다. 기존의 환급 보장
질문은 별도 주장 검수 과제로 남는다. 이번 검증은 유료 호출 0회이며 생성 결과는 모의 응답이다.

다음은 공개 사례 19건의 실제 사용자 검수와 정상 대화 자료 확보, 미노출 평가 질문/주장별
근거 검수다. 모델이 검수자를 대신하거나 미검수 자료를 자동 승인하지 않는다.
