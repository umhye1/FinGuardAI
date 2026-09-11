"""Opt-in, bounded provider evaluation over public source summaries in an isolated DB schema."""

import argparse
import hashlib
import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from finguard_ai.config import Settings
from finguard_ai.corpus import import_corpus, load_manifest
from finguard_ai.errors import ServiceUnavailable
from finguard_ai.evaluation import QUESTIONS
from finguard_ai.indexing import index_document
from finguard_ai.provider import create_provider
from finguard_ai.rag import RagService
from finguard_ai.repository import CorpusRepository


class BudgetProvider:
    def __new__(cls, settings, max_calls, client=None):
        provider = create_provider(settings, client)
        provider.calls = 0
        original = provider._post

        def bounded_post(path, payload):
            if provider.calls >= max_calls:
                raise ServiceUnavailable("EVALUATION_CALL_LIMIT")
            provider.calls += 1
            return original(path, payload)

        provider._post = bounded_post
        return provider


class RecordingRepository(CorpusRepository):
    def __init__(self, pool):
        super().__init__(pool)
        self.retrieval = {}

    def policy_candidates(self, topics, vector, model, question, min_score):
        candidates = super().policy_candidates(topics, vector, model, question, min_score)
        baseline = self.search(vector, model, 5, min_score) if vector else []
        self.retrieval = {
            "vectorBaselineIds": [
                next(
                    (r.metadata["corpus_id"] for r in candidates if r.chunk_id == c.chunk_id), str(c.chunk_id)
                )
                for c in baseline
            ],
            "hybridCandidates": [
                {"chunkId": c.chunk_id, "corpusId": c.metadata["corpus_id"], "score": c.score}
                for c in candidates
            ],
        }
        return candidates


def preflight(settings, manifest, max_cases):
    records = list(load_manifest(manifest))
    missing = []
    key = settings.openai_api_key if settings.provider == "openai" else settings.gemini_api_key
    if not key:
        missing.append("AI_OPENAI_API_KEY" if settings.provider == "openai" else "AI_GEMINI_API_KEY")
    if not settings.generation_model:
        missing.append("AI_GENERATION_MODEL")
    if not settings.connection_info:
        missing.append("AI_DATABASE_URL or AI_DATABASE_HOST")
    return {
        "status": "READY" if not missing else "NOT_RUN",
        "missingSettings": missing,
        "providerCalls": 0,
        "provider": settings.provider,
        "caseCount": min(max_cases, len(QUESTIONS)),
        "corpusRecords": len(records),
        "manifestSha256": hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        "generationModel": settings.generation_model or None,
        "embeddingModel": settings.embedding_model,
        "semanticReviewStatus": "NOT_EVALUATED",
    }


@contextmanager
def evaluation_repository(settings, migrations):
    schema = "live_eval_" + uuid.uuid4().hex
    with psycopg.connect(settings.connection_info, autocommit=True) as admin:
        extension = admin.execute(
            "SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'"
        ).fetchone()
        if not extension or extension[0] != "public":
            raise ServiceUnavailable("PUBLIC_PGVECTOR_REQUIRED")
        migration_files = sorted(Path(migrations).glob("V*__*.sql"))
        if not migration_files:
            raise ServiceUnavailable("MIGRATION_FILES_REQUIRED")
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        pool = None
        try:
            admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
            for path in migration_files:
                admin.execute(path.read_text())
            pool = ConnectionPool(
                settings.connection_info,
                open=True,
                min_size=0,
                max_size=2,
                kwargs={
                    "row_factory": dict_row,
                    "options": f"-c search_path={schema},public -c statement_timeout=5000",
                },
            )
            yield RecordingRepository(pool)
        finally:
            if pool:
                pool.close()
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def run_cases(repository, provider, settings, max_cases):
    results = []
    for ident, question, required in QUESTIONS[:max_cases]:
        repository.retrieval = {}
        started = time.monotonic()
        try:
            answer = RagService(repository, provider, settings).answer(question)
            snapshots = answer.evidenceSnapshots
            families = {c.metadata.get("family") for c in snapshots.values()}
            item = {
                "status": answer.status,
                "answer": answer.answer,
                "reasonCode": answer.reasonCode,
                "citations": {k: v.model_dump(mode="json") for k, v in snapshots.items()},
                "requiredCitationCoverage": len(required & families) / len(required) if required else None,
                "policyVersion": answer.policyVersion,
                "semanticReviewStatus": "PENDING" if answer.status == "ANSWERED" else "NOT_APPLICABLE",
            }
        except (ServiceUnavailable, psycopg.Error):
            # Do not serialize exception text: SDK/DB errors can carry credentials or raw input.
            item = {
                "status": "FAILED",
                "errorCode": "EVALUATION_REQUEST_FAILED",
                "semanticReviewStatus": "NOT_EVALUATED",
            }
        item.update(
            {
                "id": ident,
                "question": question,
                "latencyMs": round((time.monotonic() - started) * 1000),
                "retrieval": repository.retrieval,
            }
        )
        results.append(item)
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--migrations", default="backend/src/main/resources/db/migration")
    p.add_argument("--output", required=True)
    p.add_argument("--env-file", help="Explicit local dotenv path; never committed")
    p.add_argument("--max-cases", type=int, default=8, choices=range(1, 9))
    p.add_argument("--execute", action="store_true", help="Calls external embedding/generation APIs")
    a = p.parse_args()
    # The CLI does not host an HTTP endpoint; a local-only placeholder satisfies Settings.
    settings = Settings(_env_file=a.env_file, service_token="evaluation-local-only-token-00000000")
    report = preflight(settings, a.manifest, a.max_cases)
    report["createdAt"] = datetime.now(timezone.utc).isoformat()
    output = Path(a.output)
    if output.exists():
        p.error("output already exists; use a new filename to preserve previous runs")
    if not a.execute or report["missingSettings"]:
        if not report["missingSettings"]:
            report["status"] = "PREFLIGHT_ONLY"
    else:
        provider = BudgetProvider(settings, max_calls=5 + 2 * a.max_cases)
        try:
            with evaluation_repository(settings, a.migrations) as repo:
                records = list(load_manifest(a.manifest))
                ids = import_corpus(repo.pool, records)
                for doc, (_, m, _, _) in zip(ids, records):
                    if m.kind == "OFFICIAL_GUIDANCE":
                        index_document(repo, provider, doc, settings.embedding_model)
                report["cases"] = run_cases(repo, provider, settings, a.max_cases)
                report["status"] = (
                    "COMPLETED_WITH_FAILURES"
                    if any(c["status"] == "FAILED" for c in report["cases"])
                    else "COMPLETED"
                )
                report["semanticReviewStatus"] = "PENDING"
        except (ServiceUnavailable, psycopg.Error):
            report.update(status="FAILED", errorCode="EVALUATION_SETUP_FAILED")
        finally:
            report["providerCalls"] = provider.calls
            provider.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "providerCalls": report["providerCalls"]}))
    if a.execute and report["status"] not in {"COMPLETED"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
