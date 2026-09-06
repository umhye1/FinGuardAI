import json
from pathlib import Path

import pytest

from finguard_ai.classification import LocalClassifier
from finguard_ai.training import check_holdout, evaluate, load_rows, train

EXAMPLES = Path(__file__).parents[1] / "data/examples"


@pytest.fixture
def artifact():
    return train(load_rows(EXAMPLES / "synthetic-train.jsonl"), "test-v1", 0.25, 0.75, True)


def test_synthetic_training_requires_explicit_opt_in():
    with pytest.raises(ValueError, match="allow-synthetic"):
        train(load_rows(EXAMPLES / "synthetic-train.jsonl"), "test", 0.25, 0.75, False)


def test_json_artifact_inference_and_demo_safety(tmp_path, artifact):
    path = tmp_path / "model.json"
    path.write_text(json.dumps(artifact))
    with pytest.raises(ValueError, match="Synthetic"):
        LocalClassifier(path)
    model = LocalClassifier(path, True)
    assert model.classify("🦋🦋🦋").decision == "ABSTAIN"
    assert model.classify("정상 안내입니다").modelVersion == "test-v1"
    result = evaluate(model, load_rows(EXAMPLES / "synthetic-eval.jsonl"))
    assert result["samples"] == 8
    assert result["synthetic"] is True
    assert 0 <= result["coverage"] <= 1


def test_group_and_text_leakage_are_rejected(artifact):
    rows = load_rows(EXAMPLES / "synthetic-train.jsonl")
    with pytest.raises(ValueError, match="leakage"):
        check_holdout(artifact, rows)
    holdout = load_rows(EXAMPLES / "synthetic-eval.jsonl")
    holdout[0]["group"] = rows[0]["group"]
    with pytest.raises(ValueError, match="leakage"):
        check_holdout(artifact, holdout)


def test_duplicate_normalized_text_is_rejected(tmp_path):
    row = load_rows(EXAMPLES / "synthetic-train.jsonl")[0]
    duplicate = {**row, "id": "another", "text": row["text"].replace(" ", "  ")}
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(row) + "\n" + json.dumps(duplicate))
    with pytest.raises(ValueError, match="Duplicate"):
        load_rows(path)


@pytest.mark.parametrize("low,high", [(0.8, 0.2), (-0.1, 0.8), (0.5, 1.1)])
def test_invalid_thresholds(artifact, tmp_path, low, high):
    artifact["thresholds"] = {"pass": low, "flag": high}
    path = tmp_path / "model.json"
    path.write_text(json.dumps(artifact))
    with pytest.raises(ValueError, match="threshold"):
        LocalClassifier(path, True)
