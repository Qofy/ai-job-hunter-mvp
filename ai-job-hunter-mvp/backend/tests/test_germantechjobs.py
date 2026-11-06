from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.germantechjobs import parse_feed
from app.job_sources import FeedUnavailable
import app.live_jobs as live


def feed(link='https://germantechjobs.de/jobs/example'):
    return f'''<rss><channel><item><title>Frontend Engineer @ Example Ltd [50 - 70 EUR]</title>
    <link>{link}</link><description>&lt;p&gt;React interfaces&lt;/p&gt;</description>
    <pubDate>Mon, 02 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>'''.encode()


def test_rss_attribution_and_unknown_location_are_preserved():
    job=parse_feed(feed())[0]
    assert job['company']=='Example Ltd' and job['title']=='Frontend Engineer'
    assert job['salary']=='50 - 70 EUR' and job['description']=='React interfaces'
    assert job['country'] is None and job['workplace_type']=='Unspecified'
    assert job['source']=='germantechjobs' and job['is_demo'] is False
    assert job['source_created_at'] is None
    assert not parse_feed(feed('https://evil.example/jobs/test'))


def test_external_entities_and_changed_format_are_rejected():
    for xml in [b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss><channel/></rss>',b'<html/>']:
        with pytest.raises(FeedUnavailable): parse_feed(xml)


def test_provider_choice_uses_separate_account_cache(monkeypatch):
    calls=[]
    async def fetch():
        calls.append(1)
        return {'jobs':parse_feed(feed()),'checked_at':datetime.now(timezone.utc).isoformat(),
                'pages':1,'has_more':False,'notes':[]}
    monkeypatch.setattr(live,'fetch_germantechjobs',fetch)
    with TestClient(app) as client:
        client.post('/auth/register',json={'username':'rss-test','password':'test-password-long-enough'})
        body={'source':'germantechjobs'}
        result=client.post('/jobs/search',json=body)
        assert result.status_code==200,result.text
        assert result.json()['source']['name']=='GermanTechJobs'
        assert len(result.json()['jobs'])==1
        assert client.post('/jobs/search',json=body).json()['source']['status']=='cached'
        assert len(calls)==1
        assert client.get('/jobs/live?source=germantechjobs').json()['jobs']
        assert client.get('/jobs/live').json()['jobs']==[]
        assert client.post('/jobs/search',json={'source':'unsupported-board'}).status_code==422
