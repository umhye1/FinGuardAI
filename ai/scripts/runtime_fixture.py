"""Synthetic conflict/missing-document fixture; refuses non-test databases."""

import json
import os
from urllib.parse import urlparse

import psycopg

url = os.environ["TEST_DATABASE_URL"]
if urlparse(url).path != "/finguard_ai_test":
    raise ValueError("Only dedicated test DB allowed")
with psycopg.connect(url) as conn:
    conn.execute(
        "UPDATE documents SET status='FAILED' WHERE evidence_metadata::jsonb->>'family'='mobile-payment-response'"
    )
    row = conn.execute(
        "SELECT document_id,evidence_metadata FROM documents WHERE evidence_metadata::jsonb->>'family'='integrated-reporting'"
    ).fetchone()
    if not row:
        raise ValueError("Import official manifest first")
    m = json.loads(row[1])
    m["claims"][0]["value"] = "SYNTHETIC_CONFLICT_NOT_OFFICIAL"
    conn.execute(
        "UPDATE documents SET evidence_metadata=%s WHERE document_id=%s",
        (json.dumps(m, ensure_ascii=False), row[0]),
    )
print("Synthetic fixture prepared in test DB only")
