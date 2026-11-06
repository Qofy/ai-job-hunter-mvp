import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.db import get_engine
from app.models import Credential, Job
from app import board_feeds as feeds


@pytest.fixture
def client():
    with TestClient(app) as value:
        assert value.post('/auth/register', json={'username': 'board-test', 'password': 'local-board-test-password'}).status_code == 201
        yield value


def raw(board='linkedin', identifier=1, final_url=None):
    return {'id': identifier, 'job_title': 'Frontend Engineer',
            'url': f'https://www.{feeds.BOARDS[board][1][0]}/jobs/{identifier}',
            'source_url': f'https://www.{feeds.BOARDS[board][1][0]}/jobs/{identifier}',
            'final_url': final_url, 'company_object': {'name': 'Actual feed employer'},
            'locations': [{'country_name': 'Germany', 'country_code': 'DE', 'display_name': 'Berlin, Germany'}],
            'description': 'Build accessible React and TypeScript interfaces.', 'remote': True,
            'date_posted': '2026-11-01', 'closed_at': None, 'has_blurred_data': False}


def transport(monkeypatch, rows=None, search_status=200):
    calls = []
    original = httpx.AsyncClient
    def handler(request):
        assert request.headers['authorization'] == 'Bearer fake-job-data-key-for-tests'
        if str(request.url) == feeds.CHECK_URL:
            return httpx.Response(200, json={'credits': 100})
        assert str(request.url) == feeds.SEARCH_URL
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload['limit'] == 25 and payload['is_closed'] is False
        assert payload['job_country_code_or'] == ['DE', 'NL', 'FR']
        assert 'cv' not in payload and 'profile' not in payload
        return httpx.Response(search_status, json={'data': rows if rows is not None else [raw()]}, headers={'retry-after': '900'})
    monkeypatch.setattr(feeds.httpx, 'AsyncClient', lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)))
    return calls


def connect(client):
    result = client.post('/connections/job-data', json={'api_key': 'fake-job-data-key-for-tests'})
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize('board', list(feeds.BOARDS))
def test_each_board_normalizes_real_source_fields(board):
    result = feeds.normalize_job(raw(board), board)
    assert result['source'] == board and result['data_provider'] == 'TheirStack'
    assert result['is_demo'] is False and result['country'] == 'Germany'
    assert result['source_created_at'].startswith('2026-11-01')
    assert result['company'] == 'Actual feed employer'
    assert feeds.normalize_job({**raw(board), 'has_blurred_data': True}, board) is None
    assert feeds.normalize_job({**raw(board), 'closed_at': '2026-11-02'}, board) is None


def test_spoofed_board_domains_and_incomplete_records_are_rejected():
    value = {**raw(), 'url': 'https://evil-linkedin.com/jobs/1', 'source_url': 'https://linkedin.com.evil.test/job/1'}
    assert feeds.normalize_job(value, 'theirstack') is None
    assert feeds.normalize_job(raw('indeed'), 'linkedin') is None
    assert feeds.normalize_job({**raw(), 'company_object': {}, 'company': None}, 'linkedin') is None
    result = feeds.normalize_job({**raw(), 'description': None}, 'linkedin')
    assert result['description'] == '' and result['description_missing']


def test_connection_is_private_encrypted_and_does_not_search(client, monkeypatch):
    calls = transport(monkeypatch)
    status = connect(client)
    assert status['configured'] and calls == []
    assert 'fake-job-data-key-for-tests' not in json.dumps(status)
    with Session(get_engine()) as db:
        saved = db.scalar(select(Credential).where(Credential.provider == 'theirstack'))
        assert 'fake-job-data-key-for-tests' not in saved.encrypted_value
    client.post('/auth/register', json={'username': 'another-board-user', 'password': 'another-board-test-password'})
    assert not client.get('/connections/job-data').json()['configured']
    assert client.post('/jobs/search', json={'source': 'linkedin'}).status_code == 503
    assert calls == []


def test_imports_reach_opportunities_dashboard_and_job_specific_cache(client, monkeypatch):
    calls = transport(monkeypatch)
    connect(client)
    first = client.post('/jobs/search', json={'source': 'linkedin'})
    assert first.status_code == 200, first.text
    result = first.json()
    assert result['source']['name'] == 'LinkedIn' and result['source']['status'] == 'live'
    assert len(result['jobs']) == 1 and result['jobs'][0]['source'] == 'linkedin'
    assert calls[0]['url_domain_or'] == ['linkedin.com']
    assert client.get('/workspace/jobs').json()['jobs'][0]['id'] == result['jobs'][0]['id']
    assert client.post('/jobs/search', json={'source': 'linkedin'}).json()['source']['status'] == 'cached'
    assert len(calls) == 1
    assert client.post('/jobs/search', json={'source': 'linkedin', 'roles': ['React Developer']}).status_code == 200
    assert len(calls) == 2
    cached = client.get('/jobs/live?source=linkedin').json()
    assert cached['criteria']['roles'] == ['React Developer']


def test_combined_boards_deduplicate_employer_urls_and_keep_source_attribution(client, monkeypatch):
    target = 'https://employer.example/jobs/frontend'
    rows = [raw('linkedin', 1, target), raw('indeed', 2, target), raw('xing', 3)]
    calls = transport(monkeypatch, rows)
    connect(client)
    combined = client.post('/jobs/search', json={'source': 'theirstack'}).json()
    assert len(combined['jobs']) == 2
    with Session(get_engine()) as db:
        assert len(list(db.scalars(select(Job)))) == 2
    assert set(calls[0]['url_domain_or']) == {domain for _, domains in feeds.BOARDS.values() for domain in domains}
    # A later import through another board keeps the stable job id and original sources.
    rows[:] = [raw('indeed', 2, target)]
    indeed = client.post('/jobs/search', json={'source': 'indeed'}).json()['jobs'][0]
    assert indeed['source'] == 'indeed'
    saved = client.get('/jobs/live?source=theirstack').json()['jobs']
    assert {job['id'] for job in saved} == {job['id'] for job in combined['jobs']}
    with Session(get_engine()) as db:
        record = db.scalar(select(Job).where(Job.canonical_url == target))
        assert {'linkedin', 'indeed'}.issubset(record.source_metadata['source_urls'])


def test_missing_key_and_provider_failures_never_create_fictional_jobs(client, monkeypatch):
    result = client.post('/jobs/search', json={'source': 'heyjobs'})
    assert result.status_code == 503 and 'Settings' in result.json()['detail']
    calls = transport(monkeypatch, search_status=429)
    connect(client)
    result = client.post('/jobs/search', json={'source': 'heyjobs'})
    assert result.status_code == 503 and 'rate limit' in result.json()['detail']
    assert client.post('/jobs/search', json={'source': 'heyjobs'}).status_code == 503
    assert len(calls) == 1
    assert client.get('/jobs/live?source=heyjobs').json()['jobs'] == []


def test_all_six_choices_are_valid_without_claiming_unconnected_live_results(client):
    for board in feeds.BOARDS:
        result = client.get('/jobs/live', params={'source': board})
        assert result.status_code == 200
        assert result.json()['source']['name'] == feeds.SOURCE_LABELS[board]
        assert result.json()['source']['status'] == 'not_searched'
        assert result.json()['jobs'] == []
