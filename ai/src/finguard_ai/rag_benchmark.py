"""Offline retrieval metrics and explicit human faithfulness review. No LLM calls."""

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from finguard_ai.benchmark_data import digest
from finguard_ai.corpus import load_manifest
from finguard_ai.evidence import hybrid_rank, select_evidence
from finguard_ai.repository import Chunk


def retrieval_metrics(ranked_ids, gold, k):
    if k < 1 or len(ranked_ids) != len(set(ranked_ids)):
        raise ValueError("Invalid k or duplicate retrieval ids")
    if not gold:
        return None  # no relevant document: exclude from recall/MRR denominator
    gold = set(gold)
    found = gold.intersection(ranked_ids[:k])
    first = next((i for i, ident in enumerate(ranked_ids[:k], 1) if ident in gold), None)
    return {
        "recall": len(found) / len(gold),
        "hit": int(bool(found)),
        "allRequired": int(found == gold),
        "reciprocalRank": 1 / first if first else 0,
    }


def load_benchmark(directory, corpus_dir):
    root, corpus_dir = Path(directory), Path(corpus_dir)
    manifest = json.loads((root / "manifest.json").read_text())
    if digest(root / "questions.jsonl") != manifest["questionsSha256"]:
        raise ValueError("Question set checksum changed")
    chunks, seen = [], set()
    for name, expected in manifest["corpusManifests"].items():
        path = (corpus_dir / name).resolve()
        if not path.is_relative_to(corpus_dir.resolve()) or digest(path) != expected:
            raise ValueError("Corpus manifest changed")
        for r, m, text, _ in load_manifest(path):
            if m.corpus_id in seen:
                raise ValueError("Duplicate corpus id")
            seen.add(m.corpus_id)
            ident = len(chunks) + 1
            chunks.append(Chunk(ident, ident, r["title"], text, metadata=m.model_dump(mode="json")))
    rows = [json.loads(line) for line in (root / "questions.jsonl").read_text().splitlines() if line.strip()]
    ids = [r["id"] for r in rows]
    if not rows or len(ids) != len(set(ids)):
        raise ValueError("Empty or duplicate questions")
    for row in rows:
        if (
            not row["question"].strip()
            or not isinstance(row["answerable"], bool)
            or bool(row["relevantCorpusIds"]) != row["answerable"]
            or not set(row["relevantCorpusIds"]).issubset(seen)
        ):
            raise ValueError("Invalid retrieval gold")
    return rows, chunks, manifest


def review_template(rows, chunks, manifest):
    return {
        "benchmark": manifest,
        "instructions": "Supply a real generated answer and modelVersion, segment "
        "ALL factual claims, then independently assess each against cited evidence. "
        "SUPPORTED means the evidence entails that claim, not merely a matching citation. "
        "Use UNSUPPORTED or CONTRADICTED otherwise. Leave pending when not reviewed.",
        "sources": {
            c.metadata["corpus_id"]: {
                "content": c.content,
                "sha256": c.content_hash,
                "url": c.metadata["source_url"],
            }
            for c in chunks
        },
        "answers": [
            {
                "questionId": r["id"],
                "question": r["question"],
                "answer": None,
                "modelVersion": None,
                "reviewer": None,
                "allClaimsReviewed": False,
                "claims": [],
            }
            for r in rows
        ],
    }


def faithfulness(review, rows, chunks, manifest):
    if review.get("benchmark") != manifest:
        raise ValueError("Review belongs to another benchmark")
    questions = {r["id"] for r in rows}
    sources = {c.metadata["corpus_id"]: c for c in chunks}
    seen, evaluated = set(), []
    for answer in review["answers"]:
        ident = answer["questionId"]
        if ident not in questions or ident in seen:
            raise ValueError("Unknown/duplicate answer id")
        seen.add(ident)
        if not isinstance(answer.get("allClaimsReviewed"), bool):
            raise ValueError("Review status must be boolean")
        if not answer["allClaimsReviewed"]:
            continue
        if not all(
            isinstance(answer.get(k), str) and answer[k].strip()
            for k in ("answer", "reviewer", "modelVersion")
        ) or not answer.get("claims"):
            raise ValueError("Final review requires answer/model/reviewer and explicit factual claims")
        for claim in answer["claims"]:
            if (
                claim.get("verdict") not in {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED"}
                or not claim.get("text")
                or claim["text"] not in answer["answer"]
                or not claim.get("rationale", "").strip()
            ):
                raise ValueError("Invalid claim review")
            citations = claim.get("citations", [])
            if claim["verdict"] in {"SUPPORTED", "CONTRADICTED"} and not citations:
                raise ValueError("Evidence required for entailment/contradiction judgment")
            for citation in citations:
                source = sources.get(citation.get("corpusId"))
                if (
                    source is None
                    or citation.get("sha256") != source.content_hash
                    or not citation.get("quote")
                    or citation["quote"] not in source.content
                ):
                    raise ValueError("Citation is missing, stale or not an exact evidence quote")
            evaluated.append(claim)
    reviewed_answers = sum(a.get("allClaimsReviewed") is True for a in review["answers"])
    supported = sum(c["verdict"] == "SUPPORTED" for c in evaluated)
    return {
        "method": "human-labelled claim entailment; not automatic string-match faithfulness",
        "reviewedAnswers": reviewed_answers,
        "pendingQuestions": len(questions) - reviewed_answers,
        "reviewedClaims": len(evaluated),
        "supportedClaims": supported,
        "unsupportedClaims": sum(c["verdict"] == "UNSUPPORTED" for c in evaluated),
        "contradictedClaims": sum(c["verdict"] == "CONTRADICTED" for c in evaluated),
        "supportRate": supported / len(evaluated) if evaluated else None,
        "answerCorrectness": "not measured; faithfulness alone does not establish completeness or correctness",
    }


def run(directory, corpus_dir, output, *, k=2, review_path=None):
    if k < 1:
        raise ValueError("k must be positive")
    rows, chunks, manifest = load_benchmark(directory, corpus_dir)
    encoder = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), max_features=768)
    x = encoder.fit_transform([c.title + " " + c.content for c in chunks])
    results = []
    for row in rows:
        scores = (x @ encoder.transform([row["question"]]).T).toarray().ravel()
        vectors = sorted(chunks, key=lambda c: (-scores[c.chunk_id - 1], c.chunk_id))
        fusion = sorted(
            hybrid_rank(
                chunks, {c.chunk_id: float(scores[c.chunk_id - 1]) for c in chunks}, row["question"], 0
            ),
            key=lambda c: (-c.score, c.chunk_id),
        )
        policy = select_evidence(row["question"], fusion, limit=k, today=date.fromisoformat(manifest["asOf"]))
        modes = {"vector": vectors[:k], "hybrid": fusion[:k], "policySelection": policy.chunks}
        results.append(
            {
                **row,
                "retrieval": {
                    mode: {
                        "ids": [c.metadata["corpus_id"] for c in ranked],
                        "metrics": retrieval_metrics(
                            [c.metadata["corpus_id"] for c in ranked], row["relevantCorpusIds"], k
                        ),
                    }
                    for mode, ranked in modes.items()
                },
                "policyReason": policy.reason,
                "policyAnswerable": policy.reason is None,
                "answerabilityCorrect": (policy.reason is None) == row["answerable"],
            }
        )
    summaries = {}
    for mode in ("vector", "hybrid", "policySelection"):
        valid = [r["retrieval"][mode]["metrics"] for r in results if r["answerable"]]
        summaries[mode] = {
            "answerableQuestions": len(valid),
            **{
                name: float(np.mean([m[name] for m in valid])) if valid else None
                for name in ("recall", "hit", "allRequired", "reciprocalRank")
            },
        }
    template = review_template(rows, chunks, manifest)
    review = json.loads(Path(review_path).read_text()) if review_path else template
    report = {
        "benchmark": manifest,
        "k": k,
        "paidCalls": 0,
        "encoder": "offline char TF-IDF (2,4), max_features=768; NOT provider embeddings",
        "scope": "6 reviewed summaries, not full PDFs. Policy selection reads all corpus candidates; "
        "it is NOT a reranker limited to vector top-k. All modes use the same gold IDs.",
        "summary": summaries,
        "answerabilityCorrect": sum(r["answerabilityCorrect"] for r in results),
        "questions": len(rows),
        "cases": results,
        "faithfulness": faithfulness(review, rows, chunks, manifest),
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "rag-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    # Never overwrite a reviewer's edits; review input should be a separate copy.
    template_path = output / "faithfulness-review.template.json"
    if not template_path.exists():
        template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--k", type=int, default=2)
    p.add_argument("--review", type=Path)
    a = p.parse_args()
    report = run(a.data, a.corpus, a.output_dir, k=a.k, review_path=a.review)
    print(json.dumps({"retrieval": report["summary"], "faithfulness": report["faithfulness"]}, indent=2))


if __name__ == "__main__":
    main()
