import json
import math
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from finguard_ai.errors import ServiceUnavailable
from finguard_ai.privacy import mask
from finguard_ai.schemas import ClassificationResult


class LocalClassifier:
    """Safe JSON weights; no untrusted pickle/joblib deserialization."""

    def __init__(self, path: Path, allow_demo: bool = False):
        self.artifact = json.loads(path.read_text(encoding="utf-8"))
        a = self.artifact
        if a["formatVersion"] != 1 or a["labels"] != ["NORMAL", "PHISHING"]:
            raise ValueError("Unsupported classifier format")
        if a.get("synthetic") and not allow_demo:
            raise ValueError("Synthetic demo artifact is disabled")
        self.version = a["modelVersion"]
        if not isinstance(self.version, str) or not 1 <= len(self.version) <= 100:
            raise ValueError("Invalid model version")
        self.low, self.high = a["thresholds"]["pass"], a["thresholds"]["flag"]
        if not 0 <= self.low < self.high <= 1:
            raise ValueError("Invalid abstention thresholds")
        self.vectorizer = TfidfVectorizer(
            analyzer="char", ngram_range=(2, 5), vocabulary=a["vocabulary"], sublinear_tf=True
        )
        self.vectorizer.idf_ = np.asarray(a["idf"], dtype=float)
        self.weights = np.asarray(a["weights"], dtype=float)
        self.intercept = float(a["intercept"])
        if len(self.weights) != len(a["vocabulary"]) or len(a["idf"]) != len(self.weights):
            raise ValueError("Invalid classifier dimensions")
        if (
            not np.isfinite(self.weights).all()
            or not np.isfinite(self.vectorizer.idf_).all()
            or not math.isfinite(self.intercept)
        ):
            raise ValueError("Non-finite classifier artifact")

    def score(self, text: str) -> float | None:
        vector = self.vectorizer.transform([mask(text)])
        if vector.nnz == 0:
            return None
        logit = float(np.asarray(vector @ self.weights).item()) + self.intercept
        return 1 / (1 + math.exp(-max(-700, min(700, logit))))

    def classify(self, text: str) -> ClassificationResult:
        score = self.score(text)
        if score is None or self.low < score < self.high:
            label, decision = None, "ABSTAIN"
        elif score >= self.high:
            label, decision = "PHISHING", "FLAG"
        else:
            label, decision = "NORMAL", "PASS"
        return ClassificationResult(label=label, decision=decision, modelVersion=self.version)


class MissingClassifier:
    def classify(self, text: str) -> ClassificationResult:
        raise ServiceUnavailable("CLASSIFIER_NOT_READY")
