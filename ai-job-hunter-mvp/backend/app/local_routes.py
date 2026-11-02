"""Owner-scoped, transactional persistence. No submission executor is exposed."""
import hashlib
import json
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy import select, func, update, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .auth import signed_in
from .db import get_session
from .core import PROFILE
from .models import (User, CandidateProfile, CVVersion, ApplicationDraft, DocumentVersion,
                     Approval, AuditEvent, Job, now)

router = APIRouter(tags=['Local records'])


def digest(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def canonical_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, 'Invalid vacancy URL.') from exc
    if parts.scheme not in {'http','https'} or not parts.hostname or parts.username or parts.password:
        raise HTTPException(422, 'Use an HTTP(S) vacancy URL without embedded credentials.')
    query = sorted((k,v) for k,v in parse_qsl(parts.query, keep_blank_values=True)
                   if not k.lower().startswith('utm_') and k.lower() not in {'fbclid','gclid'})
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/') or '/', urlencode(query), ''))


def audit(db, user_id, action, entity_id=None, details=None):
    db.add(AuditEvent(user_id=user_id, action=action, entity_id=entity_id, details=details or {}))


def commit(db):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'A conflicting record already exists. Refresh and retry.') from exc


def own_application(db, user, application_id):
    row = db.scalar(select(ApplicationDraft).where(ApplicationDraft.id == application_id, ApplicationDraft.user_id == user.id))
    if not row:
        raise HTTPException(404, 'Application not found.')
    return row


def own_cv(db, user, version_id):
    row = db.scalar(select(CVVersion).where(CVVersion.id == version_id, CVVersion.user_id == user.id))
    if not row:
        raise HTTPException(404, 'CV version not found.')
    return row


def current_document(db, app):
    row = db.scalar(select(DocumentVersion).where(DocumentVersion.id == app.current_document_id,
                    DocumentVersion.application_id == app.id, DocumentVersion.user_id == app.user_id))
    if not row:
        raise HTTPException(409, 'Application documents are incomplete.')
    return row


def serialize(db, row):
    doc = current_document(db, row)
    approved = db.scalar(select(Approval).where(Approval.application_id == row.id, Approval.user_id == row.user_id,
                         Approval.document_id == doc.id, Approval.decision == 'approved')) if row.status == 'approved' else None
    return {'id':row.id, 'job_external_id':row.job_external_id, 'job_url':row.job_url,
            'job':row.job_snapshot, **doc.payload, 'status':row.status, 'revision':row.revision,
            'document_id':doc.id, 'document_hash':doc.digest, 'created_at':row.created_at,
            'approved_at':approved.created_at if approved else None, 'submitted_at':None, 'confirmation':None}


def new_cv(db, user_id, text, source_name='Pasted CV', facts=None):
    version = (db.scalar(select(func.max(CVVersion.version)).where(CVVersion.user_id == user_id)) or 0) + 1
    row = CVVersion(user_id=user_id, version=version, text=text, digest=digest({'text':text,'facts':facts or {}}),
                    source_name=source_name, facts=facts or {})
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'Another CV version was created. Refresh and retry.') from exc
    return row


def add_document(db, app, cv, cover_letter, answers):
    payload = {'job':app.job_snapshot, 'cv_version':cv.id, 'cv':cv.text,
               'cover_letter':cover_letter, 'answers':answers, 'version':app.revision}
    row = DocumentVersion(application_id=app.id, user_id=app.user_id, cv_version_id=cv.id,
                          version=app.revision, payload=payload, digest=digest(payload))
    db.add(row)
    db.flush()
    app.current_document_id = row.id
    app.updated_at = now()
    return row


class ExperienceInput(BaseModel):
    company: str = Field(default='', max_length=300)
    title: str = Field(default='', max_length=300)
    dates: str = Field(default='', max_length=200)


class TargetsInput(BaseModel):
    titles: list[str] = Field(default_factory=list, max_length=50)
    region: str = Field(default='', max_length=500)
    arrangements: list[str] = Field(default_factory=list, max_length=10)
    weekly_approved_target: str = Field(default='10–15', max_length=30)


class ProfileFacts(BaseModel):
    name: str = Field(default='', max_length=120)
    headline: str = Field(default='', max_length=300)
    location: str = Field(default='', max_length=300)
    experience_summary: str = Field(default='', max_length=3000)
    skills: list[str] = Field(default_factory=list, max_length=100)
    experience: list[ExperienceInput] = Field(default_factory=list, max_length=50)
    projects: list[str] = Field(default_factory=list, max_length=50)
    education: str = Field(default='', max_length=3000)
    targets: TargetsInput = Field(default_factory=TargetsInput)
    unknowns: list[str] = Field(default_factory=list, max_length=50)
    source: str = Field(default='User-reviewed profile', max_length=255)


class ProfileInput(BaseModel):
    profile: ProfileFacts
    preferences: dict = Field(default_factory=dict)

    @field_validator('preferences')
    @classmethod
    def size_limit(cls, value):
        if len(json.dumps(value)) > 60_000:
            raise ValueError('Profile or preferences exceed the supported size.')
        return value


@router.get('/profile')
def profile(user: User = Depends(signed_in), db: Session = Depends(get_session)):
    return db.get(CandidateProfile, user.id).profile


@router.put('/profile')
def save_profile(body: ProfileInput, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    # The authenticated session determines ownership. Never accept a user_id.
    row = db.get(CandidateProfile, user.id)
    row.profile, row.preferences, row.updated_at = body.profile.model_dump(), body.preferences, now()
    audit(db, user.id, 'profile.updated')
    commit(db)
    return {'profile':row.profile, 'preferences':row.preferences}


@router.get('/preferences')
def preferences(user: User = Depends(signed_in), db: Session = Depends(get_session)):
    return db.get(CandidateProfile, user.id).preferences


@router.post('/profile/import-existing')
def import_existing_profile(user: User = Depends(signed_in), db: Session = Depends(get_session)):
    row = db.get(CandidateProfile, user.id)
    row.profile, row.updated_at = json.loads(json.dumps(PROFILE)), now()
    audit(db, user.id, 'profile.imported_existing_fixture')
    commit(db)
    return row.profile


class CVInput(BaseModel):
    text: str = Field(min_length=30, max_length=60_000)
    source_name: str = Field(default='Pasted CV', max_length=255)
    facts: dict = Field(default_factory=dict)


@router.post('/cv/versions', status_code=201)
def create_cv(body: CVInput, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    if len(body.text.strip()) < 30 or len(json.dumps(body.facts)) > 60_000:
        raise HTTPException(422, 'Provide meaningful CV text and bounded facts.')
    row = new_cv(db, user.id, body.text, body.source_name, body.facts)
    audit(db, user.id, 'cv.created', row.id)
    commit(db)
    return {'id':row.id, 'version':row.version, 'hash':row.digest, 'verified':row.verified}


@router.get('/cv/versions')
def cvs(user: User = Depends(signed_in), db: Session = Depends(get_session)):
    return [{'id':r.id,'version':r.version,'source_name':r.source_name,'hash':r.digest,'verified':r.verified,'text':r.text,'facts':r.facts}
            for r in db.scalars(select(CVVersion).where(CVVersion.user_id == user.id).order_by(CVVersion.version.desc()).limit(100))]


class HashInput(BaseModel):
    expected_hash: str = Field(min_length=64, max_length=64)


@router.post('/cv/versions/{version_id}/verify')
def verify_cv(version_id: str, body: HashInput, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    row = own_cv(db, user, version_id)
    if row.digest != body.expected_hash:
        raise HTTPException(409, 'The CV snapshot changed. Review it again.')
    row.verified = True
    audit(db, user.id, 'cv.verified', row.id, {'hash':row.digest})
    commit(db)
    return {'verified':True, 'hash':row.digest}


class DocumentsInput(BaseModel):
    cv_version: str = Field(max_length=100)
    cover_letter: str = Field(default='', max_length=20_000)
    answers: dict[str,str] = Field(default_factory=dict, max_length=60)

    @field_validator('answers')
    @classmethod
    def bounded_answers(cls, value):
        if len(json.dumps(value)) > 60_000:
            raise ValueError('Screening answers exceed the supported size.')
        return value


class PreparedApplication(DocumentsInput):
    job_id: str = Field(min_length=1, max_length=500)
    job_url: HttpUrl


@router.post('/applications/prepare', status_code=201)
def prepare(body: PreparedApplication, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    cv = own_cv(db, user, body.cv_version)
    url = canonical_url(str(body.job_url))
    job = db.scalar(select(Job).where(or_(Job.external_id == body.job_id, Job.canonical_url == url)))
    if not job:
        raise HTTPException(422, 'Discover this job first, or explicitly import a legacy draft.')
    if canonical_url(job.payload['url']) != url:
        raise HTTPException(409, 'The vacancy URL does not match the discovered job.')
    row = ApplicationDraft(user_id=user.id, job_id=job.id, job_external_id=job.external_id,
                           job_url=url, job_snapshot=job.payload, revision=1, status='pending_approval')
    db.add(row)
    try:
        db.flush()
        add_document(db, row, cv, body.cover_letter, body.answers)
        audit(db, user.id, 'application.prepared', row.id)
        commit(db)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'You already have an application for this vacancy.') from exc
    return serialize(db, row)


@router.get('/applications')
def applications(include_demo: bool = False, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    rows = db.scalars(select(ApplicationDraft).where(ApplicationDraft.user_id == user.id).order_by(ApplicationDraft.created_at.desc()).limit(200))
    return [serialize(db, row) for row in rows if include_demo or not row.job_snapshot.get('is_demo')]


@router.get('/applications/{application_id}')
def detail(application_id: str, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    row = own_application(db, user, application_id)
    result = serialize(db, row)
    result['history'] = [{'action':e.action, 'at':e.created_at, 'details':e.details} for e in db.scalars(
        select(AuditEvent).where(AuditEvent.user_id == user.id, AuditEvent.entity_id == row.id).order_by(AuditEvent.created_at))]
    return result


class DecisionInput(HashInput):
    expected_document_id: str = Field(max_length=100)


def check_snapshot(db, row, body):
    doc = current_document(db, row)
    if doc.id != body.expected_document_id or doc.digest != body.expected_hash or digest(doc.payload) != doc.digest:
        raise HTTPException(409, 'Documents changed. Review the exact current snapshot before deciding.')
    return doc


@router.post('/applications/{application_id}/approve')
def approve(application_id: str, body: DecisionInput, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    row = own_application(db, user, application_id)
    doc = check_snapshot(db, row, body)
    if not own_cv(db, user, doc.cv_version_id).verified:
        raise HTTPException(409, 'Verify this exact source CV version before approving.')
    changed = db.execute(update(ApplicationDraft).where(ApplicationDraft.id == row.id, ApplicationDraft.user_id == user.id,
                         ApplicationDraft.current_document_id == doc.id, ApplicationDraft.status == 'pending_approval',
                         ApplicationDraft.revision == row.revision).values(status='approved', updated_at=now()))
    if changed.rowcount != 1:
        raise HTTPException(409, 'This application is no longer pending approval.')
    db.add(Approval(application_id=row.id, user_id=user.id, document_id=doc.id, digest=doc.digest, decision='approved'))
    audit(db, user.id, 'application.approved', row.id, {'document_id':doc.id,'hash':doc.digest})
    commit(db)
    db.refresh(row)
    return {'approved':True,'submitted':False,'application':serialize(db,row)}


class RevisionInput(DocumentsInput, DecisionInput): pass


@router.put('/applications/{application_id}/documents')
def revise(application_id: str, body: RevisionInput, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    row = own_application(db, user, application_id)
    doc = check_snapshot(db, row, body)
    if row.status == 'submitted':
        raise HTTPException(409, 'Submitted applications cannot be edited.')
    cv = own_cv(db, user, body.cv_version)
    old_revision = row.revision
    result = db.execute(update(ApplicationDraft).where(ApplicationDraft.id == row.id, ApplicationDraft.user_id == user.id,
                         ApplicationDraft.current_document_id == doc.id, ApplicationDraft.revision == old_revision)
                         .values(revision=old_revision+1,status='pending_approval',updated_at=now()))
    if result.rowcount != 1:
        raise HTTPException(409, 'Another edit occurred. Reload the application.')
    db.refresh(row)
    add_document(db, row, cv, body.cover_letter, body.answers)
    audit(db, user.id, 'application.revised_approval_invalidated', row.id, {'previous_document_id':doc.id,'version':row.revision})
    commit(db)
    return serialize(db, row)


class OtherDecision(DecisionInput):
    decision: str = Field(pattern=r'^(rejected|changes_requested)$')


@router.post('/applications/{application_id}/decision')
def decide(application_id: str, body: OtherDecision, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    row = own_application(db, user, application_id)
    doc = check_snapshot(db, row, body)
    if row.status != 'pending_approval':
        raise HTTPException(409, 'Only a pending application can receive a review decision.')
    changed = db.execute(update(ApplicationDraft).where(ApplicationDraft.id == row.id,
                         ApplicationDraft.user_id == user.id, ApplicationDraft.current_document_id == doc.id,
                         ApplicationDraft.status == 'pending_approval', ApplicationDraft.revision == row.revision)
                         .values(status=body.decision,updated_at=now()))
    if changed.rowcount != 1:
        raise HTTPException(409, 'Another review or edit occurred. Reload the application.')
    db.add(Approval(user_id=user.id, application_id=row.id, document_id=doc.id, digest=doc.digest, decision=body.decision))
    audit(db, user.id, f'application.{body.decision}', row.id, {'document_id':doc.id})
    commit(db)
    return serialize(db, row)


class LegacyDraft(BaseModel):
    job: dict
    cv: str = Field(min_length=30, max_length=60_000)
    letter: str = Field(default='', max_length=20_000)
    answers: str | dict[str,str] = ''
    status: str = Field(default='pending_approval', max_length=40)


class LegacyImport(BaseModel):
    drafts: list[LegacyDraft] = Field(max_length=100)


@router.post('/migration/browser-drafts')
def import_drafts(body: LegacyImport, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    imported, skipped = [], 0
    # Validate all records before the first write, so a failed batch changes nothing.
    for entry in body.drafts:
        if not isinstance(entry.job.get('id'), str) or not entry.job['id'] or len(json.dumps(entry.job)) > 60_000 or len(json.dumps(entry.answers)) > 60_000:
            raise HTTPException(422, 'Each legacy draft needs a bounded job snapshot with an original job ID.')
        canonical_url(entry.job.get('url',''))
    for entry in body.drafts:
        url = canonical_url(entry.job['url'])
        if db.scalar(select(ApplicationDraft.id).where(ApplicationDraft.user_id == user.id,
                      or_(ApplicationDraft.job_external_id == entry.job['id'], ApplicationDraft.job_url == url))):
            skipped += 1
            continue
        cv = new_cv(db, user.id, entry.cv, 'Imported browser draft')
        snapshot = dict(entry.job)
        snapshot['is_demo'] = bool(snapshot.get('is_demo') or snapshot.get('source') == 'demo')
        row = ApplicationDraft(user_id=user.id, job_external_id=snapshot['id'], job_url=url, job_snapshot=snapshot,
                               revision=1,status='pending_approval')
        db.add(row)
        db.flush()
        add_document(db, row, cv, entry.letter, entry.answers if isinstance(entry.answers,dict) else {'imported_notes':entry.answers})
        audit(db, user.id, 'application.imported_unapproved', row.id, {'legacy_status':entry.status})
        imported.append(row.id)
    commit(db)
    return {'imported_ids':imported,'skipped_duplicates':skipped,'approvals_imported':0}
