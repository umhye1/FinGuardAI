"""Real pgvector tests; synthetic deterministic provider, no HTTP/provider credentials."""
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from test_repository import insert_document
from test_repository import repository as repository

from finguard_ai.errors import StaleDocument
from finguard_ai.indexing import EmbeddingProfile, index_document

pytestmark = pytest.mark.integration
PROFILE = EmbeddingProfile('offline-deterministic', 'test-768')


class DeterministicProvider:
    def __init__(self, fail_at=None, action=None):
        self.calls = 0
        self.fail_at = fail_at
        self.action = action

    def embed(self, texts, task):
        self.calls += 1
        if self.action:
            self.action()
        if self.calls == self.fail_at:
            raise RuntimeError('synthetic batch failure')
        return [self.vector(t) for t in texts]

    @staticmethod
    def vector(text):
        # Exact unit vectors avoid float roundoff as a confounder in equality checks.
        position = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16) % 768
        return [1.0 if i == position else 0.0 for i in range(768)]


def populate(repo, count=100):
    doc = insert_document(repo, '합성 본문 0')
    with repo.pool.connection() as conn:
        for i in range(1, count):
            conn.execute('INSERT INTO document_chunks(document_id, chunk_index, content, created_at) '
                         'VALUES (%s, %s, %s, now())', (doc, i, f'합성 본문 {i}'))
    return doc


def active(repo, doc):
    with repo.pool.connection() as conn:
        return conn.execute('SELECT e.chunk_id, e.embedding_model, e.content_hash, '
                            'e.embedding::text, e.updated_at FROM document_embeddings e '
                            'JOIN document_chunks c USING(chunk_id) WHERE c.document_id=%s '
                            'ORDER BY e.chunk_id, e.embedding_model', (doc,)).fetchall()


@pytest.mark.parametrize('changed', [0, 1, 10, 100])
def test_change_ratios_match_full_vectors_and_search(repository, changed):
    doc = populate(repository)
    index_document(repository, DeterministicProvider(), doc, PROFILE)
    with repository.pool.connection() as conn:
        conn.execute("UPDATE document_chunks SET content=content || ' 수정' "
                     'WHERE document_id=%s AND chunk_index < %s', (doc, changed))
    plan = index_document(repository, None, doc, PROFILE, dry_run=True)
    assert plan['plannedEmbeddingInputs'] == changed
    incremental = index_document(repository, DeterministicProvider(), doc, PROFILE)
    before = active(repository, doc)
    query = DeterministicProvider.vector('합성 본문 0')
    inc_search = repository.search(query, PROFILE.model, 100, -1)
    full = index_document(repository, DeterministicProvider(), doc, PROFILE, force=True)
    assert active(repository, doc) == before  # No timestamp writes for identical active vectors.
    assert repository.search(query, PROFILE.model, 100, -1) == inc_search
    assert incremental['embeddedInputs'] == changed
    assert full['embeddedInputs'] == 100
    assert incremental['providerCalls'] == (changed + 31) // 32
    output = os.getenv('INCREMENTAL_REPORT_DIR')
    if output:
        path = Path(output)
        path.mkdir(parents=True, exist_ok=True)
        snapshot = repository.document_chunks(doc)
        (path / f'change-{changed}.json').write_text(json.dumps({
            'synthetic': True, 'provider': 'deterministic unit vectors; no external calls',
            'sampleCount': 1, 'order': 'incremental then full', 'changedPercent': changed,
            'snapshotSha256': hashlib.sha256(json.dumps([c.content for c in snapshot]).encode()).hexdigest(),
            'incremental': incremental, 'full': full, 'vectorsEqual': True, 'searchEqual': True,
        }, ensure_ascii=False, indent=2) + '\n')


def test_recreated_ids_and_metadata_only_changes_reuse_and_deleted_doc_cleans_cache(repository):
    doc = populate(repository, 3)
    index_document(repository, DeterministicProvider(), doc, PROFILE)
    contents = [c.content for c in repository.document_chunks(doc)]
    with repository.pool.connection() as conn:
        conn.execute('DELETE FROM document_chunks WHERE document_id=%s', (doc,))
        conn.execute("UPDATE documents SET evidence_metadata='{}', title='new title' WHERE document_id=%s", (doc,))
        for i, text in enumerate(contents):
            conn.execute('INSERT INTO document_chunks(document_id, chunk_index, content, created_at) '
                         'VALUES (%s,%s,%s,now())', (doc, i, text))
    provider = DeterministicProvider()
    result = index_document(repository, provider, doc, PROFILE)
    assert result['cachedChunks'] == 3
    assert provider.calls == 0
    with repository.pool.connection() as conn:
        conn.execute('DELETE FROM documents WHERE document_id=%s', (doc,))
        assert conn.execute('SELECT count(*) AS n FROM document_embedding_cache').fetchone()['n'] == 0
    assert repository.search(DeterministicProvider.vector(contents[0]), PROFILE.model, 5, -1) == []


def test_durable_batches_retry_without_partial_active_publish(repository):
    doc = populate(repository, 65)
    index_document(repository, DeterministicProvider(), doc, PROFILE)
    before = active(repository, doc)
    new_profile = replace(PROFILE, revision='new-revision')
    with pytest.raises(RuntimeError, match='synthetic batch failure'):
        index_document(repository, DeterministicProvider(fail_at=2), doc, new_profile)
    assert active(repository, doc) == before
    result = index_document(repository, DeterministicProvider(), doc, new_profile)
    assert result['cachedChunks'] == 32
    assert result['embeddedInputs'] == 33
    assert active(repository, doc) == before


@pytest.mark.parametrize('mutation', ['body', 'metadata', 'state', 'delete'])
def test_concurrent_mutation_never_activates_stale_vectors(repository, mutation):
    doc = populate(repository, 1)
    index_document(repository, DeterministicProvider(), doc, PROFILE)

    def mutate():
        with repository.pool.connection() as conn:
            # Production writers lock the parent document first as well.
            conn.execute('SELECT document_id FROM documents WHERE document_id=%s FOR UPDATE', (doc,))
            if mutation == 'body':
                conn.execute("UPDATE document_chunks SET content='changed' WHERE document_id=%s", (doc,))
            elif mutation == 'metadata':
                conn.execute("UPDATE documents SET evidence_metadata='{}', title='changed' WHERE document_id=%s", (doc,))
            elif mutation == 'state':
                conn.execute("UPDATE documents SET status='PROCESSING' WHERE document_id=%s", (doc,))
            else:
                conn.execute('DELETE FROM documents WHERE document_id=%s', (doc,))

    with pytest.raises(StaleDocument):
        index_document(repository, DeterministicProvider(action=mutate), doc, replace(PROFILE, revision='v2'))
    with repository.pool.connection() as conn:
        assert conn.execute('SELECT count(*) AS n FROM document_embedding_cache WHERE profile_hash=%s',
                            (replace(PROFILE, revision='v2').key,)).fetchone()['n'] == 0
    if mutation in ('body', 'state', 'delete'):
        assert repository.search(DeterministicProvider.vector('합성 본문 0'), PROFILE.model, 5, -1) == []


def test_failed_final_publish_leaves_prior_index_and_reuses_staged_vectors(repository, monkeypatch):
    doc = populate(repository, 2)
    index_document(repository, DeterministicProvider(), doc, PROFILE)
    before = active(repository, doc)
    profile = replace(PROFILE, revision='v3')
    publish = repository.publish

    def fail(*args):
        raise RuntimeError('synthetic publish failure')

    monkeypatch.setattr(repository, 'publish', fail)
    with pytest.raises(RuntimeError):
        index_document(repository, DeterministicProvider(), doc, profile)
    assert active(repository, doc) == before
    monkeypatch.setattr(repository, 'publish', publish)
    assert index_document(repository, DeterministicProvider(), doc, profile)['providerCalls'] == 0


def test_deleted_chunk_not_searchable_and_profile_model_isolation(repository):
    doc = populate(repository, 3)
    index_document(repository, DeterministicProvider(), doc, PROFILE)
    rows = repository.document_chunks(doc)
    with repository.pool.connection() as conn:
        conn.execute('DELETE FROM document_chunks WHERE chunk_id=%s', (rows[0].chunk_id,))
    result = index_document(repository, DeterministicProvider(), doc, PROFILE)
    assert result['cachedChunks'] == 2
    assert rows[0].chunk_id not in [c.chunk_id for c in repository.search(
        DeterministicProvider.vector(rows[0].content), PROFILE.model, 5, -1)]
    next_model = replace(PROFILE, model='next-model')
    assert index_document(repository, DeterministicProvider(), doc, next_model)['embeddedInputs'] == 2
    assert repository.has_embeddings(PROFILE.model)
    assert repository.has_embeddings(next_model.model)


def test_reused_vectors_do_not_cache_evidence_policy(repository):
    from datetime import date

    from finguard_ai.corpus import import_corpus, load_manifest
    from finguard_ai.evidence import select_evidence

    records = list(load_manifest(Path(__file__).parents[1] / 'data/official/manifest.json'))
    ids = import_corpus(repository.pool, records)
    for doc in ids:
        index_document(repository, DeterministicProvider(), doc, PROFILE)
    with repository.pool.connection() as conn:
        conn.execute(
            "UPDATE documents SET evidence_metadata = "
            "jsonb_set(evidence_metadata::jsonb, '{claims,0,value}', '\"synthetic-conflict\"')::text "
            'WHERE document_id=%s', (ids[3],),
        )
    result = index_document(repository, DeterministicProvider(), ids[3], PROFILE)
    assert result['providerCalls'] == 0
    rows = repository.policy_candidates({'transfer'}, None, PROFILE.model, '송금', 0.6)
    assert select_evidence('송금', rows, today=date(2026, 9, 11)).reason == 'CONFLICTING_EVIDENCE'


def test_cache_is_scoped_to_document(repository):
    first = populate(repository, 2)
    second = populate(repository, 2)
    index_document(repository, DeterministicProvider(), first, PROFILE)
    result = index_document(repository, DeterministicProvider(), second, PROFILE)
    assert result['cachedChunks'] == 0
    assert result['embeddedInputs'] == 2


def test_zero_call_publish_still_checks_metadata_snapshot(repository, monkeypatch):
    doc = populate(repository, 2)
    index_document(repository, DeterministicProvider(), doc, PROFILE)
    original = repository.publish
    before = active(repository, doc)

    def concurrent_publish(*args):
        with repository.pool.connection() as conn:
            conn.execute("UPDATE documents SET title='changed just before publish' WHERE document_id=%s", (doc,))
        original(*args)

    monkeypatch.setattr(repository, 'publish', concurrent_publish)
    provider = DeterministicProvider()
    with pytest.raises(StaleDocument, match='metadata'):
        index_document(repository, provider, doc, PROFILE)
    assert provider.calls == 0
    assert active(repository, doc) == before
