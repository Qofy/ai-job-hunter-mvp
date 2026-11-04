"""Synthetic, isolated Gmail/queue checks. No messages leave the test process."""
import json
from datetime import datetime,timezone
from email.message import EmailMessage
from email.utils import formatdate
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.main import app
from app.db import get_engine
from app.models import Job,JobSource,Credential,AgentTask,SubmissionAttempt,ApplicationDraft,Approval
import app.gmail as gmail
import app.agent as agent

CV='Alex Example\nalex@example.test\nSKILLS\nReact, TypeScript, JavaScript, HTML, CSS\nEXPERIENCE\nBuilt accessible frontend applications at Example GmbH, 2023-2025.'


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(gmail,'test_connection',lambda _:None)
    with TestClient(app) as client:
        client.post('/auth/register',json={'username':'agent-test','password':'isolated-test-password-2026'})
        yield client


def connect(client):
    result=client.post('/connections/gmail',json={'email':'alex@example.test','app_password':'abcdefghijklmnop','allow_send':True,'allow_read':True})
    assert result.status_code==200,result.text


def master(client):
    result=client.put('/workspace/candidate',json={'profile':{'name':'Alex Example','skills':['React','TypeScript','JavaScript','HTML','CSS'],
        'work_authorization_countries':['Germany'],'targets':{'titles':['Frontend Engineer']}},'master_cv':CV,'facts_confirmed':True})
    assert result.status_code==200,result.text


def application(client,slug='one',approve=True):
    with Session(get_engine()) as db:
        row=Job(source='arbeitnow',external_id=f'arbeitnow:{slug}',canonical_url=f'https://example.test/jobs/{slug}',is_demo=False,
                payload={'id':f'arbeitnow:{slug}','source':'arbeitnow','url':f'https://example.test/jobs/{slug}',
                'company':'Example GmbH','title':'Frontend Engineer','location':'Berlin','country':'Germany',
                'description':'Build React, TypeScript, JavaScript, HTML and CSS interfaces. Apply by email to jobs@employer.test.',
                'workplace_type':'Remote','is_demo':False})
        db.add(row);db.flush()
        source=db.scalar(select(JobSource).where(JobSource.kind=='arbeitnow'))
        from app.models import User
        if not source:
            source=JobSource(user_id=db.scalar(select(User.id)),kind='arbeitnow',identifier='public-feed',config={})
            db.add(source)
        source.config={'job_ids':source.config.get('job_ids',[])+[row.id]};source.last_success_at=datetime.now(timezone.utc).isoformat()
        db.commit()
    result=client.post('/workspace/prepare',json={'job_id':f'arbeitnow:{slug}','job_url':f'https://example.test/jobs/{slug}'})
    assert result.status_code==201,result.text
    row=result.json()
    result=client.put(f"/agent/applications/{row['id']}/delivery",json={**snapshot(row),'recipient':'jobs@employer.test',
        'subject':'Application: Frontend Engineer','accepts_email':True,'eligibility_confirmed':True})
    assert result.status_code==200,result.text
    row=result.json()
    if approve:
        response=client.post(f"/applications/{row['id']}/approve",json=snapshot(row))
        assert response.status_code==200,response.text
        row=response.json()['application']
    return row


def snapshot(row): return {'expected_document_id':row['document_id'],'expected_hash':row['document_hash']}
def queue(client,row,automatic=False): return client.post(f"/agent/applications/{row['id']}/queue",json={**snapshot(row),'automatic':automatic})


def sender(monkeypatch):
    calls=[]
    def send(value,message):
        calls.append(message)
        return {'message_id':str(message['Message-ID']),'accepted_at':datetime.now(timezone.utc).isoformat(),
                'provider':'gmail_smtp','meaning':'Synthetic SMTP acceptance used only in tests.'}
    monkeypatch.setattr(agent,'send_message',send)
    return calls


def test_gmail_credentials_are_encrypted_owned_and_never_echoed(client):
    connect(client)
    with Session(get_engine()) as db:
        encrypted=db.scalar(select(Credential)).encrypted_value
        assert 'abcdefghijklmnop' not in encrypted and 'alex@example.test' not in encrypted
    status=client.get('/connections/gmail')
    assert status.json()['can_send'] and 'abcdefghijklmnop' not in status.text
    invalid=client.post('/connections/gmail',json={'email':'alex@example.test','app_password':'secret-with-invalid-characters','allow_send':True})
    assert invalid.status_code==422 and 'secret-with-invalid-characters' not in invalid.text
    client.post('/auth/register',json={'username':'another-agent','password':'isolated-test-password-2026'})
    assert not client.get('/connections/gmail').json()['connected']


def test_manual_queue_requires_exact_approval_and_sends_once(client,monkeypatch):
    connect(client);master(client);row=application(client,approve=False)
    assert queue(client,row).status_code==409
    assert client.post(f"/applications/{row['id']}/approve",json=snapshot(row)).status_code==200
    response=queue(client,row);assert response.status_code==202,response.text
    task=response.json();assert queue(client,row).status_code==409
    assert client.get(f"/applications/{row['id']}").json()['submitted_at'] is None
    calls=sender(monkeypatch)
    agent.process_task(task['id']);agent.process_task(task['id'])
    assert len(calls)==1 and calls[0]['To']=='jobs@employer.test'
    assert len(list(calls[0].iter_attachments()))==2
    current=client.get(f"/applications/{row['id']}").json()
    assert current['status']=='submitted' and current['confirmation']['provider']=='gmail_smtp'


def test_editing_delivery_or_documents_invalidates_queued_version(client,monkeypatch):
    connect(client);master(client);row=application(client);task=queue(client,row).json();calls=sender(monkeypatch)
    revised=client.put(f"/workspace/applications/{row['id']}",json={**snapshot(row),'cv_text':CV+'\nReviewed addition.',
        'cover_letter':row['cover_letter'],'answers':{},'facts_confirmed':True})
    assert revised.status_code==200,revised.text
    agent.process_task(task['id']);assert calls==[]
    assert revised.json()['status']=='pending_approval'
    assert client.post(f"/applications/{row['id']}/approve",json=snapshot(row)).status_code==409


def test_uncertain_sends_block_retry_until_user_resolves(client,monkeypatch):
    connect(client);master(client);row=application(client);task=queue(client,row).json()
    def uncertain(*_): raise gmail.DeliveryError('Synthetic connection loss after DATA.',uncertain=True)
    monkeypatch.setattr(agent,'send_message',uncertain);agent.process_task(task['id'])
    assert client.get('/agent/status').json()['tasks'][0]['status']=='unknown'
    assert client.post(f"/agent/tasks/{task['id']}/retry").status_code==409
    assert client.post(f"/agent/tasks/{task['id']}/resolve",json={'result':'not_sent'}).status_code==422
    assert client.post(f"/agent/tasks/{task['id']}/resolve",json={'result':'not_sent','inspected_sent_mail':True}).status_code==200
    assert client.post(f"/agent/tasks/{task['id']}/retry").status_code==200
    calls=sender(monkeypatch);agent.process_task(task['id']);assert len(calls)==1


def test_weekly_cap_counts_reserved_sends(client,monkeypatch):
    connect(client);master(client)
    assert client.put('/workflow/automation',json={'weekly_limit':1}).status_code==200
    first=application(client,'first');second=application(client,'second')
    one=queue(client,first).json();two=queue(client,second).json();calls=sender(monkeypatch)
    agent.process_task(one['id']);agent.process_task(two['id'])
    assert len(calls)==1
    with Session(get_engine()) as db:
        assert db.get(AgentTask,two['id']).status=='queued'
        assert 'Weekly' in db.get(AgentTask,two['id']).error


def test_automatic_rules_bind_recipient_country_master_and_exact_version(client,monkeypatch):
    connect(client);master(client);row=application(client,approve=False)
    result=client.put('/workflow/automation',json={'mode':'automatic','paused':False,'minimum_match':0,'allowed_email_domains':['employer.test']})
    assert result.status_code==200,result.text
    queued=queue(client,row,True);assert queued.status_code==202,queued.text
    with Session(get_engine()) as db:
        approval=db.scalar(select(Approval).where(Approval.application_id==row['id']))
        assert approval.document_id==row['document_id'] and approval.digest==row['document_hash']
    # Removing permission before transfer must stop the queued automatic send.
    client.put('/workflow/automation',json={'mode':'automatic','paused':False,'minimum_match':0,'allowed_email_domains':[]})
    calls=sender(monkeypatch);agent.process_task(queued.json()['id']);assert calls==[]
    assert client.get('/agent/status').json()['tasks'][0]['status']=='cancelled'


def test_master_cv_change_cancels_waiting_submissions(client):
    connect(client);master(client);row=application(client);queued=queue(client,row).json()
    master(client)
    assert client.get('/agent/status').json()['tasks'][0]['status']=='cancelled'
    assert client.get(f"/applications/{row['id']}").json()['status']=='pending_approval'


def test_runtime_demo_endpoint_is_disabled_unless_explicitly_enabled(client,monkeypatch):
    monkeypatch.setenv('JOBPILOT_ENABLE_DEMO','0')
    assert client.get('/jobs/demo').status_code==403


@pytest.mark.parametrize('subject,text,expected',[
    ('Interview invitation','We would like to invite you to an interview.','interview'),
    ('Application update','We are not moving forward with your application.','rejected'),
    ('Next steps','If selected, we will invite you to an interview.','needs_review'),
    ('Application received','Thank you for applying.','acknowledged'),
    ('Application','We cannot invite you to an interview.','needs_review'),
    ('Einladung','Wir möchten Sie zum Vorstellungsgespräch einladen.','interview'),
])
def test_reply_classification_is_conservative(subject,text,expected):
    assert gmail.classify(subject,text)==expected


def test_application_address_detection_never_uses_generic_contact_email():
    assert agent.explicit_application_email('Questions: contact@company.test. Our team builds apps.') is None
    assert agent.explicit_application_email('Apply by email to jobs@company.test')=='jobs@company.test'
    assert agent.explicit_application_email('Do not apply by email to jobs@company.test') is None


@pytest.mark.asyncio
async def test_scheduled_discovery_preparation_and_automatic_email_pipeline(client,monkeypatch):
    from app.models import User
    import app.live_jobs as live
    from app.job_sources import normalize_arbeitnow
    connect(client);master(client)
    client.put('/workflow/automation',json={'mode':'automatic','paused':False,'minimum_match':0,
        'weekly_limit':1,'allowed_email_domains':['employer.test'],'discovery_sources':['arbeitnow']})
    async def feed():
        job=normalize_arbeitnow({'slug':'pipeline','title':'Frontend Engineer','company_name':'Example GmbH',
            'location':'Berlin','url':'https://example.test/jobs/pipeline','remote':True,
            'description':'Build React and TypeScript interfaces. Apply by email to jobs@employer.test.'})
        return {'jobs':[job],'checked_at':datetime.now(timezone.utc).isoformat(),'pages':1,'has_more':False,'notes':[]}
    monkeypatch.setattr(live,'fetch_arbeitnow',feed)
    with Session(get_engine()) as db: user_id=db.scalar(select(User.id))
    result=await agent.discover_and_prepare(user_id,force=True)
    assert result['prepared']==1
    agent.queue_automatic(user_id)
    tasks=client.get('/agent/status').json()['tasks'];assert len(tasks)==1 and tasks[0]['automatic']
    calls=sender(monkeypatch);agent.process_task(tasks[0]['id']);assert len(calls)==1
    assert client.get('/workspace/summary').json()['submitted']==1
    assert (await agent.discover_and_prepare(user_id,force=True))['prepared']==0


def test_imap_matches_actual_message_ids_and_never_marks_read(client,monkeypatch):
    connect(client);master(client);row=application(client);task=queue(client,row).json();calls=sender(monkeypatch)
    agent.process_task(task['id']);sent_id=str(calls[0]['Message-ID'])
    reply=EmailMessage();reply['From']='jobs@employer.test';reply['To']='alex@example.test';reply['Message-ID']='<reply-one@employer.test>'
    reply['In-Reply-To']=sent_id;reply['Subject']='Interview invitation';reply['Date']=formatdate()
    reply.set_content('We would like to invite you to an interview. Please reply with your availability.')
    unrelated=EmailMessage();unrelated['From']='newsletter@other.test';unrelated['Subject']='Unrelated private mail';unrelated.set_content('This body must never be fetched.')
    messages={1:reply.as_bytes(),2:unrelated.as_bytes()};fetched=[]
    class Mailbox:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def login(self,*args): pass
        def select(self,folder,readonly): assert folder=='INBOX' and readonly is True;return 'OK',[b'2']
        def response(self,name): return name,[b'123']
        def uid(self,command,*args):
            if command=='search': return 'OK',[b'1 2']
            assert command=='fetch'
            uid=int(args[0]);selector=args[1];fetched.append((uid,selector))
            assert 'BODY.PEEK' in selector
            raw=messages[uid]
            if 'HEADER.FIELDS' in selector: raw=raw.split(b'\n\n',1)[0]+b'\n\n'
            return 'OK',[(b'header',raw),b')']
    monkeypatch.setattr(gmail.imaplib,'IMAP4_SSL',Mailbox)
    result=client.post('/connections/gmail/sync');assert result.status_code==200,result.text
    assert result.json()['matched_replies']==1
    assert not any(uid==2 and 'HEADER.FIELDS' not in selector for uid,selector in fetched)
    assert client.post('/connections/gmail/sync').json()['matched_replies']==0
    progress=client.get(f"/workflow/applications/{row['id']}/progress").json()
    assert len(progress)==1 and progress[0]['kind']=='interview' and progress[0]['provenance']=='gmail_detected'
    assert client.get('/workspace/summary').json()['interviews']==1


def test_smtp_failure_classification_does_not_expose_auth_secrets(monkeypatch):
    message=EmailMessage();message['From']='alex@example.test';message['To']='jobs@employer.test';message.set_content('Synthetic test')
    class SMTP:
        def __init__(self,*args,**kwargs): assert args[:2]==('smtp.gmail.com',465) and kwargs['context'].check_hostname
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def login(self,*args): pass
        def send_message(self,*args,**kwargs): raise TimeoutError('Network interrupted')
    monkeypatch.setattr(gmail.smtplib,'SMTP_SSL',SMTP)
    with pytest.raises(gmail.DeliveryError) as error:
        gmail.send_message({'email':'alex@example.test','app_password':'abcdefghijklmnop'},message)
    assert error.value.uncertain and 'abcdefghijklmnop' not in str(error.value)


def test_real_application_list_is_paginated_private_and_not_cv_heavy(client):
    master(client);first=application(client,'first',approve=False);second=application(client,'second',approve=False)
    page=client.get('/workspace/applications?limit=1').json()
    assert page['total']==2 and len(page['items'])==1 and 'cv' not in page['items'][0]
    next_page=client.get('/workspace/applications?limit=1&offset=1').json()
    assert page['items'][0]['id']!=next_page['items'][0]['id']
    assert client.get('/workspace/applications?q=no-such-role').json()['total']==0
    client.post('/auth/register',json={'username':'private-other','password':'isolated-test-password-2026'})
    assert client.get('/workspace/applications').json()['total']==0


def test_external_submission_freezes_exact_version_and_stops_duplicate_email(client,monkeypatch):
    from datetime import timedelta
    connect(client);master(client);row=application(client);queued=queue(client,row).json();calls=sender(monkeypatch)
    report={'kind':'submitted','evidence':'User-reported external application confirmation reference APP-123.',
        'received_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),
        **snapshot(row),'exact_documents_confirmed':True}
    result=client.post(f"/workflow/applications/{row['id']}/progress",json=report)
    assert result.status_code==201,result.text
    agent.process_task(queued['id']);assert calls==[]
    current=client.get(f"/applications/{row['id']}").json()
    assert current['status']=='submitted' and current['confirmation']['provider']=='user_reported'
    stats=client.get('/workspace/summary').json()
    assert stats['submitted']==1 and stats['responses']==0


def test_sender_changes_require_a_new_delivery_review(client,monkeypatch):
    connect(client);master(client);row=application(client);queued=queue(client,row).json();calls=sender(monkeypatch)
    assert client.post('/connections/gmail',json={'email':'another@example.test','app_password':'abcdefghijklmnop','allow_send':True,'allow_read':True}).status_code==200
    agent.process_task(queued['id']);assert calls==[]
    assert client.get(f"/applications/{row['id']}").json()['status']=='pending_approval'


def test_word_attachments_and_screening_answers_are_preserved():
    import io
    from docx import Document
    payload={'cv':CV+'\n漢字','cover_letter':'Dear team, please consider my application and the attached CV.',
        'answers':{'Availability':'My confirmed availability'},
        'delivery':{'recipient':'jobs@employer.test','subject':'Application','attachment_format':'docx'}}
    message=agent.compose({'email':'alex@example.test'},payload,'test-task')
    assert 'My confirmed availability' in message.get_body(preferencelist=('plain',)).get_content()
    attachments=list(message.iter_attachments())
    assert attachments[0].get_filename()=='CV.docx'
    document=Document(io.BytesIO(attachments[0].get_payload(decode=True)))
    assert '漢字' in '\n'.join(p.text for p in document.paragraphs)


def test_claude_connection_is_private_and_uses_owned_key(client,monkeypatch):
    import httpx
    import app.ai_connection as ai
    monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False);monkeypatch.delenv('CLAUDE_MODEL',raising=False)
    secret='test-private-claude-key-not-a-real-secret'
    original=httpx.AsyncClient
    def response(request):
        assert request.headers['x-api-key']==secret
        return httpx.Response(200,json={'id':'test-model'})
    monkeypatch.setattr(ai.httpx,'AsyncClient',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(response)))
    result=client.post('/connections/claude',json={'api_key':secret,'model':'test-model'})
    assert result.status_code==200 and result.json()['configured']
    assert secret not in result.text
    with Session(get_engine()) as db: assert secret not in db.scalar(select(Credential).where(Credential.provider=='claude')).encrypted_value
    client.post('/auth/register',json={'username':'another-ai-user','password':'isolated-test-password-2026'})
    assert not client.get('/connections/claude').json()['configured']


def test_version_one_database_upgrade_preserves_records_and_creates_backup(client):
    from sqlalchemy import text
    from app.db import initialize,_migrated,data_directory
    from app.models import User
    engine=get_engine()
    with engine.begin() as connection:
        connection.execute(text('DROP TABLE agent_tasks'))
        connection.execute(text("UPDATE alembic_version SET version_num='0001_local'"))
    _migrated.discard(str(engine.url));initialize()
    with Session(engine) as db: assert db.scalar(select(User.username))=='agent-test'
    backups=list((data_directory()/'backups').glob('*.sqlite3'))
    assert len(backups)==1


def test_queue_integrity_upgrade_preserves_queued_version(client):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text, String
    from app.db import initialize, _migrated
    connect(client); master(client)
    row=application(client); task=queue(client,row).json()
    engine=get_engine()
    with engine.begin() as connection:
        operations=Operations(MigrationContext.configure(connection))
        with operations.batch_alter_table('agent_tasks') as batch:
            batch.alter_column('id',existing_type=String(36),nullable=True)
        connection.execute(text("UPDATE alembic_version SET version_num='0002_agent_queue'"))
    _migrated.discard(str(engine.url)); initialize()
    assert not next(column for column in inspect(engine).get_columns('agent_tasks') if column['name']=='id')['nullable']
    with engine.connect() as connection:
        saved=connection.execute(text('SELECT document_hash,status FROM agent_tasks WHERE id=:id'),{'id':task['id']}).one()
    assert saved.document_hash==row['document_hash'] and saved.status=='queued'
