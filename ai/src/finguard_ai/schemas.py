from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ClassificationRequest(StrictModel):
    text: str = Field(min_length=1, max_length=10000)


class QuestionRequest(StrictModel):
    question: str = Field(min_length=1, max_length=10000)


class ClassificationResult(StrictModel):
    status: Literal["COMPLETED"] = "COMPLETED"
    label: Literal["PHISHING", "NORMAL"] | None
    decision: Literal["FLAG", "PASS", "ABSTAIN"]
    modelVersion: str = Field(min_length=1, max_length=100)
    errorCode: None = None

    @model_validator(mode="after")
    def consistent_decision(self):
        if self.decision == "FLAG" and self.label != "PHISHING":
            raise ValueError("FLAG must have PHISHING label")
        if self.decision == "PASS" and self.label != "NORMAL":
            raise ValueError("PASS must have NORMAL label")
        return self


class GeneratedClassification(StrictModel):
    label: Literal["PHISHING", "NORMAL"] | None
    decision: Literal["FLAG", "PASS", "ABSTAIN"]


class GeneratedAnswer(StrictModel):
    status: Literal["ANSWERED", "INSUFFICIENT_EVIDENCE"]
    answer: str = Field(default="", max_length=10000)
    chunkIds: list[int] = Field(default_factory=list, max_length=10)


class RagResult(StrictModel):
    status: Literal["ANSWERED", "INSUFFICIENT_EVIDENCE"]
    answer: str | None = None
    chunkIds: list[int] = Field(default_factory=list, max_length=10)
    modelVersion: str | None = None
    promptVersion: str | None = None
