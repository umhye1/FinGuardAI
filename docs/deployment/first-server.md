# 첫 단일 서버 배포 (#39)

## 현재 상태와 완료 기준

PR #38은 main에 병합됐다. 이 문서는 서버 배포를 위한 구성과 절차다.
클라우드 서버 생성, DNS 연결, 공개 HTTPS, 실제 모델/공식 문서 적재 및 사용자 흐름은 아직 검증하지 않았다.
배포 경험에는 이 단계들을 직접 실행해 확인한 결과만 추가한다.

목표는 단일 Linux 서버에서 Caddy → frontend nginx → Spring, 내부 AI/PostgreSQL/Redis를
운영하는 것이다. `infra/compose.yml`의 로컬 환경과 별도 프로젝트 `finguard-prod`·볼륨을 쓴다.
DB·Redis·Spring·AI 포트는 호스트에 공개하지 않는다. API는 frontend와 같은 출처 `/api/`를 쓴다.
고가용성·무중단 배포는 제공하지 않는다. 서버 장애 시 전체 서비스가 중단된다.

## 월 1만 원 비용 제약 (2026-09-29 확인)

- 서버를 아직 생성하지 않는다. AWS 계정의 Billing → Credits에서 잔액·만료일·적용 서비스를 확인한다.
- 무료 이용은 계정 생성일과 플랜에 따라 다르다. 기존 계정에 신규 가입 크레딧이 있다고 가정하지 않는다.
- AWS Linux Lightsail 공개 IPv4 요금표는 512MB $5, 1GB $7, 2GB $12, 4GB $24/월이다.
  환율·세금·초과 트래픽·스냅샷·도메인·LLM 비용은 별도 고려한다.
- Spring/AI/DB 동시 실행과 빌드에는 우선 4GB급을 검토한다. 이는 실측 최소 사양이 아니며
  월 1만 원 상시 운영에 맞는 선택이 아니다. 512MB 서버를 싸다는 이유로 선택하지 않는다.
- 크레딧이 없다면 기간을 정한 배포 실습 후 데이터를 백업하고 리소스를 삭제하는 방식으로
  비용 견적을 다시 산정한다. 중지한 Lightsail 인스턴스에도 요금이 발생한다.
- AWS Budgets 알림은 비용 강제 차단 장치가 아니다. 월 상한과 현재 지출·환율을 확인한 뒤
  서버 종류·실행 기간·정리 시각을 정한다. 이 PR은 자동 과금 중단을 구현하지 않는다.
- 현재 AWS 인증 도구 연결, 크레딧, 도메인은 확인되지 않았다. 서버/도메인 구매를 자동 실행하지 않는다.

공식 자료: [Lightsail 요금표](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html),
[무료 이용](https://aws.amazon.com/free/free-tier-faqs/),
[과금 FAQ](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html).

## 선택한 무료 배포 대상: Oracle Cloud Always Free

사용자는 Oracle Cloud 신규 가입 후 무료 서버 배포를 선택했다. 현재 계정 가입 대기 중이다.
AWS EC2/S3 경험은 있으므로 무료 서버에서 컨테이너 통합·HTTPS·상태 검사·복구를 경험하는 방향도 가능하다.
현재 공식 Always Free 문서는 A1 ARM 총 2 OCPU·12GB, 부트/블록 볼륨 합계 200GB를 안내한다.
과거 블로그의 4 OCPU·24GB를 그대로 적용하지 말고 실제 계정 한도와 생성 화면의 무료 표시를 확인한다.
홈 리전에서 무료 대상 Ubuntu/A1을 선택하고, 계정 전체 기존 사용량을 합산한다.
첫 검토 사양은 A1 2 OCPU·6GB RAM·50GB 부트 볼륨이다. 실측 최저 사양은 아니며
생성 화면에서 Always Free 적격과 비용을 확인한 뒤 적용한다. 계정/리전에서 확보할 수 없으면 생성하지 않는다.
가입·본인 인증은 사용자가 직접 진행한다. 용량 부족 시 유료 유형으로 자동 전환하지 않는다.
유휴 인스턴스는 회수될 수 있으므로 별도 백업이 필요하며 무료 자원 확보를 보장하지 않는다.

이 Compose 구성은 AWS 전용 서비스에 의존하지 않는다. A1에서는 ARM64로 서버에서 이미지를 빌드한다.
공개 서브넷/인터넷 게이트웨이/경로와 보안 규칙을 설정하고 SSH는 본인 IP만, HTTP/HTTPS만 공개한다.
호스트 방화벽도 확인한다. DB·Redis·Spring·AI 포트를 인터넷에 노출하지 않는다.
공개 DNS 이름을 확보한 후 아래 공통 절차로 진행한다. 도메인 구매와 외부 LLM API는 무료 서버와 별도다.
계정 생성·인스턴스 확보·실제 TLS·복구 검증은 아직 실행하지 않았다.

[Oracle 공식 무료 범위와 회수 조건](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).
Render 무료는 월 750 실행 시간을 워크스페이스에서 공유하고 무료 DB는 30일 만료라,
현재 여러 프로세스와 영속 DB를 그대로 유지할 첫 선택으로 쓰지 않는다.
[Render 무료 제한](https://render.com/docs/free).

## 서버 준비

1. 비용 확인 후 Linux 서버, Docker Engine 및 Compose v2를 준비한다.
   [Docker Ubuntu 설치 문서](https://docs.docker.com/engine/install/ubuntu/)를 따른다.
   SSH 22는 본인 IP만 허용하고, 공개 포트는 80/443만 허용한다. 5432/6379/8080/8000은 열지 않는다.
2. 저장소를 `/opt/finguard/app` 등에 clone하고 배포할 검토 완료 커밋을 checkout한다.
   쓰기 권한 토큰을 서버에 복사하지 말고 필요한 경우 저장소 읽기 전용 인증을 쓴다.
3. 사용할 도메인의 A 레코드를 고정된 서버 주소로 연결한다. IPv6를 쓰지 않으면 AAAA는 만들지 않는다.
   도메인이 없으면 먼저 확보 가능한 도메인/서브도메인을 결정한다. 이 구성은 공개 DNS 이름을 전제로 한다.
4. 다음 파일을 서버에서 준비한다. 비밀값을 채팅/PR/로그에 출력하지 않는다.

```bash
cd /opt/finguard/app
cp -n infra/production/.env.example infra/production/.env
chmod 600 infra/production/.env
# 서버의 편집기로 .env 설정
```

`POSTGRES_PASSWORD`, `JWT_SECRET`, `AI_SERVICE_TOKEN`은 각각 독립적인 충분히 긴 난수로 설정한다
(JWT와 서비스 토큰 32자 이상). 비밀번호에 Compose 치환 문자가 있으면 dotenv 인용 규칙을 따른다.
`SITE_DOMAIN`에는 프로토콜/경로 없이 DNS 이름을 넣는다.
`MODEL_DIR`에는 검토된 비데모 `classifier.json`이 있는 절대 경로를 넣고 UID 10001이 읽을 수 있게 한다.
학습용 BERT 체크포인트를 이 JSON 분류기 자리에 넣지 않는다.
`AI_PROVIDER`와 해당 API 키, 생성/임베딩 모델을 일치시킨다. API 키를 넣는 것만으로 과금되지는 않지만
질문·분류 설정·인덱싱 실행은 과금을 발생시킬 수 있다. 별도 비용 승인 전에는 유료 요청을 하지 않는다.
DB는 새 볼륨을 사용하고 Flyway가 스키마를 만든다. 기존 DB 연결/자동 baseline은 금지한다.

## 배포

```bash
bash infra/production/deploy.sh
```

스크립트는 HEAD SHA를 세 앱 이미지 태그로 사용하고, 먼저 모두 빌드한다. 빌드 실패 시 기존 서비스는
유지된다. 이후 공개 proxy와 앱을 중지하고 Spring/AI를 함께 교체한다. DB/Redis → Spring 스키마 적용 →
AI readiness → frontend 순서로 확인한 뒤 proxy를 시작한다. 교체 중 다운타임이 있다.
실패 시 proxy를 다시 열지 않는다. 이전 이미지/볼륨을 자동 삭제하지 않는다.
`unless-stopped`로 재부팅 재시작을 지원하지만 Docker healthcheck 자체는 비정상 컨테이너를 재시작하지 않는다.
AI/Spring 초기화 실패 시 로그와 설정을 확인해야 한다. 운영 지표 수집·경보는 후속 작업이다.

내부 상태 검사와 공개 검증은 별개다. 배포 후 서버에서 다음 명령을 위한 함수를 설정한다.

```bash
export RELEASE_SHA=$(git rev-parse HEAD)
dc() { docker compose --env-file infra/production/.env -f infra/production/compose.yml "$@"; }
dc ps
dc exec -T backend curl --fail --silent http://127.0.0.1:8080/actuator/health
dc exec -T ai curl --fail --silent http://127.0.0.1:8000/health/ready
# 실제 DNS 이름으로 변경. 인증서 검증을 끄는 -k는 사용하지 않는다.
curl --fail --silent --show-error https://YOUR_DOMAIN/ -o /dev/null
```

외부 브라우저에서 회원가입/로그인과 인증이 필요한 화면을 검증하고, 비로그인 API는 401이어야 한다.
AI readiness는 모델·공급자 설정·DB 준비 검사이며, 공급자 키 유효성/유료 응답/공식 근거 품질을 보장하지 않는다.
공식 문서 적재는 별도의 관리자 작업과 인덱싱을 필요로 한다. `ai/README.md`를 따르고
검토된 manifest와 문서 해시를 확인한다. 빈 DB가 준비된 상태를 RAG 완료로 기록하지 않는다.
유료 검증은 예산을 정한 뒤 신고 안내 한 건과 범위 밖 질문 한 건으로 제한해 정책 v3 및 보류를 확인한다.

Caddy는 공개 DNS와 80/443 연결을 이용해 HTTPS 인증서를 발급한다. 실제 DNS/TLS 성공은 서버에서 검증한다.
인증서 데이터는 별도 볼륨에 유지한다. 요청 본문/토큰을 로그에 넣지 않는다.
[HTTPS 전제조건](https://caddyserver.com/docs/automatic-https),
[Compose 상태 의존성](https://docs.docker.com/compose/how-tos/startup-order/).

## 백업과 실패 복구

배포 전에 DB와 업로드 파일을 같은 중단 구간에 백업한다. 실행 중 별개 시점 백업은 일관성을 보장하지 않는다.
아래 `dc` 함수는 앞 절의 정의를 사용한다. 백업은 서버 외부의 접근 제한된 장소에도 복사한다.
로컬 파일만 남기는 것은 서버 유실에 대한 백업이 아니다. 모델 파일·환경 설정·릴리스 SHA도 별도로 보존한다.

```bash
umask 077
backup_dir="/opt/finguard/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
dc stop proxy frontend backend ai
dc exec -T postgres pg_dump -U finguard -d finguard -Fc > "$backup_dir/db.dump"
# 이름을 추측해 직접 볼륨에 접근하지 않고 backend의 마운트로 복사한다.
dc cp backend:/app/uploads "$backup_dir/uploads"
git rev-parse HEAD > "$backup_dir/release.txt"
# 백업 파일 확인 후 새 배포 또는 기존 서비스를 시작한다.
```

롤백은 이전 커밋 checkout 후 동일 deploy.sh 실행이다. 이전 이미지도 보존하되 이 스크립트는 재빌드한다.
앱 롤백은 DB 마이그레이션을 되돌리지 않는다. 스키마 호환이 확인된 경우에만 이 방법을 쓴다.
PR #38은 마이그레이션 변경이 없어 이전 스키마와 호환되지만, AI/Spring은 항상 같은 커밋으로 맞춘다.
스키마 복원이 필요하면 운영 DB를 즉시 덮어쓰지 말고 별도 새 DB에 `pg_restore`하고 row count·로그인·
업로드 참조를 검증한 뒤 전환한다. Redis refresh-token 상태가 사라지면 사용자가 다시 로그인해야 한다.
복구 훈련 완료 전에는 복구 검증을 했다고 기록하지 않는다.

종료는 `dc down`이다. `down -v`, 볼륨 삭제, 이미지 전체 prune은 일반 배포/롤백에 쓰지 않는다.
서버 삭제는 백업 확인 후 해당 클라우드에서 별도 실행하고 남은 디스크·스냅샷·고정 IP 과금도 확인한다.

## 남길 배포 경험 증거

배포 커밋, 이미지 ID, 서버 사양, UTC 시작/완료 시각, 다운타임, 내부 상태, 공개 HTTPS,
로그인 결과, 비용 내역, 신고 질문과 보류 질문 결과(민감정보 제거), 실패/롤백 원인과 복구 시간을 기록한다.
정적 설정 검사와 실제 배포 성공을 구분한다. 현재 검증 결과는 PR 본문에 기록한다.

이미지 태그는 커밋 단위지만 기반 이미지 태그와 일부 빌드 도구는 변할 수 있다. 완전한 비트 단위 재현성을
보장하지 않는다. 검증된 이미지 ID를 보존하고, 배포 전에 보안 업데이트를 검토한다.

## 로컬 검증 결과 (2026-09-29, 이슈 #39)

- Compose 문법, 공개 포트 80/443만 존재, 공통 릴리스 태그, 데모 모델 금지 확인.
- `python3 -m unittest discover -s infra/production/tests -v`: 3개 통과.
  빌드 실패 시 기존 서비스 유지, readiness 실패 시 proxy 미시작, 정상 순서를 검증한다.
- frontend/backend/ai Docker 이미지 Linux ARM64 빌드 성공 (`issue39-validation` 태그).
- Caddy 컨테이너 `caddy validate`: 통과. 인증서 발급이나 공개 HTTPS 테스트는 아니다.
- `finguard-issue39-check` 격리 Compose: PostgreSQL/Redis/backend/frontend healthy,
  Spring `/actuator/health` UP 확인. 빈 모델 디렉터리·API 키 없음인 AI `/health/ready`는 503 확인.
- 테스트용 프로젝트의 컨테이너·볼륨은 종료 후 삭제했다. 기존 사용자 DB/볼륨과 운영 서버는 변경하지 않았다.
- 유료 API 호출 0, 클라우드 리소스 생성 0. 실제 Oracle 배포·가입·DNS·RAG 성공 검증은 미완료다.
- 프론트 빌드의 기존 npm 의존성에서 moderate 2건 경고가 출력됐다. 이 작업에서 강제 업데이트하지 않았다.
