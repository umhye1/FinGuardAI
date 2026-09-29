"""Experimental three-intent linear model, NOT a pretrained language model.

Character and word n-grams learn local phrases/negation from labelled examples.
Safe JSON serialization avoids executable pickle artifacts. Not auto-promoted to serving.
"""

import json
from pathlib import Path

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from finguard_ai.benchmark_data import LABELS
from finguard_ai.privacy import mask


class ContextModel:
    def __init__(self, encoders, weights, intercept, threshold, version):
        self.encoders = encoders
        self.weights = np.asarray(weights, dtype=float)
        self.intercept = np.asarray(intercept, dtype=float)
        self.threshold, self.version = threshold, version
        size = sum(len(e.vocabulary_) for e in encoders)
        if (
            self.weights.shape != (3, size)
            or self.intercept.shape != (3,)
            or not np.isfinite(self.weights).all()
            or not np.isfinite(self.intercept).all()
            or not 1 / 3 <= threshold <= 1
        ):
            raise ValueError("Invalid context model parameters")

    def probabilities(self, texts):
        texts = [mask(t) for t in texts]
        x = hstack([e.transform(texts) for e in self.encoders]).tocsr()
        logits = np.asarray(x @ self.weights.T) + self.intercept
        scores = np.exp(logits - logits.max(axis=1, keepdims=True))
        scores /= scores.sum(axis=1, keepdims=True)
        # Uniform/OOV must never become a deterministic NORMAL decision by argmax tie-breaking.
        return [None if x[i].nnz == 0 else p for i, p in enumerate(scores)]

    def predict(self, text):
        scores = self.probabilities([text])[0]
        if scores is None:
            return {"label": None, "decision": "ABSTAIN", "probabilities": None}
        label = LABELS[int(np.argmax(scores))]
        decision = "ABSTAIN" if max(scores) < self.threshold else "FLAG" if label == "PHISHING" else "PASS"
        return {"label": label, "decision": decision, "probabilities": dict(zip(LABELS, map(float, scores)))}

    def save(self, path, provenance):
        encoders = []
        for e in self.encoders:
            encoders.append(
                {
                    "analyzer": e.analyzer,
                    "ngramRange": list(e.ngram_range),
                    "vocabulary": {k: int(v) for k, v in e.vocabulary_.items()},
                    "idf": e.idf_.tolist(),
                }
            )
        artifact = {
            "formatVersion": "intent-linear-v1",
            "modelVersion": self.version,
            "labels": list(LABELS),
            "threshold": self.threshold,
            "encoders": encoders,
            "weights": self.weights.tolist(),
            "intercept": self.intercept.tolist(),
            "synthetic": True,
            "provenance": provenance,
        }
        Path(path).write_text(json.dumps(artifact, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path, *, allow_synthetic=False):
        a = json.loads(Path(path).read_text())
        if a["formatVersion"] != "intent-linear-v1" or a["labels"] != list(LABELS):
            raise ValueError("Unsupported intent artifact")
        if a.get("synthetic") and not allow_synthetic:
            raise ValueError("Synthetic model requires explicit opt-in")
        encoders = []
        for spec in a["encoders"]:
            if (spec["analyzer"], tuple(spec["ngramRange"])) not in {("char", (2, 5)), ("word", (1, 2))}:
                raise ValueError("Unsupported encoder")
            e = TfidfVectorizer(
                analyzer=spec["analyzer"],
                ngram_range=tuple(spec["ngramRange"]),
                sublinear_tf=True,
                vocabulary=spec["vocabulary"],
            )
            e.idf_ = np.asarray(spec["idf"], dtype=float)
            if not np.isfinite(e.idf_).all() or len(e.idf_) != len(spec["vocabulary"]):
                raise ValueError("Invalid encoder weights")
            encoders.append(e)
        if not encoders or len(encoders) > 2:
            raise ValueError("Invalid encoder count")
        return cls(encoders, a["weights"], a["intercept"], a["threshold"], a["modelVersion"])


def fit(rows, *, words=True, c=1.0, threshold=0.5):
    if {r["label"] for r in rows} != set(LABELS):
        raise ValueError("All three intent labels required")
    encoders = [TfidfVectorizer(analyzer="char", ngram_range=(2, 5), sublinear_tf=True, max_features=100000)]
    if words:
        encoders.append(
            TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, max_features=50000)
        )
    texts = [mask(r["text"]) for r in rows]
    x = hstack([e.fit_transform(texts) for e in encoders]).tocsr()
    model = LogisticRegression(C=c, class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(x, [r["label"] for r in rows])
    if tuple(model.classes_) != LABELS:
        raise ValueError("Unexpected class order")
    return ContextModel(encoders, model.coef_, model.intercept_, threshold, "intent-linear-v1")
