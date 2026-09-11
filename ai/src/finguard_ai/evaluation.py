"""Reproducible source-grounded retrieval comparison, NOT a Gemini quality benchmark."""

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer

from finguard_ai.corpus import load_manifest
from finguard_ai.evidence import POLICY_VERSION, hybrid_rank, select_evidence
from finguard_ai.repository import Chunk

QUESTIONS = [
    ("transfer", "사기범에게 돈을 송금했어요. 지급정지하려면?", {"transfer-response"}),
    ("smishing", "문자 링크와 악성앱이 의심돼요", {"smishing-response"}),
    ("mobile", "휴대폰 소액결제 피해를 취소하려면?", {"mobile-payment-response"}),
    ("combined", "스미싱 문자를 받고 계좌로 이체했어요", {"smishing-response", "transfer-response"}),
    ("paraphrase", "돈을 보냈는데 사기 같아요", {"transfer-response"}),
    ("case", "카드 배송 사칭 문자를 받았어요", {"smishing-response"}),
    ("ambiguous", "피해를 봤어요 어떻게 하죠", set()),
    ("out_of_scope", "해외 투자 세금 환급 절차", set()),
]


def evaluate(manifest, as_of):
    records = list(load_manifest(manifest))
    chunks = [
        Chunk(i, i, r["title"], text, metadata=m.model_dump(mode="json"))
        for i, (r, m, text, _) in enumerate(records, 1)
    ]
    encoder = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), max_features=768)
    matrix = encoder.fit_transform([c.title + " " + c.content for c in chunks])
    results = []
    for ident, question, expected in QUESTIONS:
        scores = (matrix @ encoder.transform([question]).T).toarray().ravel()
        baseline = sorted(chunks, key=lambda c: (-scores[c.chunk_id - 1], c.chunk_id))[:2]
        rows = hybrid_rank(chunks, {c.chunk_id: float(scores[c.chunk_id - 1]) for c in chunks}, question, 0)
        result = select_evidence(question, rows, limit=2, today=as_of)
        actual = {c.metadata["family"] for c in result.chunks}
        results.append(
            {
                "id": ident,
                "question": question,
                "baseline_ids": [c.metadata["corpus_id"] for c in baseline],
                "baseline_required_covered": expected.issubset({c.metadata["family"] for c in baseline})
                if expected
                else None,
                "status": "INSUFFICIENT_EVIDENCE" if result.reason else "ANSWERABLE",
                "reason": result.reason,
                "policy_correct": expected.issubset(actual) and result.reason is None
                if expected
                else result.reason == "NEEDS_CLARIFICATION",
                "selected": [
                    {
                        "corpus_id": c.metadata["corpus_id"],
                        "source_url": c.metadata["source_url"],
                        "version": c.metadata["version"],
                        "content_sha256": c.content_hash,
                    }
                    for c in result.chunks
                ],
            }
        )
    return {
        "as_of": as_of.isoformat(),
        "policy_version": POLICY_VERSION,
        "manifest_sha256": hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        "embedding": "offline character TF-IDF cosine, max 768 features; NOT Gemini embeddings",
        "baseline": "same local vector encoder, top-2 without policy",
        "generation": "not executed; selected citation sources compared, no answer correctness claim",
        "official_source_pages": len({c.metadata["source_url"] for c in chunks}),
        "corpus_records": len(chunks),
        "cases": results,
        "policy_correct": sum(r["policy_correct"] for r in results),
        "sample_count": len(results),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = evaluate(a.manifest, a.as_of)
    Path(a.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Policy checks: {result['policy_correct']}/{result['sample_count']}; no live LLM evaluation")


if __name__ == "__main__":
    main()
