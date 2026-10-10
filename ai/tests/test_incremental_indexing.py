import copy
from dataclasses import replace

import pytest

from finguard_ai.errors import StaleDocument
from finguard_ai.indexing import EmbeddingProfile, index_document
from finguard_ai.repository import Chunk

PROFILE = EmbeddingProfile('offline-test', 'synthetic-model')
VECTOR = [1.0] + [0.0] * 767


class MemoryRepository:
    def __init__(self, count=40):
        self.chunks = [Chunk(i + 1, 1, 'synthetic', f'합성 청크 {i}') for i in range(count)]
        self.cache = {}
        self.active = None
        self.writes = 0

    def document_chunks(self, document_id):
        return copy.deepcopy(self.chunks)

    def cached_embeddings(self, document_id, profile, hashes):
        return {h: v for (p, h), v in self.cache.items() if p == profile and h in hashes}

    def cache_batch(self, document_id, snapshot, profile, entries):
        if snapshot != self.chunks:
            raise StaleDocument('changed')
        self.cache.update({(profile, h): v for h, v in entries.items()})
        self.writes += 1

    def publish(self, document_id, snapshot, vectors, model):
        if snapshot != self.chunks:
            raise StaleDocument('changed')
        self.active = (snapshot, vectors, model)
        self.writes += 1


class OfflineProvider:
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def embed(self, texts, task):
        self.calls.append(list(texts))
        if len(self.calls) == self.fail_at:
            raise RuntimeError('synthetic provider failure')
        return [VECTOR[:] for _ in texts]


def test_unchanged_and_recreated_chunk_ids_reuse_without_provider_calls():
    repo = MemoryRepository()
    index_document(repo, OfflineProvider(), 1, PROFILE)
    repo.chunks = [replace(c, chunk_id=c.chunk_id + 100) for c in repo.chunks]
    provider = OfflineProvider()
    result = index_document(repo, provider, 1, PROFILE)
    assert result['cachedChunks'] == 40
    assert result['providerCalls'] == 0
    assert provider.calls == []
    assert repo.active[0] == repo.chunks


def test_changed_and_duplicate_content_only_embed_unique_misses():
    repo = MemoryRepository(4)
    index_document(repo, OfflineProvider(), 1, PROFILE)
    repo.chunks[0] = replace(repo.chunks[0], content='새 합성 본문')
    repo.chunks[1] = replace(repo.chunks[1], content='새 합성 본문')
    provider = OfflineProvider()
    result = index_document(repo, provider, 1, PROFILE)
    assert result['cachedChunks'] == 2
    assert result['deduplicatedChunks'] == 1
    assert result['embeddedInputs'] == 1
    assert provider.calls == [['새 합성 본문']]


@pytest.mark.parametrize('field,value', [('provider', 'another'), ('model', 'next-model'),
                                        ('revision', 'v2'), ('processing_version', 'chunker-v2'),
                                        ('implementation', 'mask-v2')])
def test_profile_changes_do_not_reuse(field, value):
    repo = MemoryRepository(2)
    index_document(repo, OfflineProvider(), 1, PROFILE)
    result = index_document(repo, OfflineProvider(), 1, replace(PROFILE, **{field: value}))
    assert result['cachedChunks'] == 0
    assert result['embeddedInputs'] == 2


def test_dry_run_is_read_only_and_full_bypasses_cache():
    repo = MemoryRepository()
    index_document(repo, OfflineProvider(), 1, PROFILE)
    before = copy.deepcopy((repo.cache, repo.active, repo.writes))
    provider = OfflineProvider(fail_at=1)
    result = index_document(repo, provider, 1, PROFILE, force=True, dry_run=True)
    assert result['plannedProviderCalls'] == 2
    assert result['plannedEmbeddingInputs'] == 40
    assert not result['published']
    assert provider.calls == []
    assert before == (repo.cache, repo.active, repo.writes)
    result = index_document(repo, OfflineProvider(), 1, PROFILE, force=True)
    assert result['embeddedInputs'] == 40
    assert result['providerCalls'] == 2


def test_failed_second_batch_preserves_active_and_retry_uses_first_batch():
    repo = MemoryRepository(65)
    index_document(repo, OfflineProvider(), 1, PROFILE)
    before = copy.deepcopy(repo.active)
    new_profile = replace(PROFILE, revision='v2')
    with pytest.raises(RuntimeError, match='synthetic provider failure'):
        index_document(repo, OfflineProvider(fail_at=2), 1, new_profile)
    assert repo.active == before
    assert len([k for k in repo.cache if k[0] == new_profile.key]) == 32
    result = index_document(repo, OfflineProvider(), 1, new_profile)
    assert result['cachedChunks'] == 32
    assert result['embeddedInputs'] == 33
    assert result['providerCalls'] == 2


@pytest.mark.parametrize('vectors', [[], [[1.0]], [[float('nan')] * 768], [[0.0] * 768]])
def test_invalid_batch_never_writes_cache_or_active(vectors):
    repo = MemoryRepository(1)
    provider = OfflineProvider()
    provider.embed = lambda *args: vectors
    with pytest.raises(ValueError):
        index_document(repo, provider, 1, PROFILE)
    assert repo.cache == {}
    assert repo.active is None


def test_metadata_mutation_during_provider_call_is_rejected():
    repo = MemoryRepository(1)
    provider = OfflineProvider()

    def embed(*args):
        repo.chunks[0] = replace(repo.chunks[0], metadata={'review': 'changed'})
        return [VECTOR]

    provider.embed = embed
    with pytest.raises(StaleDocument):
        index_document(repo, provider, 1, PROFILE)
    assert repo.active is None
    assert not repo.cache


def test_provider_settings_mismatch_rejected_before_work():
    from finguard_ai.config import Settings

    provider = OfflineProvider()
    provider.settings = Settings(service_token='s' * 32)
    with pytest.raises(ValueError, match='do not match'):
        index_document(MemoryRepository(1), provider, 1, PROFILE)
    assert provider.calls == []


def test_cli_dry_run_never_constructs_provider(monkeypatch, capsys):
    import json

    from finguard_ai import indexing
    from finguard_ai.config import Settings

    class Pool:
        def open(self):
            pass

        def close(self):
            pass

    settings = Settings(service_token='s' * 32, database_host='offline-test')
    monkeypatch.setattr('sys.argv', ['finguard-index', '--document-id', '1', '--dry-run'])
    monkeypatch.setattr(indexing, 'load_settings', lambda path: settings)
    monkeypatch.setattr(indexing, 'make_pool', lambda *args: Pool())
    monkeypatch.setattr(indexing, 'CorpusRepository', lambda pool: MemoryRepository(1))

    def unexpected(*args):
        pytest.fail('dry-run constructed external provider')

    monkeypatch.setattr(indexing, 'create_provider', unexpected)
    indexing.main()
    result = json.loads(capsys.readouterr().out)
    assert result['plannedEmbeddingInputs'] == 1
    assert result['providerCalls'] == 0
    assert not result['published']
