"""Versioned, intent-labelled splits. No random row splitting or provider calls."""

import hashlib
import json
import unicodedata
from pathlib import Path

LABELS = ("NORMAL", "PHISHING", "PREVENTION")


def normalized(text):
    return "".join(
        c
        for c in unicodedata.normalize("NFKC", text).casefold()
        if not c.isspace() and unicodedata.category(c) != "Cf"
    )


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_splits(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    seen_ids, seen_texts, group_splits = set(), set(), {}
    splits = {}
    for split in ("train", "dev", "test"):
        path = directory / f"{split}.jsonl"
        if digest(path) != manifest["sha256"][split]:
            raise ValueError("Dataset checksum changed; create a reviewed benchmark version")
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if {r.get("label") for r in rows} != set(LABELS):
            raise ValueError("Every split must contain all three labels")
        for row in rows:
            if any(
                not isinstance(row.get(k), str) or not row[k].strip()
                for k in ("id", "group", "text", "source", "sourceType")
            ):
                raise ValueError("Missing dataset provenance or text")
            if row["sourceType"] not in {"synthetic", "licensed", "consented"}:
                raise ValueError("Unknown provenance")
            text = normalized(row["text"])
            if not text or len(row["text"]) > 10000:
                raise ValueError("Invalid text length")
            if row["id"] in seen_ids or text in seen_texts:
                raise ValueError("Duplicate id/text across or within splits")
            if group_splits.setdefault(row["group"], split) != split:
                raise ValueError("Group leakage between splits")
            seen_ids.add(row["id"])
            seen_texts.add(text)
        splits[split] = rows
    return splits, manifest
