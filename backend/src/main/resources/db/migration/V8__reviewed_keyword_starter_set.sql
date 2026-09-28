-- Weights are project heuristics, NOT official agency risk scores.
-- Preserve existing administrator edits and disabled keywords.
INSERT INTO phishing_keywords(keyword,risk_score,category,description,active,created_at)
VALUES
('원격제어',30,'PERSONAL_INFO_REQUEST','원격제어 앱 설치 유도 관련 단어. KISA 2026-09-17 nttId=72191. 단어만으로 사기를 확정하지 않음.',true,now()),
('앱설치',20,'LINK_INDUCTION','문자를 통한 앱 설치 유도. FSC 2025-01-20 /no010101/83889. 점수는 프로젝트 휴리스틱.',true,now()),
('택배',10,'LINK_INDUCTION','배송 사칭 관련 단어. FSC 2025-01-20 /no010101/83889. 정상 배송 문자에도 등장.',true,now()),
('배송조회',10,'LINK_INDUCTION','배송 조회를 미끼로 한 스미싱. KISA 2026-09-17 nttId=72191.',true,now()),
('교통법규위반',15,'INSTITUTION_IMPERSONATION','공공기관 사칭 관련 표현. KISA 2026-09-17 nttId=72191.',true,now()),
('특별경품',10,'PERSONAL_INFO_REQUEST','이벤트 참여 유도 관련 표현. KISA 2026-09-17 nttId=72191.',true,now()),
('저금리대출',15,'FINANCIAL_FRAUD','정부지원 대출 사칭 관련 표현. FSC 카드뉴스 cnId=1566 (2023). 정상 금융 안내에도 등장.',true,now()),
('계좌이체',20,'FINANCIAL_FRAUD','금전 이전 관련 표현. FSC 카드뉴스 cnId=1610 (2023). 정상 거래에도 등장.',true,now()),
('보증료',10,'FINANCIAL_FRAUD','사용자 제시 대출 사기 테스트에서 보완한 후보. 정상 대출 비용에도 등장; 공식 악성 키워드 지정 아님.',true,now()),
('검찰청',25,'INSTITUTION_IMPERSONATION','기관 사칭 분석용 기존 프로젝트 후보; 단어만으로 사기를 확정하지 않음.',true,now()),
('본인인증',15,'PERSONAL_INFO_REQUEST','개인정보 요구 관련 표현. FSC 2025-01-20 /no010101/83889.',true,now()),
('링크',20,'LINK_INDUCTION','문자 URL 유도 관련 표현. FSC 2025-01-20 /no010101/83889.',true,now())
ON CONFLICT(keyword) DO NOTHING;
