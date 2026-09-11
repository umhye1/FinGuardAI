"""Conservative policy over reviewed, structured guidance; not universal NLI."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, model_validator

from finguard_ai.schemas import StrictModel

POLICY_VERSION = "evidence-policy-v1"
RULES = {
    "transfer": {
        "terms": ["송금", "이체", "보낸", "보냈", "입금", "지급정지"],
        "families": {"transfer-response"},
    },
    "smishing": {
        "terms": ["스미싱", "문자", "링크", "악성", "앱", "카드 배송"],
        "families": {"smishing-response"},
    },
    "mobile_payment": {
        "terms": ["소액결제", "휴대폰 결제", "모바일 결제", "통신요금"],
        "families": {"mobile-payment-response"},
    },
}
CLARIFICATION = "계좌 송금, 의심 문자·앱, 휴대폰 소액결제 중 어떤 상황인가요? 피해 상황을 함께 알려주세요."


class Claim(StrictModel):
    topic: Literal["transfer", "smishing", "mobile_payment"]
    key: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=200)


class EvidenceMetadata(StrictModel):
    corpus_id: str = Field(min_length=1, max_length=120)
    kind: Literal["OFFICIAL_GUIDANCE", "CASE"]
    publisher: str = Field(min_length=1, max_length=100)
    source_url: str = Field(max_length=2000)
    published_at: date
    collected_at: date
    reviewed_on: date
    review_due: date
    applicability: Literal["KR_CONSUMER"]
    version: str = Field(min_length=1, max_length=100)
    family: str = Field(min_length=1, max_length=100)
    topics: list[Literal["transfer", "smishing", "mobile_payment"]] = Field(min_length=1, max_length=3)
    claims: list[Claim] = Field(default_factory=list, max_length=30)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    representation: Literal["SOURCE_SUMMARY", "ORIGINAL_EXCERPT"]

    @model_validator(mode="after")
    def valid_source(self):
        u = urlparse(self.source_url)
        if u.scheme != "https" or u.hostname not in {
            "www.fsc.go.kr",
            "www.fss.or.kr",
            "www.kisa.or.kr",
            "www.kisa.kr",
            "spam.kisa.or.kr",
        }:
            raise ValueError("Unapproved source host")
        if self.published_at > self.collected_at or self.reviewed_on > self.review_due:
            raise ValueError("Invalid evidence dates")
        if any(c.topic not in self.topics for c in self.claims):
            raise ValueError("Claim outside reviewed topic")
        return self


def topics_for(question):
    return {topic for topic, rule in RULES.items() if any(term in question.lower() for term in rule["terms"])}


def terms_for(question):
    return sorted(
        set(re.findall(r"[가-힣a-z0-9]{2,}", question.lower()))
        | {term for t in topics_for(question) for term in RULES[t]["terms"]}
    )[:60]


def fingerprint(metadata):
    return hashlib.sha256(json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@dataclass
class Decision:
    chunks: list
    reason: str | None = None
    clarification: str | None = None


def select_evidence(question, chunks, limit=5, today=None):
    today = today or date.today()
    topics = topics_for(question)
    if not topics:
        return Decision([], "NEEDS_CLARIFICATION", CLARIFICATION)
    if len(chunks) > 200:
        return Decision([], "CORPUS_LIMIT")
    eligible = []
    for chunk in chunks:
        try:
            m = EvidenceMetadata.model_validate(chunk.metadata)
        except ValueError:
            # A malformed newer record must not make an older procedure look current.
            if chunk.metadata.get("kind") == "OFFICIAL_GUIDANCE" and topics.intersection(
                chunk.metadata.get("topics", [])
            ):
                return Decision([], "MISSING_REQUIRED_DOCUMENT")
            continue
        if m.kind != "OFFICIAL_GUIDANCE" or not topics.intersection(m.topics) or m.published_at > today:
            continue
        eligible.append((chunk, m))
    # A newer publication supersedes only the same publisher/family/applicability.
    # Different institutions are never silently overruled by date.
    latest = {}
    for _, m in eligible:
        key = (m.publisher, m.family, m.applicability)
        latest[key] = max(latest.get(key, date.min), m.published_at)
    active = [(c, m) for c, m in eligible if m.published_at == latest[m.publisher, m.family, m.applicability]]
    # Never fall back to an older edition when the current one is expired or changed.
    if any(
        m.content_sha256 != c.content_hash or m.reviewed_on > today or m.review_due < today for c, m in active
    ):
        return Decision([], "MISSING_REQUIRED_DOCUMENT")
    if any(
        not set(m.topics).intersection(topics).issubset({claim.topic for claim in m.claims})
        for _, m in active
    ):
        return Decision([], "UNREVIEWED_PROCEDURE")
    claims = {}
    for _, m in active:
        for claim in m.claims:
            if claim.topic in topics:
                claims.setdefault((m.applicability, claim.topic, claim.key), set()).add(claim.value)
    if any(len(values) > 1 for values in claims.values()):
        return Decision([], "CONFLICTING_EVIDENCE")
    required = set.union(*(RULES[t]["families"] for t in topics))
    if not required.issubset({m.family for _, m in active}):
        return Decision([], "MISSING_REQUIRED_DOCUMENT")
    if any(not any(claim.topic == topic for _, m in active for claim in m.claims) for topic in topics):
        return Decision([], "UNREVIEWED_PROCEDURE")
    # Reserve a slot per required family, then fill by reciprocal rank fusion.
    ordered = sorted(
        active, key=lambda pair: (-pair[0].score, -pair[1].published_at.toordinal(), pair[0].chunk_id)
    )
    selected = []
    for family in sorted(required):
        selected.append(next(c for c, m in ordered if m.family == family))
    for c, _ in ordered:
        if c not in selected and len(selected) < limit:
            selected.append(c)
    if len(selected) > limit:
        return Decision([], "MISSING_REQUIRED_DOCUMENT")
    return Decision(selected)


def hybrid_rank(chunks, vector_scores, question, min_score=0.6):
    """RRF of cosine and Korean substring lexical ranks, retaining policy candidates."""
    from dataclasses import replace

    terms = terms_for(question)
    lexical = {c.chunk_id: sum(term in (c.title + " " + c.content).lower() for term in terms) for c in chunks}
    vectors = sorted(
        (c for c in chunks if vector_scores.get(c.chunk_id, -2) >= min_score),
        key=lambda c: (-vector_scores[c.chunk_id], c.chunk_id),
    )
    words = sorted(
        (c for c in chunks if lexical[c.chunk_id]), key=lambda c: (-lexical[c.chunk_id], c.chunk_id)
    )
    scores = {}
    for ranked in (vectors, words):
        for rank, c in enumerate(ranked, 1):
            scores[c.chunk_id] = scores.get(c.chunk_id, 0) + 1 / (60 + rank)
    return [replace(c, score=scores.get(c.chunk_id, 0)) for c in chunks]
