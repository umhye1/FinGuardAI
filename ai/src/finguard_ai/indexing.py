"""Content-addressed incremental embeddings, durable batches and atomic activation."""
import argparse
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass

from finguard_ai.config import load_settings
from finguard_ai.errors import StaleDocument
from finguard_ai.provider import create_provider
from finguard_ai.repository import CorpusRepository, make_pool


@dataclass(frozen=True)
class EmbeddingProfile:
    provider: str
    model: str
    revision: str = "unversioned"
    processing_version: str = "chunker-v1-raw-utf8"
    dimensions: int = 768
    task: str = "RETRIEVAL_DOCUMENT"
    implementation: str = "mask-v1-l2norm-v1"

    @property
    def key(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    @classmethod
    def from_settings(cls, settings):
        return cls(settings.provider, settings.embedding_model, settings.embedding_revision,
                   settings.embedding_processing_version, settings.embedding_dimensions)


def validate_vectors(vectors, count, dimensions):
    if len(vectors) != count:
        raise ValueError("Embedding batch count mismatch")
    for vector in vectors:
        if len(vector) != dimensions or any(
            type(x) not in (int, float) or not math.isfinite(x) for x in vector
        ) or not any(vector):
            raise ValueError("Invalid embedding vector")


def index_document(repository, provider, document_id: int, profile: EmbeddingProfile,
                   *, force=False, dry_run=False) -> dict:
    started = time.monotonic()
    if profile.dimensions != 768 or profile.task != "RETRIEVAL_DOCUMENT":
        raise ValueError("Unsupported embedding profile")
    if provider is not None and hasattr(provider, "settings"):
        if EmbeddingProfile.from_settings(provider.settings) != profile:
            raise ValueError("Provider settings do not match embedding profile")
    chunks = repository.document_chunks(document_id)
    if not chunks:
        raise StaleDocument("Document has no completed chunks")
    if len(chunks) > 2000:
        raise ValueError("Document exceeds 2000 chunks; split it before indexing")
    # Preserve original order, deduplicate identical content only in incremental mode.
    unique = {c.content_hash: c for c in chunks}
    cached = {} if force else repository.cached_embeddings(document_id, profile.key, list(unique))
    validate_vectors(list(cached.values()), len(cached), profile.dimensions)
    pending = chunks if force else [c for h, c in unique.items() if h not in cached]
    result = {
        "documentId": document_id, "chunkCount": len(chunks), "embeddingModel": profile.model,
        "profile": asdict(profile), "profileHash": profile.key,
        "mode": "full" if force else "incremental", "dryRun": dry_run,
        "cachedChunks": sum(c.content_hash in cached for c in chunks),
        "deduplicatedChunks": 0 if force else len(chunks)
        - sum(c.content_hash in cached for c in chunks) - len(pending),
        "plannedEmbeddingInputs": len(pending), "plannedProviderCalls": math.ceil(len(pending) / 32),
        "plannedInputCharacters": sum(len(c.content) for c in pending),
        "embeddedInputs": 0, "providerCalls": 0, "inputCharacters": 0,
        "inputTokens": None, "cost": None, "published": False,
    }
    if not dry_run:
        full_vectors = []
        # Finish/cache each valid batch independently. Provider errors never partially publish.
        for offset in range(0, len(pending), 32):
            batch = pending[offset:offset + 32]
            vectors = provider.embed([c.content for c in batch], profile.task)
            validate_vectors(vectors, len(batch), profile.dimensions)
            if force:
                full_vectors.extend(vectors)
            entries = {c.content_hash: v for c, v in zip(batch, vectors)}
            repository.cache_batch(document_id, chunks, profile.key, entries)
            cached.update(entries)
            result["providerCalls"] += 1
            result["embeddedInputs"] += len(batch)
            result["inputCharacters"] += sum(len(c.content) for c in batch)
        # Recheck metadata/body even for a zero-call run; current evidence policy stays at retrieval.
        repository.publish(document_id, chunks,
                           full_vectors if force else [cached[c.content_hash] for c in chunks], profile.model)
        result["published"] = True
    result["elapsedSeconds"] = round(time.monotonic() - started, 6)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Incrementally index a completed document; cache misses call paid embedding API."
    )
    parser.add_argument("--document-id", type=int, required=True)
    parser.add_argument("--env-file", help="Explicit local dotenv file")
    parser.add_argument("--dry-run", action="store_true", help="Read-only plan; no provider calls or DB writes")
    parser.add_argument("--full", action="store_true", help="Bypass cache and embed every chunk")
    args = parser.parse_args()
    if args.document_id <= 0:
        parser.error("document-id must be positive")
    settings = load_settings(args.env_file)
    if not settings.connection_info:
        parser.error("AI_DATABASE_* or AI_DATABASE_URL is required")
    provider = None if args.dry_run else create_provider(settings)
    pool = make_pool(settings.connection_info, settings.pool_max_size)
    try:
        pool.open()
        result = index_document(CorpusRepository(pool), provider, args.document_id,
                                EmbeddingProfile.from_settings(settings), force=args.full, dry_run=args.dry_run)
        print(json.dumps(result))
    finally:
        pool.close()
        if provider:
            provider.close()


if __name__ == "__main__":
    main()
