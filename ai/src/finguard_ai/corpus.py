"""Validate and import reviewed source summaries without a paid API call."""

import argparse
import hashlib
import json
from pathlib import Path

from finguard_ai.config import Settings
from finguard_ai.evidence import EvidenceMetadata
from finguard_ai.repository import make_pool


def load_manifest(path):
    path = Path(path).resolve()
    records = json.loads(path.read_text())
    seen = set()
    for record in records:
        m = EvidenceMetadata.model_validate(record["metadata"])
        file = (path.parent / record["file"]).resolve()
        if not file.is_relative_to(path.parent) or m.corpus_id in seen:
            raise ValueError("Duplicate corpus ID or unsafe file path")
        content = file.read_text().strip()
        if (
            not content
            or len(content) > 4000
            or hashlib.sha256(content.encode()).hexdigest() != m.content_sha256
        ):
            raise ValueError("Unreviewed or oversized content")
        seen.add(m.corpus_id)
        yield record, m, content, file


def import_corpus(pool, records):
    ids = []
    with pool.connection() as conn:
        # One transaction; serialize repeat/concurrent imports and reject edited versions.
        conn.execute("SELECT pg_advisory_xact_lock(71412026)")
        for record, m, content, file in records:
            metadata = m.model_dump(mode="json")
            existing = conn.execute(
                "SELECT document_id, evidence_metadata, status FROM documents "
                "WHERE evidence_metadata::jsonb->>'corpus_id' = %s FOR UPDATE",
                (m.corpus_id,),
            ).fetchone()
            if existing:
                if json.loads(existing["evidence_metadata"]) != metadata:
                    raise ValueError("Existing corpus ID differs; publish a new version/ID")
                stored = conn.execute(
                    "SELECT content FROM document_chunks WHERE document_id = %s ORDER BY chunk_index",
                    (existing["document_id"],),
                ).fetchall()
                if existing["status"] != "COMPLETED" or [r["content"] for r in stored] != [content]:
                    raise ValueError("Existing corpus content changed; review a new version")
                ids.append(existing["document_id"])
                continue
            doc = conn.execute(
                """INSERT INTO documents
                (title, source, source_url, file_path, status, created_at, original_file_name,
                 stored_file_name, chunk_count, evidence_metadata)
                VALUES (%s, %s, %s, %s, 'COMPLETED', now(), %s, %s, 1, %s) RETURNING document_id""",
                (
                    record["title"],
                    m.publisher,
                    m.source_url,
                    str(file),
                    file.name,
                    file.name,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            ).fetchone()["document_id"]
            conn.execute(
                "INSERT INTO document_chunks(document_id, chunk_index, content, created_at) "
                "VALUES (%s, 0, %s, now())",
                (doc, content),
            )
            ids.append(doc)
    return ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument(
        "--apply", action="store_true", help="Write to configured DB; otherwise validate only"
    )
    args = parser.parse_args()
    records = list(load_manifest(args.manifest))
    if not args.apply:
        print(json.dumps({"validated": len(records), "write": False}))
        return
    settings = Settings()
    if not settings.connection_info:
        raise ValueError("AI_DATABASE_* required")
    with make_pool(settings.connection_info) as pool:
        print(json.dumps({"documentIds": import_corpus(pool, records)}))


if __name__ == "__main__":
    main()
