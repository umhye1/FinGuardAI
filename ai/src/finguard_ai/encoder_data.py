"""Data provenance checks; metadata declarations do not replace independent review."""

import hashlib
import json
from datetime import date
from pathlib import Path

from finguard_ai.benchmark_data import LABELS, digest, normalized
from finguard_ai.training import fingerprint


def reference_hashes(rows):
    return {
        "ids": sorted(r["id"] for r in rows),
        "groups": sorted({hashlib.sha256(r["group"].encode()).hexdigest() for r in rows}),
        "texts": sorted({fingerprint(normalized(r["text"])) for r in rows}),
    }


def check_external(rows, reference):
    if not rows or {r.get("label") for r in rows} != set(LABELS):
        raise ValueError("Evaluation requires all three labels")
    ids, texts = set(), set()
    for row in rows:
        for field in ("id", "group", "text", "source", "sourceType"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError("Missing evaluation text/provenance")
        if len(row["text"]) > 10000 or row["sourceType"] not in {"licensed", "consented", "synthetic"}:
            raise ValueError("Invalid evaluation row")
        h = fingerprint(normalized(row["text"]))
        if row["id"] in ids or h in texts:
            raise ValueError("Duplicate evaluation id/text")
        ids.add(row["id"])
        texts.add(h)
    actual = reference_hashes(rows)
    if any(set(actual[k]) & set(reference[k]) for k in ("ids", "groups", "texts")):
        raise ValueError("Evaluation overlaps training/development or previously exposed benchmark")


def validate_review(rows, record):
    if (
        not isinstance(record.get("reviewer"), str)
        or not record["reviewer"].strip()
        or not isinstance(record.get("datasetAuthor"), str)
        or not record["datasetAuthor"].strip()
        or record["reviewer"] == record["datasetAuthor"]
        or record.get("independentReviewAttested") is not True
    ):
        raise ValueError("A separate reviewer and explicit independent review attestation are required")
    reviewed = date.fromisoformat(record["reviewedOn"])
    if reviewed > date.today():
        raise ValueError("Review date cannot be in the future")
    approved = record.get("approvedRows", {})
    if set(approved) != {r["id"] for r in rows}:
        raise ValueError("Every row must have a reviewed label and usage basis")
    for row in rows:
        decision = approved[row["id"]]
        if decision.get("label") != row["label"] or (
            not isinstance(decision.get("usageBasis"), str) or not decision["usageBasis"].strip()
        ):
            raise ValueError("Reviewed label mismatch or missing usage basis")


def register(data, review, reference, output):
    """Require per-row evidence of review, preserving the declaration as unverified provenance."""
    data, output = Path(data), Path(output)
    if output.exists():
        raise ValueError("Refusing to overwrite evaluation registration")
    rows = [json.loads(line) for line in data.read_text().splitlines() if line.strip()]
    check_external(rows, reference)
    record = json.loads(Path(review).read_text())
    validate_review(rows, record)
    result = {
        "version": "external-eval-v1",
        "dataSha256": digest(data),
        "reviewSha256": digest(review),
        "samples": len(rows),
        "sourceTypes": sorted({r["sourceType"] for r in rows}),
        "synthetic": any(r["sourceType"] == "synthetic" for r in rows),
        "review": record,
        "referenceHashes": reference,
        "independence": "reviewer attestation, not independently verified by software; semantic overlap not excluded",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def load_registered(data, registration, reference):
    r = json.loads(Path(registration).read_text())
    if r["version"] != "external-eval-v1" or digest(data) != r["dataSha256"]:
        raise ValueError("Evaluation registration/hash mismatch")
    rows = [json.loads(line) for line in Path(data).read_text().splitlines() if line.strip()]
    validate_review(rows, r["review"])
    check_external(rows, r["referenceHashes"])
    check_external(rows, reference)
    return rows, r
