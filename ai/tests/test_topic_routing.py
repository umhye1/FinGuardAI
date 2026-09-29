import json
from datetime import date
from pathlib import Path

import pytest
from test_evidence import corpus
from test_rag import Repository, service

from finguard_ai.evidence import select_evidence, topics_for
from finguard_ai.schemas import GeneratedAnswer

DATA = Path(__file__).parents[1] / "data/regression/topic-routing-v2.jsonl"
ROWS = [json.loads(line) for line in DATA.read_text().splitlines()]


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_topic_intent_contrasts(row):
    assert topics_for(row["question"]) == set(row["expectedTopics"])


@pytest.mark.parametrize(
    "question,family",
    [
        ("지인이 보낸 모바일 청첩장이 수상해요.", "smishing-response"),
        ("통신사 청구서에 모르는 콘텐츠 비용이 있어요.", "mobile-payment-response"),
    ],
)
def test_correct_family_selected_without_unrelated_transfer(question, family):
    decision = select_evidence(question, corpus(), today=date(2026, 9, 29))
    assert decision.reason is None
    assert {c.metadata["family"] for c in decision.chunks} == {family}


def test_combined_invitation_and_money_requires_both_families():
    question = "수상한 청첩장을 열고 돈을 보냈어요."
    rows = corpus()
    assert select_evidence(question, rows[:1], today=date(2026, 9, 29)).reason == "MISSING_REQUIRED_DOCUMENT"
    result = select_evidence(question, rows, today=date(2026, 9, 29))
    assert result.reason is None
    assert {"smishing-response", "transfer-response"} <= {c.metadata["family"] for c in result.chunks}


def test_rag_routes_candidates_and_validates_generated_citations():
    repository = Repository()
    repository.chunks = corpus()[2:3]
    calls = []

    def candidates(topics, *args):
        calls.append(topics)
        return repository.chunks

    repository.policy_candidates = candidates
    rag, provider = service(
        repository, GeneratedAnswer(status="ANSWERED", answer="테스트 답변", chunkIds=[3])
    )
    result = rag.answer("통신사 청구서에 모르는 콘텐츠 비용이 있어요.")
    assert result.status == "ANSWERED"
    assert calls == [{"mobile_payment"}, {"mobile_payment"}]
    assert provider.last_payload["evidence"][0]["chunk_id"] == 3


def test_rag_ordinary_delivery_does_not_call_provider():
    rag, provider = service(
        Repository(), GeneratedAnswer(status="ANSWERED", answer="사용되지 않음", chunkIds=[1])
    )
    assert rag.answer("서류를 보냈어요.").reasonCode == "NEEDS_CLARIFICATION"
    assert provider.last_payload is None
