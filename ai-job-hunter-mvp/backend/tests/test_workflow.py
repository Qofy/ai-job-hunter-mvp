from datetime import datetime,timezone,timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app

CV='Alex Example\nFrontend Engineer\nSkills: React and TypeScript\nExperience: Built accessible interfaces.'
JD='Frontend Engineer at Example Employer. Develop accessible React and TypeScript applications.'


@pytest.fixture
def client():
    with TestClient(app) as client:
        client.post('/auth/register',json={'username':'workflow-test','password':'long-test-password-2026'})
        yield client


def saved(client):
    documents={'cv':CV,'job_description':JD,'cv_draft':CV,'cover_letter':'Dear team, I am interested in your frontend role and have experience building accessible interfaces.'}
    checked=client.post('/cv/documents/check',json=documents).json()
    request={**documents,'reviewed_hash':checked['version_hash'],'job_url':'https://example.test/careers/frontend?utm_source=test',
             'job_title':'Frontend Engineer','company':'Example Employer'}
    result=client.post('/workflow/applications',json=request)
    assert result.status_code==201,result.text
    return result.json(),request


def test_modes_are_persistent_and_owner_scoped_but_not_fake_connections(client):
    initial=client.get('/workflow/automation').json()
    assert initial['policy']['mode']=='review' and initial['policy']['paused'] is True
    updated=client.put('/workflow/automation',json={'mode':'automatic','paused':False,'weekly_limit':10,'minimum_match':80}).json()
    assert updated['policy']['mode']=='automatic' and not updated['submission_ready'] and updated['blockers']
    assert client.get('/workflow/automation').json()['policy']['weekly_limit']==10
    client.post('/auth/register',json={'username':'other-workflow','password':'long-test-password-2026'})
    assert client.get('/workflow/automation').json()['policy']['mode']=='review'


def test_saved_documents_are_private_duplicate_safe_and_separately_approved(client):
    application,request=saved(client)
    assert application['status']=='pending_approval' and application['submitted_at'] is None
    assert application['cv']==CV and application['job']['source']=='user_provided'
    assert client.post('/workflow/applications',json=request).status_code==409
    decision={'expected_document_id':application['document_id'],'expected_hash':application['document_hash']}
    result=client.post(f"/applications/{application['id']}/approve",json=decision)
    assert result.status_code==200 and result.json()['submitted'] is False
    client.post('/auth/register',json={'username':'other-owner','password':'long-test-password-2026'})
    assert client.get('/applications').json()==[]
    assert client.get(f"/workflow/applications/{application['id']}/progress").status_code==404
    assert client.post(f"/applications/{application['id']}/approve",json=decision).status_code==404


def test_progress_records_evidence_without_inventing_submission(client):
    application,_=saved(client)
    url=f"/workflow/applications/{application['id']}/progress"
    evidence={'kind':'interview','evidence':'Recruiter message: Please attend an interview next week.',
              'received_at':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()}
    result=client.post(url,json=evidence)
    assert result.status_code==201 and result.json()['verified'] is False
    assert client.post(url,json=evidence).status_code==409
    rows=client.get(url).json()
    assert rows[0]['kind']=='interview' and rows[0]['provenance']=='user_reported'
    details=client.get(f"/applications/{application['id']}").json()
    assert details['submitted_at'] is None and details['status']=='pending_approval'
    assert any(event['action']=='application.progress_reported' for event in details['history'])
    assert client.post(url,json={**evidence,'received_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}).status_code==422


def test_changed_review_and_unmatched_discovered_job_are_rejected(client):
    _,request=saved(client)
    assert client.post('/workflow/applications',json={**request,'cv_draft':CV+' changed'}).status_code==409
    assert client.post('/workflow/applications',json={**request,'job_url':'https://example.test/another','discovered_job_id':'not-real'}).status_code==409
