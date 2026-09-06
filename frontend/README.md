# FinGuard AI 프론트엔드

React + TypeScript + Vite 기반의 반응형 사용자/관리자 워크스페이스입니다.

## 로컬 실행

Node.js 22 LTS 기준. 저장소 루트에서:

```bash
npm ci --prefix frontend
npm run dev --prefix frontend
```

http://127.0.0.1:5173 에서 접속합니다. 백엔드를 별도로 실행해야 합니다.
Vite는 `/api`를 `http://127.0.0.1:8080`으로 프록시합니다.
백엔드 주소 변경은 `BACKEND_URL=http://127.0.0.1:18080 npm run dev --prefix frontend`처럼 설정합니다.
AI 키와 내부 서비스 토큰은 프론트에 넣지 않습니다.

## 제공 화면

- 로그인·회원가입, 홈
- 의심 문자 분석: 규칙 점수, AI 판단/보류/실패 구분, 피드백
- 내 분석 이력 상세·삭제
- 문서 Q&A: 대화 생성·삭제, 기존 메시지, 인용 문단, 근거 부족 상태
- 관리자: 통계, PDF 업로드·실패 재처리·삭제, 키워드 등록·수정·비활성화, 피드백 검토, 분석·감사 로그

관리자 권한은 백엔드가 판정합니다. 일반 회원가입은 USER 계정이며 UI에서 관리자 승격을 제공하지 않습니다.
문서 추출 완료는 임베딩 완료를 뜻하지 않습니다. 현재 인덱싱은 ai/README.md의 CLI를 사용합니다.

## 인증·실패 처리

토큰은 메모리에만 보관합니다. 새로고침/탭 종료 시 다시 로그인해야 합니다.
동시 401 요청은 하나의 refresh 요청을 공유하며, 갱신 실패 시 로그인 화면으로 이동합니다.
백엔드의 JSON 토큰 계약을 그대로 사용합니다. 지속 로그인을 도입하려면 HttpOnly 쿠키 기반 계약과 CSRF 정책을 함께 설계해야 합니다.
요청 타임아웃 후 변경 작업이 서버에서 완료되었을 수도 있으므로 목록 확인 후 재시도합니다.
분석/채팅 입력은 localStorage에 저장하지 않으며, 서버에 전송된 내용은 기존 백엔드 정책에 따라 저장됩니다.

## 검증

```bash
npm run build --prefix frontend
npm test --prefix frontend
cd frontend
npx playwright install chromium
npx playwright test
```

Vitest는 토큰 갱신 경쟁·만료·로그인 변경·multipart 전송을 검증합니다.
Playwright는 모의 API로 데스크톱/모바일 사용자 흐름과 관리자 진입을 검증합니다.
모의 API 테스트는 실제 Gemini 응답 품질이나 전체 실서버 통합 검증을 대체하지 않습니다.

## 컨테이너

저장소 루트에서 기존 infra/.env를 설정한 뒤:

```bash
docker compose --env-file infra/.env -f infra/compose.yml up --build -d
```

프론트는 http://127.0.0.1:3000 에서 제공됩니다.
Nginx가 `/api`를 backend:8080으로 프록시하고 클라이언트 경로 새로고침을 지원합니다.
이 구성은 로컬 개발용입니다. 외부 배포 시 TLS와 도메인 설정이 추가로 필요합니다.
