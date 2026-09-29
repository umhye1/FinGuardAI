"""Frozen synthetic routing + required evidence regressions; no provider, key or DB."""

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from finguard_ai.corpus import load_manifest
from finguard_ai.evidence import POLICY_VERSION, select_evidence, topics_for
from finguard_ai.repository import Chunk


def report():
    root = Path(__file__).resolve().parents[1]
    fixture = root / "data/regression/reporting-intent-v3.jsonl"
    manifest = root / "data/official/manifest.json"
    chunks = [
        Chunk(i, i, r["title"], content, metadata=m.model_dump(mode="json"))
        for i, (r, m, content, _) in enumerate(load_manifest(manifest), 1)
    ]
    cases = []
    for line in fixture.read_text().splitlines():
        row = json.loads(line)
        topics = topics_for(row["question"])
        decision = select_evidence(row["question"], chunks, today=date(2026, 9, 29))
        families = {c.metadata["family"] for c in decision.chunks}
        expected_reason = None if row["expectedTopics"] else "NEEDS_CLARIFICATION"
        # Additional relevant guidance is allowed, but all required families must be present.
        correct = (
            topics == set(row["expectedTopics"])
            and decision.reason == expected_reason
            and set(row["expectedFamilies"]) <= families
        )
        cases.append(
            {
                **row,
                "actualTopics": sorted(topics),
                "selectedFamilies": sorted(families),
                "reason": decision.reason,
                "correct": correct,
            }
        )
    return {
        "policyVersion": POLICY_VERSION,
        "asOf": "2026-09-29",
        "fixtureSha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "manifestSha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "scope": "repository-authored synthetic regression; not independent generalization or answer quality",
        "paidCalls": 0,
        "correct": sum(c["correct"] for c in cases),
        "count": len(cases),
        "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite a previous report")
    result = report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Reporting regressions: {result['correct']}/{result['count']}; paid calls: 0")
