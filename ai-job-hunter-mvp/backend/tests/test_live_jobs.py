from datetime import datetime, timezone, timedelta
import asyncio
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.main import app
from app.db import get_engine
from app.models import JobSource, Job
from app.job_filters import role_matches, job_matches, DEFAULT_ROLES
from app.job_sources import normalize_arbeitnow, FeedUnavailable, read_page, fetch_arbeitnow
import app.live_jobs as live
import app.job_sources as provider


def raw(slug='frontend-1',title='Frontend Engineer',location='Berlin',remote=True):
    return {'slug':slug,'title':title,'company_name':'Source company','location':location,
            'remote':remote,'url':f'https://www.arbeitnow.com/jobs/{slug}',
            'description':'<h2>Engineering</h2><p>React &amp; TypeScript interfaces.</p>',
            'tags':['React','TypeScript'],'job_types':['full_time'],'created_at':1700000000}


def test_normalization_uses_source_fields_without_inventing_workplace_or_dates():
    job=normalize_arbeitnow(raw(remote=False))
    assert job['company']=='Source company' and job['is_demo'] is False
    assert job['country']=='Germany' and job['location']=='Berlin'
    assert job['workplace_type']=='Unspecified'
    assert job['description']=='Engineering\n\nReact & TypeScript interfaces.'
    assert job['source_created_at'].startswith('2023-11-14')
    assert 'published_at' not in job
    assert normalize_arbeitnow({**raw(),'url':'javascript:alert(1)'}) is None
    assert normalize_arbeitnow({'title':'incomplete'}) is None


@pytest.mark.parametrize('title,role,expected',[
    ('Frontend Entwickler (m/w/d)','Frontend Engineer',True),
    ('Front-end Developer','Frontend Engineer',True),
    ('Softwareentwickler TypeScript','Software Engineer',True),
    ('Junior Sales Manager','Junior Developer',False),
    ('Early Career Software Engineer','Junior Developer',True),
    ('Senior Data Scientist','Data Scientist',True),
    ('Process Engineer','Frontend Engineer',False),
])
def test_role_filters_exclude_unrelated_titles(title,role,expected):
    assert role_matches({'title':title,'description':''},role) is expected


def test_country_and_work_filters_do_not_claim_unknown_eligibility():
    berlin=normalize_arbeitnow(raw(remote=False))
    assert job_matches(berlin,DEFAULT_ROLES,['Germany'],['Remote','Hybrid','On-site'])
    assert not job_matches(berlin,DEFAULT_ROLES,['Germany'],['Remote'])
    assert not job_matches(berlin,DEFAULT_ROLES,['Netherlands'],[])
    unknown=normalize_arbeitnow(raw(location='Small town not specified'))
    assert unknown['country'] is None
    assert job_matches(unknown,DEFAULT_ROLES,['Germany'],[])
    assert not job_matches(unknown,DEFAULT_ROLES,['Ghana'],[])
    assert not job_matches({**berlin,'is_demo':True},DEFAULT_ROLES,[],[])


@pytest.mark.asyncio
async def test_rate_limits_and_changed_response_fail_explicitly():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(429,headers={'Retry-After':'7200'}))) as client:
        with pytest.raises(FeedUnavailable) as error:
            await read_page(client,1)
        assert error.value.retry_seconds==7200
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'unexpected':[]}))) as client:
        with pytest.raises(FeedUnavailable,match='format changed'):
            await read_page(client,1)


@pytest.mark.asyncio
async def test_pagination_does_not_follow_untrusted_next_url(monkeypatch):
    calls=[]
    async def page(client,number):
        calls.append(number)
        return {'data':[raw(str(number))], 'links':{'next':'https://untrusted.invalid/private' if number==1 else None}}
    monkeypatch.setattr(provider,'read_page',page)
    result=await fetch_arbeitnow()
    assert calls==[1,2] and result['pages']==2 and len(result['jobs'])==2
    assert all(j['source']=='arbeitnow' and not j['is_demo'] for j in result['jobs'])


@pytest.mark.asyncio
async def test_partial_scan_is_reported_not_hidden(monkeypatch):
    async def page(client,number):
        if number>1: raise FeedUnavailable('Source temporarily unavailable')
        return {'data':[raw()], 'links':{'next':'next'}}
    monkeypatch.setattr(provider,'read_page',page)
    result=await fetch_arbeitnow()
    assert len(result['jobs'])==1 and result['pages']==1
    assert result['has_more'] is True and result['notes']


@pytest.fixture
def client():
    with TestClient(app) as value:
        response=value.post('/auth/register',json={'username':'live-test','password':'local-test-password-long'})
        assert response.status_code==201
        yield value


@pytest.fixture
def feed(monkeypatch):
    calls=[]
    async def fetch():
        calls.append(1)
        return {'jobs':[normalize_arbeitnow(raw()),normalize_arbeitnow(raw('sales','Sales Manager')),
                        normalize_arbeitnow(raw('paris','Software Engineer','Paris',False)),
                        normalize_arbeitnow(raw('us','Frontend Engineer','Boston, United States'))],
                'checked_at':datetime.now(timezone.utc).isoformat(),'pages':1,'has_more':False,'notes':[]}
    monkeypatch.setattr(live,'fetch_arbeitnow',fetch)
    return calls


def test_live_search_persists_real_records_and_filters_locally(client,feed):
    response=client.post('/jobs/search',json={})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['source']['status']=='live' and data['source']['scanned']==4
    assert {j['id'] for j in data['jobs']}=={'arbeitnow:frontend-1','arbeitnow:paris'}
    assert all(not j['is_demo'] for j in data['jobs'])
    with Session(get_engine()) as db:
        rows=list(db.scalars(select(Job)))
        assert len(rows)==4
        assert all(row.published_at is None for row in rows)
    cached=client.post('/jobs/search',json={'roles':['Sales Manager']}).json()
    assert cached['source']['status']=='cached' and len(cached['jobs'])==1
    assert len(feed)==1
    assert client.get('/jobs/live').json()['criteria']['roles']==['Sales Manager']


def test_saved_search_is_account_scoped(client,feed):
    client.post('/jobs/search',json={})
    client.post('/auth/register',json={'username':'another-user','password':'local-test-password-long'})
    data=client.get('/jobs/live').json()
    assert data['jobs']==[] and data['source']['status']=='not_searched'
    assert client.post('/jobs/search',json={'roles':[]}).status_code==422


def test_source_failure_never_loads_demo_or_hammers_provider(client,monkeypatch):
    calls=[]
    async def failed():
        calls.append(1)
        raise FeedUnavailable('Feed unavailable',7200)
    monkeypatch.setattr(live,'fetch_arbeitnow',failed)
    assert client.post('/jobs/search',json={}).status_code==503
    assert client.post('/jobs/search',json={}).status_code==503
    assert len(calls)==1
    with Session(get_engine()) as db:
        assert not list(db.scalars(select(Job)))
        assert db.scalar(select(JobSource)).last_error=='Feed unavailable'


def test_stale_cache_survives_outage_and_is_marked_stale(client,feed,monkeypatch):
    first=client.post('/jobs/search',json={}).json()
    with Session(get_engine()) as db:
        source=db.scalar(select(JobSource))
        source.last_success_at=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
        db.commit()
    async def failed(): raise FeedUnavailable('Feed offline')
    monkeypatch.setattr(live,'fetch_arbeitnow',failed)
    result=client.post('/jobs/search',json={})
    assert result.status_code==200
    stale=result.json()
    assert stale['source']['status']=='stale' and stale['source']['error']=='Feed offline'
    assert [j['id'] for j in stale['jobs']]==[j['id'] for j in first['jobs']]
    assert all(not j['is_demo'] for j in stale['jobs'])


def test_search_requires_local_session():
    with TestClient(app) as anonymous:
        assert anonymous.post('/jobs/search',json={}).status_code==401
        assert anonymous.get('/jobs/live').status_code==401
