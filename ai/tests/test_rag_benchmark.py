from copy import deepcopy
from pathlib import Path

import pytest

from finguard_ai.rag_benchmark import faithfulness, load_benchmark, retrieval_metrics, review_template, run

ROOT = Path(__file__).parents[1] / "data"


def test_multidocument_recall_and_rank_are_not_any_hit():
    result = retrieval_metrics(["distractor", "a", "b"], ["a", "b"], 2)
    assert result == {"recall": 0.5, "hit": 1, "allRequired": 0, "reciprocalRank": 0.5}
    assert retrieval_metrics(["a"], [], 2) is None


def test_pending_review_is_not_perfect_faithfulness():
    rows, chunks, manifest = load_benchmark(ROOT / "benchmarks/rag-v1", ROOT / "official")
    result = faithfulness(review_template(rows, chunks, manifest), rows, chunks, manifest)
    assert result["reviewedClaims"] == 0
    assert result["supportRate"] is None
    assert result["pendingQuestions"] == 20


def reviewed_fixture():
    rows, chunks, manifest = load_benchmark(ROOT / "benchmarks/rag-v1", ROOT / "official")
    review = review_template(rows, chunks, manifest)
    # Deliberately fabricated answer for evaluator test, never report as an actual LLM run.
    claim = "돈이 무조건 내일 돌아옵니다."
    review["answers"][0].update(
        answer=claim,
        modelVersion="test-fixture-no-llm",
        reviewer="test-reviewer",
        allClaimsReviewed=True,
        claims=[
            {
                "text": claim,
                "verdict": "UNSUPPORTED",
                "rationale": "Citation contains no guarantee of next-day reimbursement.",
                "citations": [
                    {
                        "corpusId": chunks[0].metadata["corpus_id"],
                        "sha256": chunks[0].content_hash,
                        "quote": chunks[0].content,
                    }
                ],
            }
        ],
    )
    return review, rows, chunks, manifest


def test_valid_citation_does_not_imply_supported_answer():
    review, rows, chunks, manifest = reviewed_fixture()
    result = faithfulness(review, rows, chunks, manifest)
    assert result["supportRate"] == 0
    assert result["unsupportedClaims"] == 1


@pytest.mark.parametrize("change", ["sha256", "quote", "corpusId"])
def test_invalid_evidence_rejected(change):
    review, rows, chunks, manifest = reviewed_fixture()
    review["answers"][0]["claims"][0]["citations"][0][change] = "not-in-corpus"
    with pytest.raises(ValueError, match="Citation"):
        faithfulness(review, rows, chunks, manifest)


def test_unknown_or_duplicate_answer_cannot_inflate_denominator():
    review, rows, chunks, manifest = reviewed_fixture()
    review["answers"].append(deepcopy(review["answers"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        faithfulness(review, rows, chunks, manifest)


def test_offline_rag_report_preserves_unmeasured_generation(tmp_path):
    report = run(ROOT / "benchmarks/rag-v1", ROOT / "official", tmp_path)
    assert report["paidCalls"] == 0
    assert report["summary"]["vector"]["answerableQuestions"] == 15
    assert report["faithfulness"]["supportRate"] is None
    assert len(report["cases"]) == 20
