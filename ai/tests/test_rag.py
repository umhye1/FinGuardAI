import pytest
from test_evidence import corpus

from finguard_ai.config import Settings
from finguard_ai.errors import ServiceUnavailable, StaleDocument
from finguard_ai.indexing import index_document
from finguard_ai.rag import RagService
from finguard_ai.schemas import GeneratedAnswer


class Repository:
    def __init__(self):
        self.chunks = [corpus()[0]]
        self.stale = False
        self.published = None

    def has_embeddings(self, model):
        return bool(self.chunks)

    def policy_candidates(self, *args):
        return [] if self.stale else self.chunks

    def search(self, *args):
        return self.chunks

    def document_chunks(self, doc_id):
        return [] if self.stale else self.chunks

    def publish(self, *args):
        self.published = args


class Provider:
    def __init__(self, result):
        self.result = result
        self.last_payload = None

    def embed(self, texts, task):
        return [[1.0] + [0.0] * 767 for _ in texts]

    def generate(self, system, payload, schema):
        self.last_payload = payload
        return self.result


def service(repo, result):
    provider = Provider(result)
    return RagService(
        repo, provider, Settings(service_token="s" * 32, generation_model="test-model")
    ), provider


def test_retrieved_citations_are_required():
    rag, _ = service(Repository(), GeneratedAnswer(status="ANSWERED", answer="답변", chunkIds=[999]))
    with pytest.raises(ServiceUnavailable, match="UNGROUNDED"):
        rag.answer("송금 피해 질문")


def test_valid_answer_has_model_and_prompt_provenance():
    rag, provider = service(Repository(), GeneratedAnswer(status="ANSWERED", answer="답변", chunkIds=[1]))
    result = rag.answer("010-1234-5678 송금 질문")
    assert result.chunkIds == [1]
    assert result.promptVersion == "rag-grounded-v2"
    assert "010-1234-5678" not in str(provider.last_payload)


def test_document_removed_after_generation_abstains():
    repository = Repository()
    rag, provider = service(repository, GeneratedAnswer(status="ANSWERED", answer="답변", chunkIds=[1]))
    original = provider.generate

    def generate(*args):
        repository.stale = True
        return original(*args)

    provider.generate = generate
    assert rag.answer("송금 피해 질문").status == "INSUFFICIENT_EVIDENCE"


def test_empty_corpus_and_missing_document_do_not_generate():
    repository = Repository()
    repository.chunks = []
    rag, provider = service(repository, GeneratedAnswer(status="ANSWERED", answer="답변", chunkIds=[1]))
    assert rag.answer("송금 피해 질문").status == "INSUFFICIENT_EVIDENCE"
    assert provider.last_payload is None
    with pytest.raises(StaleDocument):
        index_document(repository, provider, 10, "test-model")


def test_indexing_passes_snapshot_and_vectors_to_atomic_publish():
    repository = Repository()
    provider = Provider(None)
    assert index_document(repository, provider, 10, "embedding-model") == 1
    assert repository.published[0] == 10
    assert repository.published[3] == "embedding-model"


def test_conflict_never_calls_generation():
    from copy import deepcopy
    from dataclasses import replace

    repository = Repository()
    m = deepcopy(repository.chunks[0].metadata)
    m["publisher"] = "different institution"
    m["claims"][0]["value"] = "synthetic-conflict"
    repository.chunks.append(replace(repository.chunks[0], chunk_id=99, metadata=m))
    rag, provider = service(repository, GeneratedAnswer(status="ANSWERED", answer="unsafe", chunkIds=[1]))
    assert rag.answer("송금 피해").reasonCode == "CONFLICTING_EVIDENCE"
    assert provider.last_payload is None


def test_missing_required_citation_is_rejected_even_if_id_is_real():
    repository = Repository()
    repository.chunks = corpus()[:2]
    rag, _ = service(repository, GeneratedAnswer(status="ANSWERED", answer="incomplete", chunkIds=[1]))
    assert rag.answer("스미싱 송금 피해").reasonCode == "MISSING_REQUIRED_CITATION"


def test_new_conflict_inserted_during_generation_abstains():
    from copy import deepcopy
    from dataclasses import replace

    repository = Repository()
    rag, provider = service(repository, GeneratedAnswer(status="ANSWERED", answer="answer", chunkIds=[1]))
    original = provider.generate

    def generate(*args):
        m = deepcopy(repository.chunks[0].metadata)
        m["publisher"] = "another institution"
        m["claims"][0]["value"] = "synthetic-conflict"
        repository.chunks.append(replace(repository.chunks[0], chunk_id=99, metadata=m))
        return original(*args)

    provider.generate = generate
    assert rag.answer("송금 피해").reasonCode == "CORPUS_CHANGED"
