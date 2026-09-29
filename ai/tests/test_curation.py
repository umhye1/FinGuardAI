import copy
import json
from datetime import date
from pathlib import Path

import pytest

from finguard_ai.benchmark_data import digest
from finguard_ai.curation import finalize, load_queue, overlap_report, prepare, render_form
from finguard_ai.encoder_data import load_registered, reference_hashes, register

QUEUE = Path(__file__).parents[1] / 'data/review/public-cases-v1'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False))


@pytest.fixture
def queue(tmp_path):
    path = tmp_path / 'queue'
    path.mkdir()
    source = {'id': 'test-source', 'license': 'KOGL-1', 'status': 'ELIGIBLE',
              'licenseEvidence': 'unit test fixture only', 'url': 'https://example.org/source'}
    rows = [{'id': f'case-{i}', 'text': text, 'sourceId': source['id'], 'group': source['id'],
             'sourceType': 'licensed', 'reviewStatus': 'PENDING', 'locator': str(i),
             'representation': 'PUBLISHED_EXAMPLE'} for i, text in enumerate([
                 '테스트 약속 대화', '테스트 이체 유도', '테스트 예방 안내'])]
    write(path / 'sources.json', [source])
    (path / 'candidates.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    freeze(path)
    return path


def freeze(path):
    write(path / 'manifest.json', {'datasetAuthor': 'curator', 'files': {
        name: digest(path / name) for name in ('sources.json', 'candidates.jsonl')}})


def reviewed(queue, tmp_path):
    output = tmp_path / 'work'
    prepare(queue, [], output)
    record = json.loads((output / 'review.json').read_text())
    record.update(reviewer='human', reviewedOn=date.today().isoformat(), independentReviewAttested=True)
    for decision, label in zip(record['decisions'].values(), ['NORMAL', 'PHISHING', 'PREVENTION']):
        decision.update(decision='APPROVE', label=label, reason='manually checked',
                        privacyReviewed=True, rightsReviewed=True, overlapReviewed=True)
    write(output / 'review.json', record)
    return output / 'review.json', record


def test_public_queue_frozen_unlabelled_and_excluded_source_unused():
    rows, sources, _, _ = load_queue(QUEUE)
    assert len(rows) == 19
    assert all('label' not in r for r in rows)
    assert all(sources[r['sourceId']]['status'] == 'ELIGIBLE' for r in rows)
    assert {r['representation'] for r in rows} == {'PUBLISHED_EXAMPLE', 'NOTICE_EXCERPT'}


def test_prepare_blind_and_does_not_overwrite(queue, tmp_path):
    out = tmp_path / 'work'
    result = prepare(queue, [], out)
    assert result['state'] == 'PENDING'
    record = json.loads((out / 'review.json').read_text())
    assert all(r['label'] == '' for r in record['decisions'].values())
    assert not record['independentReviewAttested']
    with pytest.raises(ValueError, match='overwrite'):
        prepare(queue, [], out)


def test_successful_review_integrates_with_existing_registration(queue, tmp_path):
    path, _ = reviewed(queue, tmp_path)
    output = tmp_path / 'approved'
    result = finalize(queue, path, [], output)
    assert result['approved'] == 3
    reg = output / 'registration.json'
    register(output / 'evaluation.jsonl', output / 'review.json', reference_hashes([]), reg)
    rows, _ = load_registered(output / 'evaluation.jsonl', reg, reference_hashes([]))
    assert len(rows) == 3
    with pytest.raises(ValueError, match='overwrite'):
        finalize(queue, path, [], output)


@pytest.mark.parametrize('field,value', [('decision', 'PENDING'), ('decision', 'UNCERTAIN'),
    ('label', ''), ('privacyReviewed', False), ('rightsReviewed', False),
    ('overlapReviewed', False), ('reason', '')])
def test_incomplete_review_blocked(queue, tmp_path, field, value):
    path, record = reviewed(queue, tmp_path)
    record['decisions']['case-0'][field] = value
    write(path, record)
    with pytest.raises(ValueError):
        finalize(queue, path, [], tmp_path / 'approved')
    assert not (tmp_path / 'approved').exists()


@pytest.mark.parametrize('mutation', ['hash', 'author', 'reviewer', 'attestation', 'missing', 'extra'])
def test_review_binding_and_identity(queue, tmp_path, mutation):
    path, record = reviewed(queue, tmp_path)
    if mutation == 'hash':
        record['queueSha256'] = 'changed'
    elif mutation == 'author':
        record['datasetAuthor'] = 'changed'
    elif mutation == 'reviewer':
        record['reviewer'] = 'curator'
    elif mutation == 'attestation':
        record['independentReviewAttested'] = False
    elif mutation == 'missing':
        record['decisions'].pop('case-0')
    else:
        record['decisions']['extra'] = {}
    write(path, record)
    with pytest.raises(ValueError):
        finalize(queue, path, [], tmp_path / 'approved')


def test_exclusion_cannot_bypass_class_coverage(queue, tmp_path):
    path, record = reviewed(queue, tmp_path)
    record['decisions']['case-0'].update(decision='EXCLUDE', reason='ambiguous')
    write(path, record)
    with pytest.raises(ValueError, match='three labels'):
        finalize(queue, path, [], tmp_path / 'approved')


def test_reference_overlap_blocks_export(queue, tmp_path):
    path, _ = reviewed(queue, tmp_path)
    rows, _, _, _ = load_queue(queue)
    ref = copy.deepcopy(rows[0])
    ref.update(id='old-case', group='old-source')
    with pytest.raises(ValueError, match='overlaps'):
        finalize(queue, path, [ref], tmp_path / 'approved')
    assert overlap_report(rows, [ref])[0]['needsOverlapReview']


@pytest.mark.parametrize('mutation', ['url', 'phone', 'label', 'duplicate', 'rights', 'checksum'])
def test_invalid_candidates(queue, mutation):
    rows, _, _, _ = load_queue(queue)
    if mutation == 'rights':
        sources = json.loads((queue / 'sources.json').read_text())
        sources[0]['license'] = 'KOGL-4'
        write(queue / 'sources.json', sources)
    elif mutation == 'url':
        rows[0]['text'] = 'https://example.com'
    elif mutation == 'phone':
        rows[0]['text'] = '010-1234-5678'
    elif mutation == 'label':
        rows[0]['label'] = 'NORMAL'
    elif mutation == 'duplicate':
        rows[1]['text'] = rows[0]['text']
    else:
        rows[0]['text'] = 'tampered'
    (queue / 'candidates.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    if mutation != 'checksum':
        freeze(queue)
    with pytest.raises(ValueError):
        load_queue(queue)


def test_html_escapes_candidate_and_json():
    page = render_form([{'id': '\"><script>', 'text': '<script>alert(1)</script>'}],
                       {'datasetAuthor': '</script><script>alert(1)</script>'})
    assert '<script>alert(1)</script>' not in page
    assert '&lt;script&gt;' in page
    assert '\\u003c/script>' in page
