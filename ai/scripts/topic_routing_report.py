"""Report synthetic routing regressions without providers or a database (run from ai/)."""

import argparse
import hashlib
import json
from pathlib import Path

from finguard_ai.evidence import POLICY_VERSION, topics_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / "data/regression/topic-routing-v2.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    cases = [
        {
            **r,
            "actualTopics": sorted(topics_for(r["question"])),
            "correct": set(r["expectedTopics"]) == topics_for(r["question"]),
        }
        for r in rows
    ]
    report = {
        "policyVersion": POLICY_VERSION,
        "fixtureSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "scope": "synthetic regression cases authored from observed failures; not independent generalization evaluation",
        "paidCalls": 0,
        "correct": sum(c["correct"] for c in cases),
        "count": len(cases),
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Routing regressions: {report['correct']}/{report['count']}; no provider calls")


if __name__ == "__main__":
    main()
