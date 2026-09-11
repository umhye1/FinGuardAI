from copy import deepcopy
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from finguard_ai.corpus import load_manifest
from finguard_ai.evidence import hybrid_rank, select_evidence
from finguard_ai.repository import Chunk

TODAY = date(2026, 9, 11)


def corpus():
    return [
        Chunk(i, i, r["title"], content, metadata=m.model_dump(mode="json"))
        for i, (r, m, content, _) in enumerate(
            load_manifest(Path(__file__).parents[1] / "data/official/manifest.json"), 1
        )
    ]


def decide(q, rows):
    return select_evidence(q, rows, today=TODAY)


def test_real_source_requirements_and_separate_case():
    result = decide("스미싱 문자로 돈을 송금했어요", corpus())
    assert result.reason is None
    assert {"transfer-response", "smishing-response"} <= {c.metadata["family"] for c in result.chunks}
    assert all(c.metadata["kind"] == "OFFICIAL_GUIDANCE" for c in result.chunks)


def test_low_rank_cross_institution_conflict_stops_before_top_k():
    rows = corpus()
    m = deepcopy(rows[0].metadata)
    m["publisher"] = "한국인터넷진흥원"
    m["claims"][0]["value"] = "SYNTHETIC_CONFLICT_NOT_OFFICIAL"
    rows.append(replace(rows[0], chunk_id=99, score=-1, metadata=m))
    assert decide("송금 피해", rows).reason == "CONFLICTING_EVIDENCE"


def test_only_same_publisher_family_supersedes_old_version():
    row = corpus()[0]
    m = deepcopy(row.metadata)
    m["published_at"] = "2020-01-01"
    m["claims"][0]["value"] = "SYNTHETIC_OLD"
    old = replace(row, chunk_id=99, metadata=m)
    assert [c.chunk_id for c in decide("송금 피해", [old, row]).chunks] == [row.chunk_id]


def test_same_date_conflict_is_not_arbitrarily_resolved():
    row = corpus()[0]
    m = deepcopy(row.metadata)
    m["claims"][0]["value"] = "SYNTHETIC_SAME_DATE"
    assert decide("송금 피해", [row, replace(row, chunk_id=90, metadata=m)]).reason == "CONFLICTING_EVIDENCE"


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "CASE"},
        {"review_due": "2026-09-10"},
        {"published_at": "2027-01-01"},
        {"content_sha256": "0" * 64},
        {"source_url": "https://example.com/fake"},
    ],
)
def test_unusable_guidance_cannot_satisfy_required_document(change):
    row = corpus()[0]
    assert (
        decide("송금 피해", [replace(row, metadata=row.metadata | change)]).reason
        == "MISSING_REQUIRED_DOCUMENT"
    )


def test_ambiguous_question_asks_instead_of_inventing_target():
    result = decide("어떻게 해야 하나요", corpus())
    assert result.reason == "NEEDS_CLARIFICATION"
    assert result.clarification


def test_mobile_payment_does_not_use_transfer_as_required_evidence():
    result = decide("휴대폰 소액결제 피해", corpus())
    assert result.reason is None
    assert {c.metadata["family"] for c in result.chunks} == {"mobile-payment-response"}


def test_lexical_rescues_vector_miss_and_vector_rescues_lexical_miss():
    rows = [
        Chunk(1, 1, "a", "소액결제"),
        Chunk(2, 2, "b", "semantic synonym"),
        Chunk(3, 3, "c", "irrelevant"),
    ]
    ranked = hybrid_rank(rows, {2: 0.95}, "소액결제", 0.6)
    assert ranked[0].score > 0 and ranked[1].score > 0 and ranked[2].score == 0


def test_excessive_corpus_fails_closed():
    assert decide("송금", [corpus()[0]] * 201).reason == "CORPUS_LIMIT"


def test_expired_current_edition_does_not_fall_back_to_old_edition():
    row = corpus()[0]
    old = replace(row, chunk_id=99, metadata=row.metadata | {"published_at": "2020-01-01"})
    expired = replace(row, metadata=row.metadata | {"review_due": "2026-09-10"})
    assert decide("송금", [old, expired]).reason == "MISSING_REQUIRED_DOCUMENT"


def test_unannotated_official_procedure_is_not_silently_trusted():
    row = corpus()[0]
    assert (
        decide("송금", [replace(row, metadata=row.metadata | {"claims": []})]).reason
        == "UNREVIEWED_PROCEDURE"
    )
