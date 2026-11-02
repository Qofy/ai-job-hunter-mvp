from concurrent.futures import ThreadPoolExecutor
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.main import app
from app.db import initialize, get_engine, data_directory, REPOSITORY, _migrated
from app.models import User, Approval, DocumentVersion, CVVersion, Session as LoginSession

CV = 'Test Candidate\nFrontend Engineer\n\nSKILLS\nReact, TypeScript, Vue\n\nEXPERIENCE\nSoftware project development 2024-2025'


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def account(client, name='alice'):
    response = client.post('/auth/register',json={'username':name,'password':'test-only-long-password','display_name':name.title()})
    assert response.status_code == 201, response.text
    result = response.json()
    return {'Authorization':f"Bearer {result['access_token']}"}, result['user']


def version(client, headers, verify=True):
    response = client.post('/cv/versions',headers=headers,json={'text':CV,'facts':{'skills':['React','TypeScript','Vue']}})
    assert response.status_code == 201, response.text
    value = response.json()
    if verify:
        assert client.post(f"/cv/versions/{value['id']}/verify",headers=headers,json={'expected_hash':value['hash']}).status_code == 200
    return value


def prepared(client, headers, verify=True):
    cv = version(client, headers, verify)
    job = client.get('/jobs/demo',headers=headers).json()[0]
    response = client.post('/applications/prepare',headers=headers,json={'cv_version':cv['id'],'job_id':job['id'],'job_url':job['url']})
    assert response.status_code == 201, response.text
    return response.json()


def decision(row):
    return {'expected_document_id':row['document_id'],'expected_hash':row['document_hash']}


def test_migration_foreign_keys_indexes_and_restart():
    engine = initialize()
    assert initialize() is engine
    tables = inspect(engine).get_table_names()
    assert len(tables) == 16  # 15 domain tables plus Alembic's version table.
    assert inspect(engine).get_indexes('sessions')
    with engine.connect() as connection:
        assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
        assert connection.exec_driver_sql('PRAGMA journal_mode').scalar() == 'wal'
        assert connection.execute(text('select version_num from alembic_version')).scalar() == '0001_local'
    assert not data_directory().is_relative_to(REPOSITORY)
    assert (data_directory() / 'files').is_dir()


def test_data_directory_rejects_source_checkout(monkeypatch):
    monkeypatch.setenv('JOBPILOT_DATA_DIR',str(REPOSITORY / 'must-not-create'))
    with pytest.raises(RuntimeError,match='outside'):
        data_directory()
    assert not (REPOSITORY / 'must-not-create').exists()


def test_registration_password_hash_cookie_and_logout(client):
    headers,user = account(client)
    assert 'password' not in str(user)
    with Session(get_engine()) as db:
        stored = db.get(User,user['id']).password_hash
        assert stored.startswith('scrypt$') and 'test-only-long-password' not in stored
    assert client.get('/auth/me').json()['id'] == user['id']
    cookie = client.cookies.get('jobpilot_session')
    assert cookie
    assert client.post('/auth/logout',headers=headers).status_code == 200
    assert client.get('/auth/me',headers=headers).status_code == 401
    assert client.get('/auth/me').status_code == 401
    response = client.post('/auth/login',json={'username':'ALICE','password':'test-only-long-password'})
    assert response.status_code == 200
    assert 'httponly' in response.headers['set-cookie'].lower()
    assert 'samesite=strict' in response.headers['set-cookie'].lower()


def test_unauthenticated_private_routes_are_closed(client):
    for path in ['/profile','/preferences','/applications','/cv/versions','/jobs/demo']:
        assert client.get(path).status_code == 401
    assert client.post('/cv/analyze',json={'cv':CV,'job_description':CV}).status_code == 401


def test_expired_session_requires_fresh_login(client):
    headers,_ = account(client)
    with Session(get_engine()) as db:
        db.execute(update(LoginSession).values(expires_at=time.time()-1))
        db.commit()
    assert client.get('/auth/me',headers=headers).status_code == 401
    assert client.get('/profile',headers=headers).status_code == 401


def test_failed_source_returns_an_error_without_fabricated_jobs(client,monkeypatch):
    headers,_ = account(client)
    import app.main as main
    async def failed(_):
        raise TimeoutError('test failure')
    monkeypatch.setattr(main,'greenhouse_jobs',failed)
    response = client.get('/jobs/greenhouse/example',headers=headers)
    assert response.status_code == 502
    assert 'unavailable' in response.json()['detail']
    assert client.get('/applications',headers=headers).json() == []


def test_profiles_cvs_and_preferences_are_isolated(client):
    alice,a = account(client)
    bob,b = account(client,'bob')
    assert client.put('/profile',headers=alice,json={'profile':{'name':'Alice','skills':['React','Vue']},'preferences':{'countries':['Ghana']}}).status_code == 200
    cv = version(client,alice)
    assert client.get('/profile',headers=bob).json()['name'] == 'Bob'
    assert client.get('/preferences',headers=bob).json() == {}
    assert client.get('/cv/versions',headers=bob).json() == []
    assert client.post(f"/cv/versions/{cv['id']}/verify",headers=bob,json={'expected_hash':cv['hash']}).status_code == 404
    assert client.get('/profile',headers=alice,params={'user_id':b['id']}).json()['name'] == 'Alice'
    assert client.get('/preferences',headers=alice).json()['countries'] == ['Ghana']
    assert client.get('/profile',headers=alice).json()['skills'] == ['React','Vue']


def test_matching_uses_current_user_and_real_profile(client):
    alice,_ = account(client)
    bob,_ = account(client,'bob')
    client.put('/profile',headers=alice,json={'profile':{'name':'Alice','skills':['React','TypeScript']}})
    client.put('/profile',headers=bob,json={'profile':{'name':'Bob','skills':['Python']}})
    a = client.get('/jobs/demo',headers=alice).json()
    b = client.get('/jobs/demo',headers=bob).json()
    assert a[0]['match']['matched_skills'] == ['React','TypeScript']
    assert b[0]['match']['matched_skills'] == []
    assert all(j['is_demo'] for j in a+b)


def test_cross_user_application_access_and_cv_spoofing_fail(client):
    alice,_ = account(client)
    row = prepared(client,alice)
    bob,_ = account(client,'bob')
    assert client.get('/applications',headers=bob,params={'include_demo':True}).json() == []
    assert client.get(f"/applications/{row['id']}",headers=bob).status_code == 404
    assert client.post(f"/applications/{row['id']}/approve",headers=bob,json=decision(row)).status_code == 404
    assert client.post('/applications/prepare',headers=bob,json={'cv_version':row['cv_version'],'job_id':row['job']['id'],'job_url':row['job_url']}).status_code == 404


def test_approval_requires_verified_cv_and_exact_hash(client):
    headers,_ = account(client)
    row = prepared(client,headers,False)
    url = f"/applications/{row['id']}/approve"
    assert client.post(url,headers=headers,json=decision(row)).status_code == 409
    cv = client.get('/cv/versions',headers=headers).json()[0]
    client.post(f"/cv/versions/{cv['id']}/verify",headers=headers,json={'expected_hash':cv['hash']})
    assert client.post(url,headers=headers,json={**decision(row),'expected_hash':'0'*64}).status_code == 409
    assert client.post(url,headers=headers).status_code == 422
    result = client.post(url,headers=headers,json=decision(row))
    assert result.status_code == 200 and result.json()['submitted'] is False
    assert result.json()['application']['confirmation'] is None
    assert client.post(url,headers=headers,json=decision(row)).status_code == 409


def test_edits_invalidate_approval_and_preserve_immutable_history(client):
    headers,_ = account(client)
    row = prepared(client,headers)
    client.post(f"/applications/{row['id']}/approve",headers=headers,json=decision(row))
    changed = client.put(f"/applications/{row['id']}/documents",headers=headers,json={**decision(row),'cv_version':row['cv_version'],'cover_letter':'Updated, user-authored cover letter.'})
    assert changed.status_code == 200, changed.text
    new = changed.json()
    assert new['status'] == 'pending_approval' and new['approved_at'] is None
    assert new['document_hash'] != row['document_hash'] and new['revision'] == 2
    assert client.post(f"/applications/{row['id']}/approve",headers=headers,json=decision(row)).status_code == 409
    assert client.post(f"/applications/{row['id']}/approve",headers=headers,json=decision(new)).status_code == 200
    with Session(get_engine()) as db:
        assert len(db.scalars(select(Approval)).all()) == 2
        assert len(db.scalars(select(DocumentVersion)).all()) == 2
        with pytest.raises(IntegrityError,match='immutable'):
            db.execute(update(DocumentVersion).where(DocumentVersion.id==row['document_id']).values(digest='0'*64))
        db.rollback()
        with pytest.raises(IntegrityError,match='new CV version'):
            db.execute(update(CVVersion).values(text='tampered CV'))


def test_duplicate_urls_and_demo_separation(client):
    headers,_ = account(client)
    row = prepared(client,headers)
    duplicate = client.post('/applications/prepare',headers=headers,json={'cv_version':row['cv_version'],'job_id':row['job']['id'],'job_url':row['job_url']+'?utm_source=duplicate#fragment'})
    assert duplicate.status_code == 409
    assert client.get('/applications',headers=headers).json() == []
    assert len(client.get('/applications?include_demo=true',headers=headers).json()) == 1


def test_legacy_import_is_transactional_idempotent_and_never_imports_approval(client):
    headers,_ = account(client)
    legacy = {'job':{'id':'legacy-1','url':'https://example.com/role','title':'Imported role','is_demo':False},'cv':CV,'status':'approved','letter':'original letter','answers':'Original screening notes','approval':{'hash':'untrusted'}}
    bad = {**legacy,'job':{'id':'bad','url':'javascript:alert(1)'}}
    assert client.post('/migration/browser-drafts',headers=headers,json={'drafts':[legacy,bad]}).status_code == 422
    assert client.get('/applications',headers=headers).json() == []
    response = client.post('/migration/browser-drafts',headers=headers,json={'drafts':[legacy]})
    assert response.status_code == 200 and response.json()['approvals_imported'] == 0
    row = client.get('/applications',headers=headers).json()[0]
    assert row['status'] == 'pending_approval' and row['cv'] == CV
    assert row['answers']['imported_notes'] == legacy['answers']
    assert client.post(f"/applications/{row['id']}/approve",headers=headers,json=decision(row)).status_code == 409
    repeat = client.post('/migration/browser-drafts',headers=headers,json={'drafts':[legacy]}).json()
    assert repeat['skipped_duplicates'] == 1 and repeat['imported_ids'] == []


def test_sessions_and_documents_survive_connection_restart(client):
    headers,_ = account(client)
    row = prepared(client,headers)
    get_engine().dispose()
    _migrated.clear()
    with TestClient(app) as restarted:
        result = restarted.get(f"/applications/{row['id']}",headers=headers)
        assert result.status_code == 200 and result.json()['document_hash'] == row['document_hash']


def test_untrusted_write_origin_and_no_submission_executor(client):
    assert client.post('/auth/register',headers={'Origin':'https://untrusted.example'},json={'username':'attacker','password':'long-test-password'}).status_code == 403
    headers,_ = account(client)
    row = prepared(client,headers)
    assert client.post(f"/applications/{row['id']}/submit",headers=headers).status_code == 404


def test_concurrent_approval_records_at_most_one_decision(client):
    headers,_ = account(client)
    row = prepared(client,headers)
    def approve(_):
        with TestClient(app) as parallel:
            return parallel.post(f"/applications/{row['id']}/approve",headers=headers,json=decision(row)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(approve,range(2)))
    assert statuses.count(200) == 1
    assert all(status in {200,409,503} for status in statuses)
    with Session(get_engine()) as db:
        assert len(db.scalars(select(Approval)).all()) == 1
