import json
from copy import deepcopy
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from test_evidence import corpus
from test_rag import Repository, service

from finguard_ai.evidence import select_evidence, topics_for
from finguard_ai.schemas import GeneratedAnswer

QUESTION = "보이스피싱 통합신고 센터가 무엇인가요?"
TODAY = date(2026, 9, 29)
ROWS = [
    json.loads(line)
    for line in (Path(__file__).parents[1] / "data/regression/reporting-intent-v3.jsonl")
    .read_text()
    .splitlines()
]


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_reporting_intent_and_required_families(row):
    assert topics_for(row["question"]) == set(row["expectedTopics"])
    result = select_evidence(row["question"], corpus(), today=TODAY)
    assert result.reason == (None if row["expectedTopics"] else "NEEDS_CLARIFICATION")
    assert set(row["expectedFamilies"]) <= {c.metadata["family"] for c in result.chunks}


def test_reporting_only_selects_reporting_family_without_relabelling_reviewed_metadata():
    rows = corpus()
    original = deepcopy(rows)
    decision = select_evidence(QUESTION, rows, today=TODAY)
    assert [c.metadata["family"] for c in decision.chunks] == ["integrated-reporting"]
    assert decision.chunks[0].metadata["topics"] == ["transfer"]
    assert rows == original


@pytest.mark.parametrize(
    "change",
    [
        {"review_due": "2026-09-28"},
        {"content_sha256": "0" * 64},
        {"kind": "CASE"},
        {"source_url": "https://example.com/fake"},
        {"claims": []},
    ],
)
def test_unusable_reporting_guidance_abstains_before_generation(change):
    repo = Repository()
    row = corpus()[3]
    repo.chunks = [replace(row, metadata=row.metadata | change)]
    rag, provider = service(repo, GeneratedAnswer(status="ANSWERED", answer="test", chunkIds=[4]))
    assert rag.answer(QUESTION).status == "INSUFFICIENT_EVIDENCE"
    assert provider.last_payload is None


def test_transfer_guidance_cannot_replace_missing_reporting_guidance():
    assert select_evidence(QUESTION, corpus()[:1], today=TODAY).reason == "MISSING_REQUIRED_DOCUMENT"


def test_expired_latest_reporting_does_not_fall_back():
    row = corpus()[3]
    old = replace(row, chunk_id=99, metadata=row.metadata | {"published_at": "2020-01-01"})
    expired = replace(row, metadata=row.metadata | {"review_due": "2026-09-28"})
    assert select_evidence(QUESTION, [old, expired], today=TODAY).reason == "MISSING_REQUIRED_DOCUMENT"


def test_conflicting_reporting_claims_abstain():
    row = corpus()[3]
    metadata = deepcopy(row.metadata)
    metadata["publisher"] = "other reviewed publisher"
    metadata["claims"][0]["value"] = "SYNTHETIC_CONFLICT"
    assert (
        select_evidence(QUESTION, [row, replace(row, chunk_id=99, metadata=metadata)], today=TODAY).reason
        == "CONFLICTING_EVIDENCE"
    )


def test_combined_question_requires_each_family_even_at_low_limit():
    question = "송금 피해와 보이스피싱 통합신고센터가 궁금해요."
    for rows in (corpus()[:1], corpus()[3:4]):
        assert select_evidence(question, rows, today=TODAY).reason == "MISSING_REQUIRED_DOCUMENT"
    assert select_evidence(question, corpus(), limit=1, today=TODAY).reason == "MISSING_REQUIRED_DOCUMENT"


def test_reporting_rag_validates_citations_and_rechecks_candidates():
    repo = Repository()
    repo.chunks = corpus()
    calls = []

    def candidates(topics, *args):
        calls.append(topics)
        return repo.chunks

    repo.policy_candidates = candidates
    rag, provider = service(repo, GeneratedAnswer(status="ANSWERED", answer="test", chunkIds=[4]))
    result = rag.answer(QUESTION)
    assert result.status == "ANSWERED"
    assert result.policyVersion == "evidence-policy-v3"
    assert calls == [{"reporting"}, {"reporting"}]
    assert [c["chunk_id"] for c in provider.last_payload["evidence"]] == [4]
    assert result.evidenceSnapshots["4"].metadata == corpus()[3].metadata


@pytest.mark.parametrize("ids", [[1], [4]])
def test_combined_answer_must_cite_both_families(ids):
    repo = Repository()
    repo.chunks = corpus()
    rag, _ = service(repo, GeneratedAnswer(status="ANSWERED", answer="test", chunkIds=ids))
    assert rag.answer("송금 피해와 보이스피싱 통합신고센터 안내").reasonCode == "MISSING_REQUIRED_CITATION"


def test_reporting_document_change_during_generation_abstains():
    repo = Repository()
    repo.chunks = corpus()[3:4]
    rag, provider = service(repo, GeneratedAnswer(status="ANSWERED", answer="test", chunkIds=[4]))
    generate = provider.generate

    def changed(*args):
        repo.chunks = [replace(repo.chunks[0], content="changed")]
        return generate(*args)

    provider.generate = changed
    assert rag.answer(QUESTION).reasonCode == "CORPUS_CHANGED"


@pytest.mark.parametrize(
    "question",
    [
        "보이스피싱 예방 교육과 세금 신고 방법이 궁금해요.",
        "금융사기 예방 자료를 읽다가 지갑 분실 신고를 하려 합니다.",
    ],
)
def test_explicit_unrelated_reporting_in_same_sentence_is_not_financial_reporting(question):
    assert topics_for(question) == set()


def test_combined_question_cannot_borrow_reporting_claim_from_transfer_document():
    rows = corpus()
    metadata = deepcopy(rows[3].metadata)
    metadata["claims"][0]["key"] = "some_other_reviewed_item"
    rows[3] = replace(rows[3], metadata=metadata)
    assert (
        select_evidence("송금 피해와 보이스피싱 신고 안내", rows, today=TODAY).reason
        == "UNREVIEWED_PROCEDURE"
    )
