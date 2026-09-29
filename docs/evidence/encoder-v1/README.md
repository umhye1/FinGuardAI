# 한국어 encoder 미세조정 실험 — #33

이번에는 실제 `klue/bert-base`의 전체 가중치를 3분류 태스크로 미세조정하고 저장·재로드·평가했다.
생성 LLM 파인튜닝이 아닌 한국어 BERT encoder 분류 학습이다. 학습 코드는 별도 CLI이며
FastAPI 운영 모델을 변경하거나 서버/DB를 재시작하지 않았다. 유료 API 호출은 0회다.

## 모델과 데이터

- [KLUE 모델 카드](https://huggingface.co/klue/bert-base), CC BY-SA 4.0.
- 고정 revision: `77c8b3d707df785034b4e50f2da5d37be5f0f546`.
- [Transformers 분류 학습 문서](https://huggingface.co/docs/transformers/tasks/sequence_classification).
- 공개 safetensors만 로드하며 remote code는 실행하지 않는다. 원 모델의 분류 head는 새로 초기화한다.
- 파라미터 110,619,651개 전체를 학습했다. 모델 가중치는 약 443MB이며 Git에는 넣지 않았다.
- 기존 합성 train 36 / dev 18 / test 30. test는 이미 이전 실험에서 관찰했으므로 독립 평가가 아니다.
- 학습은 train/dev 파일만 읽으며 test가 없어도 실행된다. dev 비용 함수로 체크포인트와
  보류 임계값을 선택하고, test는 재로드 후 별도 명령에서만 평가한다.
- CPU 2 threads, seed 42, AdamW lr 2e-5, batch 4, max tokens 128, 1 epoch.
  학습 루프 약 16.97초(다운로드·모델 로드 제외). train/dev/test 잘린 입력 0개.

## 관찰 결과

| 방식 | 사기 FLAG 실패(보류 포함)/10 | 사기를 PASS/10 | 예방 오탐/10 | 보류/30 | CPU p50 |
|---|---:|---:|---:|---:|---:|
| 규칙 | 3 | 3 | 6 | 0 | 0.18ms |
| 기존 이진 방식(.25/.75) | 10 | 0 | 0 | 30 | 0.83ms |
| 이진 임계값 통제군 | 1 | 0 | 0 | 1 | 0.91ms |
| 문자+단어 3분류 | 0 | 0 | 0 | 0 | 1.98ms |
| BERT 1 epoch (dev 선택 threshold .5) | 4 | 0 | 0 | 14 | 133.06ms |

강제 argmax 기준 BERT는 정상 1개를 사기로, 사기 1개를 예방으로 분류했다. 해당 입력들은
보류되어 실제 FLAG/PASS 오류 지표에는 나타나지 않는다. 보류율을 함께 봐야 하는 이유다.
현재 실험에서 BERT는 더 느리고 더 많이 보류해 기존 모델보다 우수하다고 볼 수 없다.
데이터가 작고 합성 문체에 편향돼 있으며 1 epoch만 수행했으므로 BERT 자체가 열등하다는
결론도 아니다. test 결과를 보고 재학습/임계값 변경을 반복하지 않았다. 운영 모델 승격 없음.
지연은 로컬 30회 단건 측정으로 서버 부하 테스트가 아니다. 원자료·가중치 해시는 JSON 참조.

## 재현

아래 명령은 ai/에서 실행한다. 기존 서비스와 의존성을 분리하려면 별도 venv를 사용한다.
기본 서비스 설치에는 torch/transformers를 추가하지 않았다. 다운로드는 무료 공개 가중치다.

```bash
cd ai
python3 -m venv .venv-encoder
.venv-encoder/bin/pip install -c requirements.lock -e '.[test]'
.venv-encoder/bin/pip install -r requirements-encoder.txt
HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 \
  .venv-encoder/bin/python -m finguard_ai.encoder_experiment train \
  --data data/benchmarks/context-v1 --output .artifacts/encoder-new \
  --download --allow-synthetic --epochs 1 --threads 2
.venv-encoder/bin/python -m finguard_ai.context_benchmark \
  --data data/benchmarks/context-v1 --output-dir .artifacts/encoder-new-baselines --allow-synthetic
HF_HUB_OFFLINE=1 .venv-encoder/bin/python -m finguard_ai.encoder_experiment evaluate \
  --model .artifacts/encoder-new --data data/benchmarks/context-v1 \
  --baseline-report .artifacts/encoder-new-baselines/classification-report.json \
  --output .artifacts/encoder-new/comparison.json --allow-synthetic
```

출력 경로가 존재하면 덮어쓰지 않는다. 기본 학습은 캐시만 사용하며 `--download`일 때만
공개 모델 다운로드를 허용한다. 학습 중 test 파일을 수정하면 사후 평가의 해시 검사에서 거부된다.
max tokens를 초과하는 문장은 잘릴 수 있으며 그 수를 보고한다. 문장 뒷부분의 사기 유도를
놓칠 수 있으므로 긴 입력 검증 없이 서비스에 배포하지 않는다.

## 독립 평가 데이터 등록

실제 독립 검수 데이터는 아직 없다. 소프트웨어는 독립 검수를 대신하지 않는다.
허가된 사례를 새로 수집하고 작성자와 다른 검수자가 라벨/이용 근거를 확인해야 한다.
JSONL 행은 기존 id/group/text/label/source/sourceType 형식이다. 원문은 data/private/에 보관한다.
검수 파일 형식:

```json
{
  "datasetAuthor": "작성자 식별자",
  "reviewer": "별도 검수자 식별자",
  "reviewedOn": "2026-09-29",
  "independentReviewAttested": true,
  "approvedRows": {
    "row-id": {"label": "PHISHING", "usageBasis": "이용 허가 또는 동의 근거"}
  }
}
```

모든 행에 승인 라벨과 이용 근거가 있어야 한다. 도구는 검수자 신원/허가 진위를 검증하지
못한다. 합성 사례는 독립 검수했더라도 계속 synthetic으로 기록된다. 기존 train/dev뿐 아니라
이미 관찰한 test와의 ID/group/정규화·마스킹 텍스트 중복도 등록 단계에서 차단한다.
의미상 비슷한 변형 문장의 누수는 별도 사람이 검토해야 한다.

```bash
.venv-encoder/bin/python -m finguard_ai.encoder_experiment register-evaluation \
  --data data/private/external.jsonl --review data/private/review.json \
  --benchmark data/benchmarks/context-v1 --output .artifacts/external-registration.json
.venv-encoder/bin/python -m finguard_ai.encoder_experiment evaluate \
  --model .artifacts/encoder-new --data data/private/external.jsonl \
  --registration .artifacts/external-registration.json \
  --output .artifacts/external-report.json --allow-synthetic
```

모델 자체가 합성 학습이면 마지막 opt-in이 필요하다. 외부 데이터는 자동 생성/수집하지 않는다.
현재 비교 CLI의 baseline 보고서 결합은 동일 기존 benchmark만 허용한다. 외부 평가의 기준선
비교는 신규 데이터 확보 후 별도 동일 행 추론 결과를 준비해야 한다.

## 검증과 자소서 표현

로컬 AI 비통합 114개 통과(DB 통합 6개 제외), Ruff 통과. 작은 무작위 BERT로 실제 gradient
갱신·safetensors 저장·재로드를 테스트하고 CI에서는 pretrained 다운로드 없이 이 테스트만 수행한다.

말할 수 있는 경험: “한국어 사전학습 encoder를 3개 의도로 미세조정하고, dev로 임계값을
선택한 뒤 기존 선형 모델과 미탐·오탐·보류·지연을 비교했다. 복잡한 모델이 작은 합성 데이터에서
더 낫지 않음을 확인해 운영 적용을 보류하고 독립 데이터 검수 경로를 마련했다.”
실사용 정확도 개선, 독립 평가 완료, 생성 LLM 미세조정으로 표현하면 안 된다.
