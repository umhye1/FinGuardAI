# [Feat] AI 문맥 분류·RAG 평가 및 이슈 기반 개발 규칙 구축

이슈: https://github.com/umhye1/FinGuardAI/issues/29
브랜치: `feat/#29-ai-performance-evaluation`

## 문제와 목표

현재 FinGuard의 규칙 점수와 이진 분류 경로는 `검찰청이나 은행을 사칭하며 본인인증을 요구하는 문자는 클릭하지 마세요` 같은 예방·인용 문구를 실제 사기 유도 문구와 충분히 구분하지 못하거나, 불확실한 입력을 모두 보류합니다. RAG도 인용 문서가 검색되었다는 사실과 생성 답변이 실제로 근거를 따르는지를 별도로 측정하지 못했습니다.

문맥 의도를 `PHISHING`, `PREVENTION`, `NORMAL`로 분리해 누수 없는 고정 평가셋을 만들고, 규칙·기존 이진 모델·3분류 후보를 같은 test에서 비교합니다. RAG는 검색 성공, 정책 라우팅, 답변 근거 충실도를 분리해 평가할 수 있게 합니다.

## 구현 범위

- `ai/data/benchmarks/context-v1/`
  - train/dev/test 고정 split 84건
  - 시나리오 group, 정규화 텍스트, 파일 해시 교차 검증
  - 예방 문구처럼 시작하지만 실제 정보를 요구하는 적대적 사례 포함
- `finguard_ai.context_model`
  - 안전한 JSON 기반 문자·단어 n-gram 3분류 후보
  - synthetic 데이터 모델은 명시적 opt-in 없이는 로드하지 않음
- `finguard_ai.context_benchmark`
  - 규칙 스냅샷·기존 이진 방식·임계값 통제군·3분류 후보 비교
  - 사기 미탐, PASS, 예방 오탐, 정상 오탐, 보류율, coverage, p50/p95 지연 측정
  - test를 보기 전에 dev에서 임계값·후보를 선택
- `ai/data/benchmarks/rag-v1/`
  - 공식 출처 요약 6건과 합성 질문 20건의 문서 ID 정답
- `finguard_ai.rag_benchmark`
  - Vector/Hybrid/Policy 선택의 Recall@k, Hit, AllRequired, MRR 비교
  - 검색 결과와 생성 답변의 faithfulness를 분리
  - 인용 원문·해시·주장 단위 수동 검수 템플릿 제공
- 저장소 운영 규칙
  - 이슈 템플릿, PR 템플릿, `feat/#번호-...`·`fix/#번호-...` 브랜치 검사 CI 추가
  - 이슈·브랜치·커밋·PR 번호 연결 규칙 문서화

## 검증 조건

- [ ] `cd ai && .venv/bin/python -m ruff check .`
- [ ] `cd ai && .venv/bin/python -m pytest -m 'not integration' -q`
- [ ] provider/API key/DB 없이 분류·RAG 오프라인 평가가 재현됨
- [ ] 데이터 split 간 group·정규화 텍스트 누수가 실행 단계에서 차단됨
- [ ] 답변 근거 충실도 미검수 상태가 `null`/pending으로 표시됨
- [ ] 운영 API가 새 후보 모델로 자동 변경되지 않음

## 측정 결과의 한계

현재 데이터는 저장소에서 직접 작성한 합성 문장이고 독립 라벨 검수가 완료되지 않았습니다. 전체 PDF가 아닌 검토된 공식 요약 6건만 사용했으며, 실제 사용자 분포·실사용 정확도·LLM 파인튜닝 성능을 의미하지 않습니다. 후속으로 사용 권한이 확인된 사례와 신규 holdout test를 확보해야 합니다.

## 관련 문서

- `docs/evidence/ai-performance-v1/README.md`
- `docs/development-workflow.md`
- `ai/data/benchmarks/context-v1/README.md`
- `ai/data/benchmarks/rag-v1/README.md`
