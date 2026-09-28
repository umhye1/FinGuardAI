import hashlib
import json
import shutil
from pathlib import Path

import pytest

from finguard_ai.benchmark_data import load_splits

DATA = Path(__file__).parents[1] / "data/benchmarks/context-v1"


def test_locked_splits():
    splits, _ = load_splits(DATA)
    assert [len(splits[s]) for s in ("train", "dev", "test")] == [36, 18, 30]


@pytest.mark.parametrize("mutation,error", [("group", "Group leakage"), ("text", "Duplicate"),
                                          ("checksum", "checksum")])
def test_contaminated_splits_rejected(tmp_path, mutation, error):
    shutil.copytree(DATA, tmp_path / "data")
    root = tmp_path / "data"
    train = json.loads((root / "train.jsonl").read_text().splitlines()[0])
    path = root / "test.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["group" if mutation == "group" else "text"] = (
        train["group"] if mutation == "group" else train["text"].replace(" ", "\u200b ")
    )
    path.write_text("\n".join(json.dumps(r) for r in rows))
    if mutation != "checksum":
        manifest = json.loads((root / "manifest.json").read_text())
        manifest["sha256"]["test"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=error):
        load_splits(root)
