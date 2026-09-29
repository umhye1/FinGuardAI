from pathlib import Path

import numpy as np
import pytest

from finguard_ai.benchmark_data import load_splits
from finguard_ai.context_benchmark import metrics, rule_predict, select_candidate
from finguard_ai.context_model import ContextModel, fit

DATA = Path(__file__).parents[1] / "data/benchmarks/context-v1"


def test_abstention_cannot_hide_missed_phishing():
    rows = [{"label": "PHISHING"}, {"label": "PHISHING"}, {"label": "PREVENTION"}]
    predictions = [
        {"label": None, "decision": "ABSTAIN"},
        {"label": "NORMAL", "decision": "PASS"},
        {"label": "PHISHING", "decision": "FLAG"},
    ]
    result = metrics(rows, predictions)
    assert result["phishingNotFlagged"] == {"count": 2, "denominator": 2, "rate": 1.0}
    assert result["phishingPassed"]["rate"] == 0.5
    assert result["preventionFlagged"]["rate"] == 1.0
    assert result["normalFlagged"]["rate"] is None


def test_safe_artifact_roundtrip_and_oov(tmp_path):
    splits, manifest = load_splits(DATA)
    model = fit(splits["train"])
    path = tmp_path / "model.json"
    model.save(path, manifest)
    with pytest.raises(ValueError, match="explicit opt-in"):
        ContextModel.load(path)
    loaded = ContextModel.load(path, allow_synthetic=True)
    examples = [r["text"] for r in splits["dev"]]
    np.testing.assert_allclose(model.probabilities(examples), loaded.probabilities(examples))
    assert loaded.predict("🦋🦋") == {"label": None, "decision": "ABSTAIN", "probabilities": None}


def test_dev_selection_deterministic_without_test_input():
    splits, _ = load_splits(DATA)
    a, trials = select_candidate(splits["train"], splits["dev"], True)
    b, other = select_candidate(splits["train"], splits["dev"], True)
    assert trials == other
    assert a.threshold == b.threshold
    np.testing.assert_allclose(a.weights, b.weights)


def test_keyword_baseline_reproduces_prevention_false_positive():
    result = rule_predict("검찰청 사칭 링크의 본인 인증 요구에 주의하세요.")
    assert result["ruleScore"] == 60
    assert result["decision"] == "FLAG"
