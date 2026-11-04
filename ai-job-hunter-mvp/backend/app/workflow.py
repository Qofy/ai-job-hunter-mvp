"""Local application workflow. Actual submission connectors must supply evidence."""
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from .auth import signed_in
from .db import get_session
from .models import CandidateProfile, User, ApplicationDraft, RecruiterResponse, Job, AgentTask, now
from .document_studio import Documents, version_hash
from .local_routes import canonical_url, digest, new_cv, add_document, serialize, own_application, audit, commit

router=APIRouter(prefix='/workflow',tags=['Local application workflow'])


class AutomationPolicy(BaseModel):
    mode: Literal['review','automatic'] = 'review'
    paused: bool = True
    weekly_limit: int = Field(default=12,ge=1,le=15)
    minimum_match: int = Field(default=70,ge=0,le=100)
    reviewed_facts_only: bool = True
    allowed_email_domains: list[str] = Field(default_factory=list,max_length=100)
    use_claude: bool = False
    cloud_consent: bool = False
    discovery_sources: list[Literal['arbeitnow','germantechjobs']] = Field(default_factory=lambda:['arbeitnow','germantechjobs'],max_length=2)
    attachment_format: Literal['pdf','docx'] = 'pdf'

    @field_validator('allowed_email_domains')
    @classmethod
    def domains(cls,values):
        import re
        output=[]
        for value in values:
            value=value.strip().lower()
            if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}',value):
                raise ValueError('Use employer email domains such as company.de, without @ or wildcards.')
            if value in {'gmail.com','yahoo.com','hotmail.com','outlook.com','live.com','aol.com'}:
                raise ValueError('Shared personal email domains need per-application review; use employer domains for automatic mode.')
            if value not in output: output.append(value)
        return output


def policy_response(row):
    stored=row.preferences.get('automation',{})
    policy=AutomationPolicy(**stored)
    from .gmail import status
    from .db import get_engine
    with Session(get_engine()) as db: gmail=status(db,row.user_id)
    blockers=[]
    if not gmail['can_send']: blockers.append('Connect Gmail with sending enabled to send email applications.')
    if not gmail['can_sync']: blockers.append('Connect Gmail with reply tracking enabled to detect recruiter replies.')
    if policy.mode=='automatic' and not policy.allowed_email_domains: blockers.append('Add allowed employer email domains before automatic email submission.')
    if not row.preferences.get('master_cv_id'): blockers.append('Save and verify your master CV in My profile before scheduled drafting.')
    if policy.use_claude and not policy.cloud_consent: blockers.append('Consent to Claude processing before enabling AI drafts.')
    if policy.use_claude:
        from .ai_connection import configuration
        try:
            ai=configuration(row.user_id)
            if not ai['key'] or not ai['model']: blockers.append('Connect the optional Claude API, or choose local source-preserving drafts.')
        except HTTPException: blockers.append('Reconnect your Claude API settings, or choose local drafts.')
    return {'policy':policy.model_dump(),'submission_ready':gmail['can_send'],'response_tracking_ready':gmail['can_sync'],
            'blockers':blockers,'local_only':True,'submission_channel':'email_only'}


@router.get('/automation')
def automation(user:User=Depends(signed_in),db:Session=Depends(get_session)):
    return policy_response(db.get(CandidateProfile,user.id))


@router.put('/automation')
def save_automation(body:AutomationPolicy,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    if not body.reviewed_facts_only:
        raise HTTPException(422,'Automatic generation must use reviewed candidate facts.')
    row=db.get(CandidateProfile,user.id)
    previous=AutomationPolicy(**row.preferences.get('automation',{}))
    if previous.mode=='automatic' and body.mode=='review':
        for task in db.scalars(select(AgentTask).where(AgentTask.user_id==user.id,AgentTask.automatic.is_(True),AgentTask.status=='queued')):
            task.status='cancelled';task.error='Switched to review mode. Approve the exact version before sending.';task.updated_at=now()
            application=db.get(ApplicationDraft,task.application_id)
            if application.status=='approved': application.status='pending_approval'
    row.preferences={**row.preferences,'automation':body.model_dump()}
    row.updated_at=now()
    audit(db,user.id,'automation.policy_updated',details=body.model_dump())
    commit(db)
    return policy_response(row)


class SaveDocuments(Documents):
    reviewed_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    job_url: HttpUrl
    job_title: str = Field(min_length=1,max_length=500)
    company: str = Field(min_length=1,max_length=300)
    discovered_job_id: str | None = Field(default=None,max_length=500)


@router.post('/applications',status_code=201)
def save_application(body:SaveDocuments,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    if not body.job_title.strip() or not body.company.strip():
        raise HTTPException(422,'Provide the role title and employer.')
    if version_hash(body)!=body.reviewed_hash:
        raise HTTPException(409,'Documents or job changed. Check and review the current version again.')
    if len(body.cv_draft.strip())<30: raise HTTPException(422,'The CV draft needs at least 30 characters.')
    url=canonical_url(str(body.job_url))
    if db.scalar(select(ApplicationDraft.id).where(ApplicationDraft.user_id==user.id,ApplicationDraft.job_url==url)):
        raise HTTPException(409,'You already saved an application for this vacancy. Review it in Applications.')
    discovered=db.scalar(select(Job).where(Job.external_id==body.discovered_job_id)) if body.discovered_job_id else None
    if body.discovered_job_id and (not discovered or canonical_url(discovered.payload['url'])!=url):
        raise HTTPException(409,'The selected discovered job does not match this URL.')
    snapshot={**(discovered.payload if discovered else {}),'id':discovered.external_id if discovered else 'pasted:'+digest({'url':url})[:24],
              'title':body.job_title.strip(),'company':body.company.strip(),'url':url,'description':body.job_description,
              'source':discovered.source if discovered else 'user_provided','is_demo':discovered.is_demo if discovered else False,
              'location':discovered.payload.get('location','Not specified') if discovered else 'Not specified',
              'workplace_type':discovered.payload.get('workplace_type','Unspecified') if discovered else 'Unspecified',
              'description_provenance':'User-reviewed text'}
    cv=new_cv(db,user.id,body.cv_draft,'Reviewed document studio draft',{'source_cv':body.cv,'reviewed_document_hash':body.reviewed_hash})
    cv.verified=True
    row=ApplicationDraft(user_id=user.id,job_id=discovered.id if discovered else None,
                         job_external_id=snapshot['id'],job_url=url,job_snapshot=snapshot,revision=1,status='pending_approval')
    db.add(row)
    db.flush()
    add_document(db,row,cv,body.cover_letter,{})
    audit(db,user.id,'application.saved_from_documents',row.id,{'reviewed_document_hash':body.reviewed_hash})
    commit(db)
    return serialize(db,row)


class ReportedProgress(BaseModel):
    kind: Literal['submitted','rejected','interview','offer','withdrawn']
    evidence: str = Field(min_length=10,max_length=10000)
    received_at: datetime
    expected_document_id: str | None = Field(default=None,max_length=100)
    expected_hash: str | None = Field(default=None,pattern=r'^[a-f0-9]{64}$')
    exact_documents_confirmed: bool = False


@router.post('/applications/{application_id}/progress',status_code=201)
def record_progress(application_id:str,body:ReportedProgress,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    row=own_application(db,user,application_id)
    if row.job_snapshot.get('is_demo'): raise HTTPException(422,'Demo applications cannot have real progress records.')
    if body.received_at.tzinfo is None: raise HTTPException(422,'Include the timezone for the evidence timestamp.')
    if body.received_at>datetime.now(timezone.utc): raise HTTPException(422,'Progress evidence cannot be dated in the future.')
    evidence=body.evidence.strip()
    if len(evidence)<10: raise HTTPException(422,'Provide meaningful evidence, such as a confirmation or recruiter message.')
    from .local_routes import check_snapshot,DecisionInput
    external=body.kind=='submitted' and body.exact_documents_confirmed
    if external:
        from .local_routes import ensure_not_sending
        ensure_not_sending(db,row)
        if not body.expected_document_id or not body.expected_hash: raise HTTPException(422,'Identify the exact document version used for the external submission.')
        check_snapshot(db,row,DecisionInput(expected_document_id=body.expected_document_id,expected_hash=body.expected_hash))
    stored_kind='external_submitted' if external else body.kind
    signature=digest({'kind':body.kind,'evidence':evidence,'at':body.received_at.isoformat()})
    if db.scalar(select(RecruiterResponse.id).where(RecruiterResponse.user_id==user.id,
        RecruiterResponse.application_id==row.id,RecruiterResponse.kind==stored_kind,
        RecruiterResponse.evidence==evidence,RecruiterResponse.received_at==body.received_at.isoformat())):
        raise HTTPException(409,'This progress evidence has already been recorded.')
    record=RecruiterResponse(user_id=user.id,application_id=row.id,kind=stored_kind,evidence=evidence,
                             verified_at=None,received_at=body.received_at.isoformat())
    db.add(record)
    if external:
        row.status='submitted';row.updated_at=now()
        for task in db.scalars(select(AgentTask).where(AgentTask.application_id==row.id,AgentTask.status=='queued')):
            task.status='cancelled';task.error='External submission reported; duplicate email submission was prevented.';task.updated_at=now()
    audit(db,user.id,'application.progress_reported',row.id,{'kind':body.kind,'evidence_hash':signature,'provenance':'user_reported',
        'document_id':row.current_document_id,'exact_documents_confirmed':body.exact_documents_confirmed})
    commit(db)
    return {'recorded':True,'provenance':'user_reported','verified':False}


@router.get('/applications/{application_id}/progress')
def progress(application_id:str,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    row=own_application(db,user,application_id)
    import json
    output=[]
    for item in db.scalars(select(RecruiterResponse).where(RecruiterResponse.application_id==row.id,
        RecruiterResponse.user_id==user.id).order_by(RecruiterResponse.received_at.desc())):
        is_mail=item.kind.startswith('mail_')
        evidence=item.evidence
        if is_mail:
            try:
                message=json.loads(evidence)
                evidence=f"From: {message.get('from','')}\nSubject: {message.get('subject','')}\nMessage-ID: {message.get('message_id','')}\n\n{message.get('text','')}"
            except ValueError: pass
        output.append({'id':item.id,'kind':'submitted' if item.kind=='external_submitted' else item.kind.removeprefix('mail_'),'evidence':evidence,'received_at':item.received_at,
             'provenance':'gmail_detected' if is_mail else 'user_reported','verified':False})
    return output
