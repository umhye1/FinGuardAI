# 로컬 Compose 실험 결과 — 2026-10-10 KST

## 결과

동일 Mac의 Docker Desktop에서 기동·backend stop/start·postgres stop/start **3/3회 통과**.
각 재생성/복구 이후 최초 합성 분석 상세 JSON이 완전히 일치했다. 이미지 수집 시점 수정 후 추가 1회도 통과했지만 아래 기본 3회 통계와 섞지 않는다.

단위: 초. 복구는 **start 호출 직전부터 전체 smoke 완료까지**다.

| 회차 | 기동 | backend 복구 | postgres 복구 | backend 중단부터 복구까지 | postgres 중단부터 복구까지 | 데이터 일치 |
|---|---:|---:|---:|---:|---:|---|
| 1 | 14.990 | 9.922 | 2.327 | 18.740 | 10.729 | 통과 |
| 2 | 16.816 | 9.900 | 2.347 | 18.890 | 10.740 | 통과 |
| 3 | 13.991 | 10.982 | 1.255 | 19.813 | 1.669 | 통과 |

범위: 기동 13.991–16.816초, backend 복구 9.900–10.982초, postgres 복구 1.255–2.347초.
3회만으로 SLA·일반적인 장애 복구 시간·개선율을 주장하지 않는다. 비교 대상이나 성능 개선 작업은 없다.

추가 1회: 기동 14.220초, backend 복구 9.860초, postgres 복구 2.363초, 데이터 일치 통과.

## 증거와 환경

- [기본 3회 원시 결과](results/compose-20261010-three-runs.json): `fd917ef4b8905467a9261800f1bbdf6891d8c63b`, 실행 소스는 커밋 상태.
- [기록 수정 후 1회 원시 결과](results/compose-20261010-metadata-check.json): `f7717ba55cc37e34e3b713fef2e332447b847c00`. 실행 당시 추가 변경은 운영 문서 링크와 테스트였으며 실행 코드 해시를 별도 기록했다.
- 시작/종료 시각은 JSON에 UTC로 기록. 기본 3회는 KST 01:11:40–01:14:13, 추가 확인은 01:14:32–01:15:21.
- Darwin 25.6.0 arm64, Docker 28.3.3, Compose 2.39.2-desktop.1, Docker VM 8 CPU / 8,218,316,800 bytes RAM.
- ARM64 이미지: 기존 frontend/backend/ai Dockerfile, pgvector/pgvector:pg16, redis:7-alpine. 추가 결과에 실제 이미지 ID를 기록했다. 두 실행 사이 이미지 재빌드는 없었다.
- 프로젝트/DB 볼륨: `finguard-ops-lab` / `finguard-ops-lab_postgres_data`.
- synthetic-train 20행, 로컬 모델 `ops-synthetic-v1`. 모델 SHA-256: `52a5a49020e0b275d68f16ad505e9a03fe93f6999f4c04ea1a8160e1892a4f5e`.
- 합성 계정 1개와 최초 분석 상세 1개를 보존 기준으로 사용. 성공 smoke에서 생성한 분석은 삭제. 실패 분석은 진단용으로 남을 수 있다.
- 이미지 빌드/최초 DB 준비를 마친 뒤 같은 볼륨으로 순차 반복. 캐시 초기화 없음, 동시 부하 없음. 이미지 태그는 가변이므로 나중에 다시 빌드하면 같은 바이너리/시간이 보장되지 않는다.
- 외부 생성·임베딩 호출 없음. 외부 API 키를 비운 Compose override와 local 분류 경로로 실행. RAG 품질/준비 완료를 검증한 결과가 아니다.

## 실제 관찰·조치

1. 시작 전 Docker daemon이 꺼져 있었다. Docker Desktop 실행 후 전용 환경을 준비했다.
2. backend 중단은 3회 모두 로그인 HTTP 요청의 8초 제한에서 TimeoutError로 감지했다. DB 중단은 1·2회 TimeoutError, 3회 HTTP 503이었다. 503 회차의 중단 감지 시간이 짧아 totalSeconds도 짧았다. 이를 DB 엔진 개선으로 해석하지 않는다.
3. 추가 확인 중 backend 로그에서 Hikari `Failed to validate connection` / `This connection has been closed` 경고를 확인했다. PostgreSQL 재시작 후 backend 재시작 없이 전체 smoke가 다시 통과했다. 경고 문구만 보고 maxLifetime을 임의 변경하지 않았다.
4. 최초 결과의 images가 null인 기록 결함을 발견했다. 최초 컨테이너 생성 전 목록을 읽은 것이 원인이었다. 준비 완료 후 목록을 저장하도록 수정하고 소스 해시도 추가했다. 원본 결과를 사후 수정하지 않고 추가 1회로 수정 동작을 확인했다.
5. 별도 AI 중단 검사: AI 컨테이너만 stop하고 smoke 실행 시 Spring의 HTTP 200 부분 결과를 `AI classification incomplete`로 거부했다. AI start 후 smoke 재통과(대기 함수 기준 9.861초, start 명령 시간 제외). 이 보조 검사는 기본 복구 통계에 합치지 않았다.
6. 비밀값·합성 로그인 정보·전체 로그는 커밋하지 않았다. 원시 결과 JSON은 허용된 환경/시간/실패 코드만 포함하는지 검토했다. 전체 backend 로그에는 자동 생성 보안 비밀번호가 포함될 수 있으므로 그대로 공개하지 않는다.

## 검증과 한계

- `python3 -m unittest discover -s infra/ops -p 'test_*.py' -v`: 8개 통과. AI 부분 성공/다른 모델, 데이터 변조, 장애 미감지, 복구 실패 후 start, 시간 초과, 쉘 설정 유입을 검사한다.
- 합친 Compose `config --quiet`: 통과.
- `prepare`: 세 이미지 빌드 및 합성 모델 학습 성공.
- `run --runs 3`, 수정 후 `run --runs 1`: 모두 통과.
- 클라우드 배포, 강제 crash, 백업 복원, 모든 테이블 무결성, 문서 업로드/임베딩, AI RAG DB 검색, 실제 브라우저 조작은 이번 측정 범위 밖이다.
- AI 도구(Codex)가 구현과 명령 실행을 수행했다. 사용자가 직접 실험하고 설명 가능한 범위를 확인하기 전에는 본인의 수동 장애 대응 경험으로 표현하지 않는다.

재현 명령과 실패 복구 절차는 [운영 안내](compose-recovery-lab.md)를 따른다.
