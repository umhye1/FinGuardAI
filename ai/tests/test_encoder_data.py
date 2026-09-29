import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from finguard_ai.benchmark_data import load_splits
from finguard_ai.encoder_data import check_external, load_registered, reference_hashes, register
from finguard_ai.encoder_experiment import prediction, select_threshold

DATA = Path(__file__).parents[1] / "data/benchmarks/context-v1"


def test_training_split_loader_never_opens_test(tmp_path):
    shutil.copytree(DATA, tmp_path / "data")
    (tmp_path / "data/test.jsonl").unlink()
    splits, _ = load_splits(tmp_path / "data", split_names=("train", "dev"))
    assert set(splits) == {"train", "dev"}
    with pytest.raises(FileNotFoundError):
        load_splits(tmp_path / "data")


def external_rows():
    return [
        {
            "id": f"external-{i}",
            "group": f"external-group-{i}",
            "text": f"독립 검수용 테스트 문장 {i}",
            "label": label,
            "source": "authored test fixture",
            "sourceType": "synthetic",
        }
        for i, label in enumerate(("NORMAL", "PHISHING", "PREVENTION"))
    ]


def test_external_overlap_includes_previously_exposed_test():
    splits, _ = load_splits(DATA)
    reference = reference_hashes([r for rows in splits.values() for r in rows])
    rows = external_rows()
    rows[0]["text"] = splits["test"][0]["text"].replace(" ", "\u200b ")
    with pytest.raises(ValueError, match="overlaps"):
        check_external(rows, reference)
    rows = external_rows()
    rows[0]["group"] = splits["dev"][0]["group"]
    with pytest.raises(ValueError, match="overlaps"):
        check_external(rows, reference)


def test_registration_requires_review_and_preserves_synthetic_label(tmp_path):
    rows = external_rows()
    data, review, output = [tmp_path / n for n in ("data.jsonl", "review.json", "registered.json")]
    data.write_text("\n".join(json.dumps(r) for r in rows))
    note = {
        "reviewer": "reviewer-b",
        "datasetAuthor": "author-a",
        "reviewedOn": date.today().isoformat(),
        "independentReviewAttested": True,
        "approvedRows": {
            r["id"]: {"label": r["label"], "usageBasis": "authored fixture, not real messages"} for r in rows
        },
    }
    review.write_text(json.dumps(note))
    reference = reference_hashes([])
    r = register(data, review, reference, output)
    assert r["synthetic"] is True
    assert load_registered(data, output, reference)[0] == rows
    with pytest.raises(ValueError, match="overwrite"):
        register(data, review, reference, output)
    data.write_text(data.read_text() + "\n")
    with pytest.raises(ValueError, match="hash"):
        load_registered(data, output, reference)


@pytest.mark.parametrize("change", ["reviewer", "approvedRows"])
def test_fabricated_or_incomplete_review_rejected(tmp_path, change):
    rows = external_rows()
    data, review = tmp_path / "rows.jsonl", tmp_path / "review.json"
    data.write_text("\n".join(json.dumps(r) for r in rows))
    note = {
        "reviewer": "different",
        "datasetAuthor": "author",
        "reviewedOn": date.today().isoformat(),
        "independentReviewAttested": True,
        "approvedRows": {r["id"]: {"label": r["label"], "usageBasis": "test fixture"} for r in rows},
    }
    note[change] = "author" if change == "reviewer" else {}
    review.write_text(json.dumps(note))
    with pytest.raises(ValueError):
        register(data, review, reference_hashes([]), tmp_path / "output.json")


def test_threshold_only_uses_dev_and_does_not_hide_abstention():
    rows = [{"label": "PHISHING"}, {"label": "PREVENTION"}]
    probabilities = [[0.1, 0.6, 0.3], [0.2, 0.1, 0.7]]
    threshold, trials = select_threshold(rows, probabilities)
    assert threshold == 0.4
    assert len(trials) == 4
    assert prediction([0.34, 0.33, 0.33], 0.5)["decision"] == "ABSTAIN"
    with pytest.raises(ValueError):
        prediction([float("nan"), 0, 1], 0.5)
