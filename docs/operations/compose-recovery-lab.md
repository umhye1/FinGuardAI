# Compose 로컬 기동·복구 실험

이슈 #43. 기존 Docker 도입과 구분하여 **웹 → Spring → 로컬 AI → DB의 실제 응답과 복구**를 검증한다. 클라우드 공개·실서비스 장애 대응·분류 품질 평가가 아니다. 증분 임베딩과 사용량 대시보드는 후속 범위다.

## 실행

Docker Desktop/Engine, Compose v2, Python 3.11 이상이 필요하다. 저장소 루트에서 실행한다.

```bash
python3 infra/ops/lab.py prepare
python3 infra/ops/lab.py run --runs 3
python3 infra/ops/lab.py smoke
python3 infra/ops/lab.py status
# 실험 종료: 볼륨은 보존
python3 infra/ops/lab.py down
```

`prepare`는 기존 Dockerfile로 이미지를 빌드하고 기존 synthetic-train 자료로 데모 분류기를 만든다. 최초 다운로드·빌드·학습 시간은 기동 측정에 포함하지 않는다. 두 번째 prepare는 비밀값과 합성 계정을 유지한다. `run`은 실패하면 0이 아닌 종료 코드를 반환한다. 원인을 해결하고 동일 명령으로 다시 실행할 수 있으며 이전 결과를 덮어쓰지 않는다.

- 고정 프로젝트: `finguard-ops-lab`. 이 이름의 컨테이너는 실험 중 중단·재생성된다. 같은 프로젝트에서 동시 실행하지 않는다.
- 웹 `127.0.0.1:3100`, Spring `127.0.0.1:8180`, DB `127.0.0.1:56432`. 점유 중이면 점유 프로세스를 임의 종료하지 않고 확인한다.
- 기존 `finguard-dev`, 기존 사용자 DB, `infra/.env`, `ai/.artifacts`를 재사용하지 않는다.
- 전용 비밀값·모델·합성 계정·보존 기준 응답·원시 결과는 Git 제외된 `infra/.ops-lab/`에 둔다. 이 폴더를 삭제하면 기존 볼륨의 비밀번호/계정과 새 설정이 불일치할 수 있다.
- 기존 Compose에 `compose.ops.yml`을 합친다. 외부 AI 키는 빈 값, 분류기는 local로 강제한다. 쉘의 AI/Compose/포트/DB 설정도 제거하고 전용 env 파일을 사용한다.
- 실험 볼륨은 `finguard-ops-lab_postgres_data`, `..._redis_data`, `..._uploads`다. `down -v`는 사용하지 않는다.

## 성공 판정

단순 컨테이너 Running이나 HTTP 200은 충분하지 않다. 각 smoke는 다음을 확인한다.

1. 웹 HTML의 FinGuard AI 제목과 React root.
2. 웹 Nginx `/api` 프록시를 통한 합성 계정 로그인: DB 조회와 Redis 세션 저장.
3. 인증된 내 정보 조회와 합성 계정 일치.
4. 최초 저장한 분석 상세 전체 JSON과 현재 API 응답의 정확한 일치: ID·본문·분류·생성 시각 등 포함.
5. 새 분석 생성의 `modelResult.status == COMPLETED`, `modelVersion == ops-synthetic-v1`, 분석 ID 확인 후 상세 조회·삭제.

AI 연결 실패에도 Spring 분석 API는 HTTP 200 부분 결과를 줄 수 있다. 따라서 `FAILED`/`NOT_REQUESTED`는 실패다. 로컬 모델의 정상적인 `ABSTAIN` 판단은 허용한다. 데모 모델은 분류 정확도를 입증하지 않는다. 테스트가 성공해도 모든 브라우저 화면·관리자 기능·문서 업로드·RAG가 검증된 것은 아니다.

AI `/health/ready`는 외부 provider 준비까지 요구한다. 이 무료 실험에서는 503이 예상되며 이를 RAG 정상으로 해석하지 않는다. 핵심 성공 범위는 로컬 분류다. DB 읽기/쓰기와 AI 호출을 Spring 분석 경로에서 검증하지만 AI의 RAG용 DB 조회는 실행하지 않는다.

## 측정 정의

회차별 동일 이미지·기존 볼륨으로 순차 실행한다. 호스트/DB 캐시는 강제로 비우지 않는다.

| 항목 | 시작 | 종료 |
|---|---|---|
| startup.seconds | `compose up -d --no-build` 호출 직전 | 전체 smoke 성공 직후 |
| backend/postgres.seconds | 중단 감지 후 `compose start 서비스` 호출 직전 | 전체 smoke 성공 직후 |
| stopAndDetectionSeconds | `compose stop 서비스` 직전 | smoke 실패 관찰 직후 |
| totalSeconds | `compose stop 서비스` 직전 | 복구 smoke 성공 직후 |

기동 전 `compose down` 시간은 startup에 포함하지 않는다. stop/start는 정상 종료를 포함한 수동 복구 실험이며 kill/crash, 자동 재시작, 백업 복원, 디스크 손상 실험은 아니다. DB 중단 시 backend와 AI는 그대로 두어 기존 연결 풀의 재연결을 확인한다.

`time.monotonic()`으로 측정하고 실패 시 1초 간격 재시도한다. HTTP 요청별 제한은 8초, 기본 재시도 창은 180초다. 마지막 진행 중 요청 및 1초 대기 때문에 창보다 늦게 끝날 수 있다. 값에는 Compose 실행·API 검사·합성 분석 정리 비용이 포함되어 순수 서버 준비 시간이나 상용 MTTR이 아니다. 측정 중 사용자가 개입하지 않으며 사람의 진단 시간은 측정하지 않는다.

컨테이너 재생성 및 각 서비스 복구 후 같은 분석 상세를 조회한다. 이는 해당 합성 행의 볼륨 영속성 증거이며 모든 테이블/파일 무결성이나 백업 복원 보장은 아니다.

## 실패 진단과 복구

결과 파일은 `infra/.ops-lab/result-UTC시각.json`이다. 통과 회차와 실패 지점을 함께 보존한다. 인증 토큰·비밀번호·원문 응답을 결과에 넣지 않는다. 자동 수집 결과 외 로그를 공유할 때는 내용을 검토한다.

```bash
# 전용 프로젝트에만 접근한다. config 전체 출력은 비밀값을 포함하므로 피한다.
docker compose -p finguard-ops-lab --env-file infra/.ops-lab/lab.env \
  -f infra/compose.yml -f infra/compose.ops.yml ps

docker compose -p finguard-ops-lab --env-file infra/.ops-lab/lab.env \
  -f infra/compose.yml -f infra/compose.ops.yml logs --tail 100 backend ai postgres

# 실패 후 수동 복구: 데이터 볼륨은 유지
docker compose -p finguard-ops-lab --env-file infra/.ops-lab/lab.env \
  -f infra/compose.yml -f infra/compose.ops.yml up -d --no-build
python3 infra/ops/lab.py smoke
```

- Docker 연결 실패: Desktop/Engine 실행과 권한 확인.
- `HTTP 502`: 웹은 살아 있지만 backend 연결이 안 되는 구간인지 backend 로그 확인.
- 로그인 시간 초과/5xx: PostgreSQL 상태와 Hikari 재연결 로그 확인. 임의로 DB 볼륨 삭제하지 않는다.
- `AI classification incomplete`: AI 모델 마운트·학습 결과·서비스 토큰 연결 확인. provider 키를 넣어 우회하지 않는다.
- `persisted analysis changed or missing`: 다른 DB/볼륨 연결 또는 데이터 변경 여부 확인. 기준 JSON을 새 값으로 덮어써 통과시키지 않는다.
- 도중 실패/일반 중단에서는 `finally`가 중단 대상 서비스를 다시 시작한다. 프로세스 강제 종료나 Docker 중단에서는 수동 복구 명령이 필요하다.

## 회귀 검증과 직접 시연

```bash
python3 -m unittest discover -s infra/ops -p 'test_*.py' -v
```

CI는 실패 판정과 Compose 구성 유효성을 검사한다. CI 단위 테스트 성공을 실제 Docker 3회 실험 성공으로 대신하지 않는다. 실제 측정 자료는 [실험 결과](compose-recovery-results.md)에 기록한다.

면접 전 직접 `run --runs 1`을 실행하고, 중단된 서비스·관찰된 오류·복구 조건을 설명해 본다. AI 도구가 구현·실행을 도왔다는 사실과 본인이 직접 확인한 범위를 구분한다. 자소서에는 실제 결과와 로컬 실습 범위만 기입한다.
