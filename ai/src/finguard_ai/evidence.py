"""Conservative policy over reviewed, structured guidance; not universal NLI."""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, model_validator

from finguard_ai.schemas import StrictModel

POLICY_VERSION = "evidence-policy-v3"
RULES = {
    "transfer": {
        "terms": ["송금", "이체", "입금", "지급정지"],
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
    # A query intent, not a new reviewed metadata topic. The existing reporting
    # family is reviewed under transfer; never mutate its metadata in memory/DB.
    "reporting": {
        "terms": ["보이스피싱", "금융사기", "통합신고", "신고", "접수"],
        "families": {"integrated-reporting"},
    },
}
CLARIFICATION = "계좌 송금, 의심 문자·앱, 휴대폰 소액결제, 보이스피싱 신고 안내 중 어떤 상황인가요? 질문을 조금 더 구체적으로 알려주세요."


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
            "www.krcert.or.kr",
            "spam.kisa.or.kr",
        }:
            raise ValueError("Unapproved source host")
        if self.published_at > self.collected_at or self.reviewed_on > self.review_due:
            raise ValueError("Invalid evidence dates")
        if any(c.topic not in self.topics for c in self.claims):
            raise ValueError("Claim outside reviewed topic")
        return self


def normalized_question(question):
    return "".join(
        c for c in unicodedata.normalize("NFKC", question).lower() if unicodedata.category(c) != "Cf"
    )


def topics_for(question):
    """Bounded lexical routing for evidence retrieval, not fraud or entailment classification.

    Ambiguous sending requires an adjacent money object. Context combinations never
    cross sentence boundaries. Explicit transfer/payment words retain prior behavior.
    """
    question = normalized_question(question)
    compact = re.sub(r"\s+", "", question)
    topics = {
        topic
        for topic, rule in RULES.items()
        if topic != "reporting" and any(re.sub(r"\s+", "", term) in compact for term in rule["terms"])
    }
    for sentence in re.split(r"[.!?。！？;\n]+", question):
        sentence_compact = re.sub(r"\s+", "", sentence)
        # Bare 신고/112/통합신고센터 does not identify the financial-scam domain.
        # Keep this sentence-local so tax/loss reporting in another sentence
        # cannot acquire a financial-scam purpose from a preceding sentence.
        if re.search(r"보이스피싱|금융사기", sentence_compact) and re.search(
            r"신고|접수", sentence_compact
        ) and not re.search(r"(?:세금|소득세|부가세|분실|주차|혼인|출생)(?:을|를|의)?(?:신고|접수)", sentence_compact):
            topics.add("reporting")
        if re.search(
            r"(?:돈|금액|현금|보증금|수수료|대금)(?:을|를)?\s*"
            r"(?:(?:먼저|이미|전부|모두|바로|즉시|다)\s*){0,2}(?:보내|보낸|보냈)",
            sentence,
        ):
            topics.add("transfer")
        if re.search(r"청첩장|초대장|부고장", sentence) and re.search(
            r"수상|의심|사칭|열어도|눌러도|설치|악성|피싱", sentence
        ):
            topics.add("smishing")
        if (
            re.search(r"통신사|통신요금|휴대폰|휴대전화|핸드폰", sentence)
            and re.search(r"청구|요금|과금", sentence)
            and re.search(r"콘텐츠|컨텐츠|소액|결제", sentence)
        ):
            topics.add("mobile_payment")
    return topics


def terms_for(question):
    return sorted(
        set(re.findall(r"[가-힣a-z0-9]{2,}", question.lower()))
        | {term for t in topics_for(question) for term in RULES[t]["terms"]}
    )[:60]


def fingerprint(metadata):
    return hashlib.sha256(json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def relevant_metadata(metadata, intents):
    return bool((intents - {"reporting"}).intersection(metadata.get("topics", []))) or (
        "reporting" in intents and metadata.get("family") == "integrated-reporting"
    )


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
    # Claims retain their reviewed topic; routing intent is deliberately separate.
    claim_topics = (topics - {"reporting"}) | ({"transfer"} if "reporting" in topics else set())
    eligible = []
    for chunk in chunks:
        try:
            m = EvidenceMetadata.model_validate(chunk.metadata)
        except ValueError:
            # A malformed newer record must not make an older procedure look current.
            if chunk.metadata.get("kind") == "OFFICIAL_GUIDANCE" and relevant_metadata(chunk.metadata, topics):
                return Decision([], "MISSING_REQUIRED_DOCUMENT")
            continue
        if m.kind != "OFFICIAL_GUIDANCE" or not relevant_metadata(chunk.metadata, topics) or m.published_at > today:
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
        not set(m.topics).intersection(claim_topics).issubset({claim.topic for claim in m.claims})
        or ("reporting" in topics and m.family == "integrated-reporting"
            and not any(claim.topic == "transfer" and claim.key == "report_channel" for claim in m.claims))
        for _, m in active
    ):
        return Decision([], "UNREVIEWED_PROCEDURE")
    claims = {}
    for _, m in active:
        for claim in m.claims:
            if claim.topic in claim_topics:
                claims.setdefault((m.applicability, claim.topic, claim.key), set()).add(claim.value)
    if any(len(values) > 1 for values in claims.values()):
        return Decision([], "CONFLICTING_EVIDENCE")
    required = set.union(*(RULES[t]["families"] for t in topics))
    if not required.issubset({m.family for _, m in active}):
        return Decision([], "MISSING_REQUIRED_DOCUMENT")
    if any(not any(claim.topic == topic for _, m in active for claim in m.claims) for topic in claim_topics):
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
