# 공개 사례 검수 대기 v1

**19건 모두 미검수. 학습/평가 데이터로 등록하지 않았다.** 검수자는 혜원님이 맡기로 했으나,
이는 검수 완료나 각 문장의 정답 확인을 뜻하지 않는다. 모델 예측은 실행하지 않았다.

## 출처와 표현 범위

- 관계부처 합동(과기정통부·방통위·금융위·경찰청·KISA·금감원),
  「정부, 추석 명절 연휴기간 스미싱 등 전기통신금융사기 피해 예방·대응 수칙 안내」,
  2025-09-28, [공식 PDF](https://www.kmcc.go.kr/download.do?fileSeq=61948).
  PDF 6쪽의 공공누리 출처표시 마크를 렌더링 확인했다. 7쪽의 본문 문자 예시 12건,
  3·11쪽의 안내 발췌 4건. 그림·사진·연락처 표는 수집하지 않았다.
- 과학기술정보통신부 / 정책브리핑, 「추석 앞두고 택배·국민지원금 사칭한 스미싱 조심하세요」,
  2021-09-13, [본문](https://www.korea.kr/news/policyNewsView.do?newsId=148893067).
  텍스트 공공누리 제1유형 표시 확인. 예방 수칙 문단 3건, 사진 제외.
- 금융위원회 2020년 카드뉴스는 변경금지 등이 포함된 제4유형이라 링크 목록에만 남겼다.

원문 문장·위치는 candidates.jsonl, 게시일·수집일·이용조건·PDF SHA-256은 sources.json에 있다.
레이아웃 줄바꿈을 연결하고 예시의 `<URL>`만 `[URL]`로 바꿨다. 원문 오탈자는 보존했다.
기관이 공개한 예시이지 피해자가 제공한 실제 수신 원문이라고 주장하지 않는다.
안내문은 문단 발췌이므로 원래 메시지 전체와 다르다. 과거 자료는 문맥 분류용이며 최신 대응 안내로
배포하지 않는다. 동일 문서의 후보는 하나의 group으로 묶어 서로 다른 split에 나누지 않는다.

## 혜원님 검수 방법

저장소 루트에서:

```bash
cd ai
.venv/bin/python -m finguard_ai.curation prepare \
  --queue data/review/public-cases-v1 --reference data/benchmarks/context-v1 \
  --output .artifacts/review/public-cases-v1
```

이미 생성했으면 다시 실행하지 말고 해당 폴더의 `review.html`을 브라우저로 연다.
먼저 문장만 보고 라벨과 이유를 고르고, `provenance.json`을 열어 출처·이용조건·중복 비교를 확인한다.
출처의 분류명은 정답 힌트가 될 수 있으므로 첫 판단 뒤 확인한다. 예측 결과·추정 라벨은 없다.

- NORMAL: 일반 대화나 정상 안내
- PHISHING: 개인정보·금전·악성앱 등 사기 행동을 유도하는 문맥
- PREVENTION: 사기를 예방하거나 사기 문구를 설명·인용하는 문맥
- UNCERTAIN: 문장만으로 판단하기 어려움. 정답으로 강제 편입하지 않는다.
- EXCLUDE: 불명확함, 중복, 개인정보 또는 이용조건 문제 등. 이유 필수.

확인한 항목만 체크하고 검수자·검수일을 작성한 뒤 JSON을 다운로드한다.
화면에 자동 저장 기능은 없다. 중간 결과도 다운로드할 수 있으며 JSON을 직접 편집할 수 있다.
로컬 `.artifacts/` 안에 보관하고 검수자 이름·개인 수신 문자는 Git에 커밋하지 않는다.
개인정보 탐지 정규식은 보조 검사이며 이름·주소 등을 모두 찾아내지 못한다.

## 등록 전 차단 조건

```bash
.venv/bin/python -m finguard_ai.curation finalize \
  --queue data/review/public-cases-v1 --reference data/benchmarks/context-v1 \
  --review .artifacts/review/public-cases-v1/review.json \
  --output .artifacts/review/public-cases-v1-approved
```

큐 해시, 모든 항목의 처리/이유, 승인 라벨, 개인정보/이용조건/중복 확인, 별도 검수자 선언을 검사한다.
이후 기존 encoder_data의 3개 클래스·기존 train/dev/test 중복 차단 규칙을 그대로 적용한다.
승인 시 evaluation.jsonl과 기존 register-evaluation에 입력 가능한 review.json이 생성된다.
코드는 검수자의 실제 독립성을 확인하지 못한다. 선언 기록과 실제 절차를 구분한다.

**이 큐에는 동의받은 정상 대화가 없으므로 검수만으로 완성된 평가셋이 되지 않는다.**
정상 라벨 수를 채우려고 안내문/불명확 예시를 NORMAL로 변경하지 않는다. 정상 자료와 다양한 출처의
사례를 확보한 다음 새 큐 버전으로 검수 범위를 확장해야 한다. 동의 자료는 public queue가 아닌
`data/private/`에서 출처·이용 동의를 관리하고 기존 외부 평가 등록 절차를 사용한다.
이 도구의 공개 출처 허용 범위는 현재 확인된 KOGL-1 텍스트에 한정한다.

문자 유사도는 SequenceMatcher의 문자열 유사도(0.8 이상 표시)이며 의미 중복이나 독립성을 증명하지
않는다. 동일 자료의 다른 재게시본·유사 문장도 사람이 제외해야 한다. 이 19건으로 실사용 정확도,
오탐 감소율, 대표성을 주장할 수 없다. 검수 완료 전 학습·튜닝·평가에 사용하지 않는다.
