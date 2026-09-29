"""Offline controlled comparison. No environment keys, network, DB, or paid inference."""

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np
import sklearn
from sklearn.metrics import confusion_matrix

from finguard_ai.benchmark_data import LABELS, load_splits, normalized
from finguard_ai.classification import LocalClassifier
from finguard_ai.context_model import fit
from finguard_ai.training import check_holdout, train

# Frozen snapshot of the 14-keyword local runtime, not a query of mutable user data.
KEYWORDS = {
    "검찰청": 25,
    "계좌번호": 30,
    "본인인증": 15,
    "링크": 20,
    "주민등록번호": 20,
    "원격제어": 30,
    "앱설치": 20,
    "택배": 10,
    "배송조회": 10,
    "교통법규위반": 15,
    "특별경품": 10,
    "저금리대출": 15,
    "계좌이체": 20,
    "보증료": 10,
}


def ratio(n, d):
    return {"count": int(n), "denominator": int(d), "rate": float(n / d) if d else None}


def metrics(rows, predictions):
    if not rows or len(rows) != len(predictions):
        raise ValueError("Nonempty aligned rows/predictions required")
    pairs = list(zip(rows, predictions))
    phishing = sum(r["label"] == "PHISHING" for r in rows)
    prevention = sum(r["label"] == "PREVENTION" for r in rows)
    normal = sum(r["label"] == "NORMAL" for r in rows)
    return {
        "phishingNotFlagged": ratio(
            sum(r["label"] == "PHISHING" and p["decision"] != "FLAG" for r, p in pairs), phishing
        ),
        "phishingPassed": ratio(
            sum(r["label"] == "PHISHING" and p["decision"] == "PASS" for r, p in pairs), phishing
        ),
        "preventionFlagged": ratio(
            sum(r["label"] == "PREVENTION" and p["decision"] == "FLAG" for r, p in pairs), prevention
        ),
        "normalFlagged": ratio(
            sum(r["label"] == "NORMAL" and p["decision"] == "FLAG" for r, p in pairs), normal
        ),
        "abstention": ratio(sum(p["decision"] == "ABSTAIN" for p in predictions), len(rows)),
        "coverage": ratio(sum(p["decision"] != "ABSTAIN" for p in predictions), len(rows)),
        "forcedPhishingMiss": ratio(
            sum(r["label"] == "PHISHING" and p["label"] != "PHISHING" for r, p in pairs), phishing
        ),
        "forcedPreventionFalsePositive": ratio(
            sum(r["label"] == "PREVENTION" and p["label"] == "PHISHING" for r, p in pairs), prevention
        ),
    }


def dev_cost(rows, predictions):
    # Frozen before test: explicit cost tradeoff, not calibrated business loss.
    m = metrics(rows, predictions)
    return (
        5 * m["phishingPassed"]["count"]
        + 2 * m["preventionFlagged"]["count"]
        + m["normalFlagged"]["count"]
        + 0.25 * m["abstention"]["count"]
    )


def select_candidate(train_rows, dev_rows, words):
    trials = []
    best = None
    for c in (0.5, 2.0, 8.0):
        model = fit(train_rows, words=words, c=c)
        for threshold in (0.4, 0.5, 0.6):
            model.threshold = threshold
            cost = dev_cost(dev_rows, [model.predict(r["text"]) for r in dev_rows])
            trials.append({"c": c, "threshold": threshold, "devCost": cost})
            key = (cost, c, threshold)
            if best is None or key < best[0]:
                best = (key, c, threshold)
    _, c, threshold = best
    return fit(train_rows, words=words, c=c, threshold=threshold), trials


def rule_predict(text):
    score = min(100, sum(weight for word, weight in KEYWORDS.items() if normalized(word) in normalized(text)))
    # Evaluation-only mapping: production serves 8 ordinal levels, not binary labels.
    flagged = score >= 40  # SUSPICIOUS and above
    return {
        "label": "PHISHING" if flagged else "NORMAL",
        "decision": "FLAG" if flagged else "PASS",
        "ruleScore": score,
    }


def measure(rows, predict, three_class=False):
    predict("모델 준비를 위한 첫 호출")  # one unmeasured warmup
    outputs, times = [], []
    for row in rows:
        start = time.perf_counter()
        outputs.append(predict(row["text"]))
        times.append((time.perf_counter() - start) * 1000)
    result = {
        "metrics": metrics(rows, outputs),
        "latencyMs": {
            "p50": float(np.percentile(times, 50)),
            "p95": float(np.percentile(times, 95)),
            "note": "one local CPU inference per row; excludes training/startup/network",
        },
        "cases": [{"id": r["id"], "expected": r["label"], **p} for r, p in zip(rows, outputs)],
    }
    if three_class:
        result["confusionLabels"] = [*LABELS, "OOV"]
        result["forcedConfusionMatrix"] = confusion_matrix(
            [r["label"] for r in rows], [p["label"] or "OOV" for p in outputs], labels=[*LABELS, "OOV"]
        ).tolist()
    return result


def run(data, output, allow_synthetic=False):
    splits, manifest = load_splits(data)
    if not allow_synthetic:
        raise ValueError("Use --allow-synthetic; these results are not real-world accuracy")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    binary_rows = [
        {**r, "label": "PHISHING" if r["label"] == "PHISHING" else "NORMAL"} for r in splits["train"]
    ]
    artifact = train(binary_rows, "binary-controlled-v1", 0.25, 0.75, True)
    check_holdout(artifact, splits["dev"] + splits["test"])
    path = output / "binary-model.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False))
    binary = LocalClassifier(path, True)

    def binary_predict(text):
        score = binary.score(text)
        return {
            "label": None if score is None else "PHISHING" if score >= 0.5 else "NORMAL",
            "decision": "ABSTAIN"
            if score is None or binary.low < score < binary.high
            else "FLAG"
            if score >= binary.high
            else "PASS",
            "score": score,
        }

    binary_trials = []
    for low, high in ((0.25, 0.75), (0.4, 0.6), (0.45, 0.55), (0.49, 0.51)):
        binary.low, binary.high = low, high
        cost = dev_cost(splits["dev"], [binary_predict(r["text"]) for r in splits["dev"]])
        binary_trials.append({"low": low, "high": high, "devCost": cost})
    selected_binary = min(binary_trials, key=lambda t: (t["devCost"], t["low"]))
    binary.low, binary.high = 0.25, 0.75

    # Fit/select candidates before touching test predictions. No test-driven selection.
    char, char_trials = select_candidate(splits["train"], splits["dev"], False)
    phrase, phrase_trials = select_candidate(splits["train"], splits["dev"], True)
    char.save(output / "intent-char-model.json", manifest)
    phrase.save(output / "intent-phrase-model.json", manifest)
    report = {
        "benchmark": manifest,
        "syntheticOnly": True,
        "paidCalls": 0,
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "trainingRows": len(splits["train"]),
        "devRows": len(splits["dev"]),
        "testRows": len(splits["test"]),
        "comparison": "binary baseline reproduces existing algorithm retrained on same train rows; "
        "not the deployed model artifact. Three-intent candidates are linear n-grams, NOT LLMs.",
        "rules": {
            "keywordSnapshot": KEYWORDS,
            "flagThreshold": 40,
            "mapping": "evaluation-only SUSPICIOUS+; not a probability",
        },
        "selection": {
            "cost": "5*phishingPassed + 2*preventionFlagged + normalFlagged + .25*abstained",
            "binaryTrials": binary_trials,
            "binarySelected": selected_binary,
            "charTrials": char_trials,
            "phraseTrials": phrase_trials,
            "charThreshold": char.threshold,
            "phraseThreshold": phrase.threshold,
        },
        "models": {
            "rule_snapshot": measure(splits["test"], rule_predict),
            "binary_current_algorithm": measure(splits["test"], binary_predict),
            "intent_char_ablation": measure(splits["test"], char.predict, True),
            "intent_char_word_candidate": measure(splits["test"], phrase.predict, True),
        },
    }
    binary.low, binary.high = selected_binary["low"], selected_binary["high"]
    report["models"]["binary_threshold_control"] = measure(splits["test"], binary_predict)
    (output / "classification-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args()
    result = run(args.data, args.output_dir, args.allow_synthetic)
    print(json.dumps({k: v["metrics"] for k, v in result["models"].items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
