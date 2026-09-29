# RAG benchmark v1

2026-09-29 기준 공식 출처 요약 6개에 대해 직접 작성한 합성 질문 20개.
`manifest.json`은 질문과 두 corpus manifest 해시를 잠근다. 각 원문 내용 해시는
기존 corpus loader가 다시 검증한다. `relevantCorpusIds`는 exact document ID 정답이며
구버전 문서가 같은 family라도 최신 문서 정답을 만족하지 못한다.

15개는 자료에 근거한 응답 대상으로, 5개는 범위 외/모호/근거 부족 요청으로 작성했다.
독립 검수 전 초안이다. 특히 '내일 전액 반환된다는 근거'는 자료 부족으로 라벨링했으나
'그러한 보장은 확인되지 않는다'는 답변도 가능하므로 answerable의 의미를 재검토할 대상이다.
이 라벨로 생성 답변의 오답을 단정하지 않는다.

정답이 있는 질문만 Recall/Hit/AllRequired/MRR의 분모에 사용한다. 정답이 없는 질문의
생성 가능 여부 판단은 별도로 평가한다. 문서 선택 성공과 생성 답변 품질은 다르다.
현재 평가셋은 이미 결과를 관찰했으므로 검색·정책 수정 후 일반화 평가는 신규 holdout에서 한다.
실행법 및 결과 해석: `docs/evidence/ai-performance-v1/README.md`.
