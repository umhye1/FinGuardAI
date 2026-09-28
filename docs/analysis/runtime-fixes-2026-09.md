# 문자 분석과 AI 실행 점검 — 2026-09-28

## 확인한 원인

- 실행 중 Spring 설정에 ai.enabled가 없어 기본 false였음.
- AI 8000 포트 미실행, ai/.env의 OpenAI 키 공란.
- ai/.env DB 자격증명이 현재 Spring DB와 불일치.
- DB 활성 키워드는 검찰청/계좌번호/본인인증/링크/주민등록번호 5개, 벡터 0개.
- 문자열 contains만 사용하여 띄어쓰기·제로폭 문자에 취약.
- 프론트 위험도 목록과 백엔드 8단계 enum 불일치.

## 변경

V8은 없는 키워드만 추가한다. 기존 점수·비활성 설정은 덮어쓰지 않는다.
점수는 프로젝트 휴리스틱이며 공식 기관이 정한 위험 점수가 아니다.
원격제어/앱설치/택배/배송조회/교통법규위반/특별경품/저금리대출/계좌이체 등을 보강했다.
보증료는 사용자 테스트에서 추가한 후보이고 정상 대출에도 쓰인다.
NFKC·공백·제로폭 문자·대소문자 정규화, 점수 100 상한을 적용했다.
예방 문장도 단어는 탐지된다. 단어 점수와 LLM 문맥 분류를 별도 표시하며,
예방 문구가 있다는 이유만으로 무조건 정상 처리하는 우회 규칙은 추가하지 않았다.

공식 자료 확인:
- KISA, 2026-09-17: https://www.krcert.or.kr/kr/bbs/view.do?bbsId=B0000133&categoryCode=&menuNo=205020&nttId=72191&pageIndex=1&searchCnd=&searchWrd=
- 관계기관 합동, 2025-01-20: https://www.fsc.go.kr/no010101/83889
- FSC 정부지원 대출 사칭 안내(2023): https://fsc.go.kr/no040101?cnId=1566&curPage=253&pastPage=253&srchKey=&srchText=
- FSC 저금리 대환 안내/사칭 주의(2023): https://www.fsc.go.kr/no040101?cnId=1610&curPage=1

최신 KISA 공지의 스미싱 부분만 별도 manifest-2026-09.json에 요약했다.
원문 전체가 아니며 실제 상담·법률 판단의 정확성을 보증하지 않는다.
기존 평가용 5개 manifest는 재현성을 위해 변경하지 않았다.

## 실행 (저장소 루트)

1. ai/.env의 AI_OPENAI_API_KEY에 실제 키를 넣는다. AI_PROVIDER=openai,
   AI_CLASSIFIER_MODE=openai를 사용한다. DB와 서비스 토큰도 동일 환경으로 맞춘다.
2. AI 실행:

```sh
ai/.venv/bin/python -m finguard_ai.serve --env-file ai/.env
```

키 없이 연결 상태만 진단하려면 --allow-unconfigured를 명시한다. 정상 AI 결과로 대체하지 않는다.
`/health/live`는 프로세스 생존만 의미한다. `/health/ready`가 UP이어도 키의 유효성이나 RAG 품질을 보증하지 않는다.
3. 기존 8080 Spring을 중지한 다음 Java 21 환경에서:

```sh
ai/.venv/bin/python scripts/run_backend_with_ai.py
```

이 실행기는 ai/.env 서비스 토큰만 백엔드 환경변수로 전달한다. AI 키는 전달하지 않는다.
프론트는 기존 Vite 5173에서 8080으로 연결한다.

4. 공식 요약 등록 (외부 API 호출 없음, 중복 import 가능):

```sh
ai/.venv/bin/python -m finguard_ai.corpus --env-file ai/.env --manifest ai/data/official/manifest.json --apply
ai/.venv/bin/python -m finguard_ai.corpus --env-file ai/.env --manifest ai/data/official/manifest-2026-09.json --apply
```

5. 출력된 공식 지침 documentIds만 인덱싱 (유료 임베딩 호출):

```sh
ai/.venv/bin/python -m finguard_ai.indexing --env-file ai/.env --document-id 14
```

14는 이번 로컬 DB의 최신 KISA 요약 ID이며 다른 환경에서는 실제 출력 ID를 사용한다.
기존 개인 업로드 문서를 일괄 인덱싱하지 않는다. 키 설정 후 AI 서버를 재시작한다.

## 추천 후속 기능

우선순위는 실제 장애와 업무 요구를 기준으로 정한다.
1. 관리자 AI 상태 화면과 요청 단위 추적: 비활성/키 오류/호출 한도/DB 오류 구분.
2. 문서 임베딩 비동기 작업: 현재 CLI를 기존 작업 큐에 연결하고 버전·중복·재처리 제어.
3. 평가셋과 CI 회귀: 예방문자 오탐, 실제 요구문자 누락, 근거 충돌, 답변 보류, 비용·지연 측정.
4. 제한된 도구 사용 상담 Agent: 사건 정보 확인→공식 자료 검색→검토 요청. 실제 신고/송금은 실행하지 않음.

자소서 폴더의 NH투자증권 2026-09-26 분석은 시스템 개발·운영, SQL, 보안과 업무 연결을 강조한다.
이를 특정 프레임워크가 채용 필수라는 주장으로 확대하지 않는다. 멀티에이전트/파인튜닝은
단일 에이전트 및 프롬프트 기준선의 실패를 측정한 뒤 도입한다.

## 이번 실행 결과

실제 로컬 DB에 V8 적용: 기존 5개 보존, 신규 9개 추가(총 14개).
최신 KISA 요약 documentId=14 등록. 실제 Spring(8080)→FastAPI(8000) 경로 확인.
테스트 계정 하나와 분석 5건·Q&A 검증 대화를 생성했으며 계정 토큰은 저장하지 않았다.
사용자 예제 순서대로 규칙 점수 60/45/40/0/40.
마지막 예방 안내문도 단어가 포함되어 40점: 규칙의 문맥 한계가 해결됐다는 의미가 아니다.
API 키가 비어 있어 모델 결과는 FAILED / GENERATION_NOT_CONFIGURED,
문서 Q&A는 FAILED. 실제 LLM 분류·답변 품질 또는 임베딩 성공은 확인하지 못했다.
AI는 --allow-unconfigured로 진단 상태에서 실행 중이며, 키를 설정한 뒤 재시작해야 한다.
명시한 dotenv 파일의 키만 사용하도록 런처를 수정해 상위 셸의 다른 키 혼입을 방지했다.

## 충전 후 최소 실제 호출 확인 (2026-09-28)

사용자 요청에 따라 유료 API 호출 총 4회로 제한해 검증했다.
- 임베딩 1회: 공식 요약 5건, 총 945자; 문서 9/10/11/12/14 벡터 저장.
- 분류 1회: 예방 안내 문자 → COMPLETED / ABSTAIN, 약 2.4초.
  규칙 점수는 40점이며, AI가 NORMAL로 분류한 것은 아니다.
- 질문 임베딩 1회 + 답변 생성 1회: ANSWERED, 약 4.31초.
  실제 Spring→FastAPI→OpenAI→DB 경로에서 최신 KISA 문서 14/청크 9 인용이 저장됐다.
- 첫 Spring 검증은 내부 서비스 토큰 불일치로 OpenAI 호출 전에 차단됐다.
  백엔드를 현재 ai/.env 토큰으로 재시작한 후 해결했다.

실제 비용은 응답 토큰 사용량을 수집하지 않아 산정하지 않았다. 계정 Usage에서 확인한다.
이 결과는 연결·저장 동작 검증이며 정확도/오탐률 개선 성과가 아니다.
추가 반복 평가나 다른 사용자 문서 인덱싱은 실행하지 않았다.
개별 결과는 ignored ai/.artifacts/runtime/minimal-live-success.json에 보관한다.
