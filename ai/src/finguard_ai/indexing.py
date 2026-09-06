import argparse
import json

from finguard_ai.config import Settings
from finguard_ai.errors import StaleDocument
from finguard_ai.provider import GeminiProvider
from finguard_ai.repository import CorpusRepository, make_pool


def index_document(repository, provider, document_id: int, model: str) -> int:
    chunks = repository.document_chunks(document_id)
    if not chunks:
        raise StaleDocument("Document has no completed chunks")
    if len(chunks) > 2000:
        raise ValueError("Document exceeds 2000 chunks; split it before indexing")
    vectors = []
    for offset in range(0, len(chunks), 32):
        vectors.extend(
            provider.embed([c.content for c in chunks[offset : offset + 32]], "RETRIEVAL_DOCUMENT")
        )
    repository.publish(document_id, chunks, vectors, model)
    return len(chunks)


def main():
    parser = argparse.ArgumentParser(
        description="Index an already uploaded/completed document; calls paid embedding API."
    )
    parser.add_argument("--document-id", type=int, required=True)
    args = parser.parse_args()
    if args.document_id <= 0:
        parser.error("document-id must be positive")
    settings = Settings()
    if not settings.connection_info:
        parser.error("AI_DATABASE_URL is required")
    provider = GeminiProvider(settings)
    pool = make_pool(settings.connection_info, settings.pool_max_size)
    try:
        pool.open()
        count = index_document(CorpusRepository(pool), provider, args.document_id, settings.embedding_model)
        print(
            json.dumps(
                {
                    "documentId": args.document_id,
                    "chunkCount": count,
                    "embeddingModel": settings.embedding_model,
                }
            )
        )
    finally:
        pool.close()
        provider.close()
