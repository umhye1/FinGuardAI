import argparse
import hashlib
import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from finguard_ai.classification import LocalClassifier
from finguard_ai.privacy import mask

LABELS = {"NORMAL", "PHISHING"}


def fingerprint(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", "", mask(text)).lower().encode()).hexdigest()


def load_rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("Dataset is empty")
    ids, texts = set(), set()
    for r in rows:
        if (
            r.get("label") not in LABELS
            or not isinstance(r.get("text"), str)
            or not 1 <= len(r["text"].strip()) <= 10000
        ):
            raise ValueError("Invalid text/label")
        if not all(
            isinstance(r.get(k), str) and r[k].strip() for k in ("id", "group", "source", "sourceType")
        ):
            raise ValueError("id/group/source/sourceType are required")
        if r["sourceType"] not in {"synthetic", "licensed", "consented"}:
            raise ValueError("Unknown sourceType")
        h = fingerprint(r["text"])
        if r["id"] in ids or h in texts:
            raise ValueError("Duplicate id or normalized text")
        ids.add(r["id"])
        texts.add(h)
    return rows


def check_holdout(artifact: dict, rows: list[dict]):
    groups = {hashlib.sha256(r["group"].encode()).hexdigest() for r in rows}
    if groups & set(artifact["trainingGroupHashes"]) or {fingerprint(r["text"]) for r in rows} & set(
        artifact["trainingTextHashes"]
    ):
        raise ValueError("Training/evaluation leakage: shared group or normalized text")


def train(rows: list[dict], version: str, low: float, high: float, allow_synthetic: bool) -> dict:
    if {r["label"] for r in rows} != LABELS:
        raise ValueError("Training requires both labels")
    if not 0 <= low < high <= 1 or not 1 <= len(version) <= 100:
        raise ValueError("Invalid thresholds or version")
    synthetic = any(r["sourceType"] == "synthetic" for r in rows)
    if synthetic and not allow_synthetic:
        raise ValueError("Use --allow-synthetic for demo data; never report it as real-world performance")
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 5), sublinear_tf=True, max_features=100000)
    x = vectorizer.fit_transform([mask(r["text"]) for r in rows])
    model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(x, [r["label"] for r in rows])
    return {
        "formatVersion": 1,
        "modelVersion": version,
        "labels": model.classes_.tolist(),
        "vocabulary": {k: int(v) for k, v in vectorizer.vocabulary_.items()},
        "idf": vectorizer.idf_.tolist(),
        "weights": model.coef_[0].tolist(),
        "intercept": float(model.intercept_[0]),
        "thresholds": {"pass": low, "flag": high},
        "synthetic": synthetic,
        "trainingGroupHashes": sorted({hashlib.sha256(r["group"].encode()).hexdigest() for r in rows}),
        "trainingTextHashes": sorted(fingerprint(r["text"]) for r in rows),
        "trainingRows": len(rows),
    }


def evaluate(model: LocalClassifier, rows: list[dict]) -> dict:
    check_holdout(model.artifact, rows)
    results = [model.classify(r["text"]) for r in rows]
    scores = [model.score(r["text"]) for r in rows]
    # 0.5 metrics only cover rows with a non-empty feature vector. OOV remains explicit.
    scored = [(row, score) for row, score in zip(rows, scores) if score is not None]
    y = [row["label"] for row, _ in scored]
    predictions = ["PHISHING" if score >= 0.5 else "NORMAL" for _, score in scored]
    if scored:
        precision, recall, f1, _ = precision_recall_fscore_support(
            y, predictions, labels=["NORMAL", "PHISHING"], zero_division=0
        )
        counts = confusion_matrix(y, predictions, labels=["NORMAL", "PHISHING"]).tolist()
        metrics = {
            "confusionMatrixAt05": counts,
            "precisionAt05": precision.tolist(),
            "recallAt05": recall.tolist(),
            "f1At05": f1.tolist(),
        }
    else:
        metrics = {
            "confusionMatrixAt05": [[0, 0], [0, 0]],
            "precisionAt05": None,
            "recallAt05": None,
            "f1At05": None,
        }
    fn_safe = sum(r["label"] == "PHISHING" and p.decision == "PASS" for r, p in zip(rows, results))
    return {
        "modelVersion": model.version,
        "samples": len(rows),
        "synthetic": any(r["sourceType"] == "synthetic" for r in rows),
        "labels": ["NORMAL", "PHISHING"],
        **metrics,
        "scoredSamplesAt05": len(scored),
        "outOfVocabulary": len(rows) - len(scored),
        "abstained": sum(p.decision == "ABSTAIN" for p in results),
        "phishingPassed": fn_safe,
        "normalFlagged": sum(r["label"] == "NORMAL" and p.decision == "FLAG" for r, p in zip(rows, results)),
        "coverage": sum(p.decision != "ABSTAIN" for p in results) / len(rows),
        "datasetSha256": hashlib.sha256(
            json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest(),
    }


def train_main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--pass-threshold", type=float, default=0.25)
    p.add_argument("--flag-threshold", type=float, default=0.75)
    p.add_argument("--allow-synthetic", action="store_true")
    a = p.parse_args()
    artifact = train(load_rows(a.data), a.version, a.pass_threshold, a.flag_threshold, a.allow_synthetic)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "modelVersion": a.version,
                "trainingRows": artifact["trainingRows"],
                "synthetic": artifact["synthetic"],
            }
        )
    )


def evaluate_main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--allow-synthetic", action="store_true")
    a = p.parse_args()
    result = evaluate(LocalClassifier(a.model, a.allow_synthetic), load_rows(a.data))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
