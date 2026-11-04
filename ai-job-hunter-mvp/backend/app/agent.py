"""Durable email submission, conservative scheduled discovery and reply tracking."""
import asyncio
import json
import os
import re
import threading
import hashlib
from contextlib import suppress
from datetime import datetime,timezone,timedelta
from email.message import EmailMessage
from email.utils import formatdate
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select,update,func
from sqlalchemy.orm import Session
from .auth import signed_in
from .db import get_session,initialize,data_directory
from .models import (User,CandidateProfile,CVVersion,ApplicationDraft,DocumentVersion,Approval,
                     SubmissionAttempt,AgentTask,JobSource,AuditEvent,RecruiterResponse,now)
from .local_routes import (own_application,own_cv,current_document,check_snapshot,DecisionInput,
    canonical_url,add_document,new_cv,serialize,digest,audit,commit,ensure_not_sending)
from .gmail import credential,status as gmail_status,valid_address,send_message,DeliveryError,sync_mail
from .document_studio import pdf_bytes,docx_bytes

router=APIRouter(prefix='/agent',tags=['Local job agent'])
_cycle_lock=asyncio.Lock()
_background=set()


def schedule(coroutine):
    task=asyncio.create_task(coroutine)
    _background.add(task)
    task.add_done_callback(_background.discard)


def week_start():
    current=datetime.now(timezone.utc)
    return (current-timedelta(days=current.weekday())).replace(hour=0,minute=0,second=0,microsecond=0).isoformat()


def policy(db,user_id):
    from .workflow import AutomationPolicy
    return AutomationPolicy(**db.get(CandidateProfile,user_id).preferences.get('automation',{}))


def task_json(task):
    return {key:getattr(task,key) for key in ['id','application_id','document_id','document_hash','status','automatic','error','created_at','updated_at']}


class DeliveryInput(DecisionInput):
    recipient: str = Field(max_length=254)
    subject: str = Field(min_length=3,max_length=200)
    accepts_email: bool = False
    eligibility_confirmed: bool = False
    attachment_format: str = Field(default='pdf',pattern='^(pdf|docx)$')

    @field_validator('recipient')
    @classmethod
    def recipient_address(cls,value): return valid_address(value.strip())

    @field_validator('subject')
    @classmethod
    def no_headers(cls,value):
        if any(ord(c)<32 for c in value): raise ValueError('Use a subject without control characters.')
        return value.strip()


@router.put('/applications/{application_id}/delivery')
def set_delivery(application_id:str,body:DeliveryInput,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    row=own_application(db,user,application_id);ensure_not_sending(db,row)
    if row.status=='submitted' or row.job_snapshot.get('is_demo'): raise HTTPException(409,'Submitted or demo applications cannot be configured for delivery.')
    old=check_snapshot(db,row,body)
    if not body.accepts_email: raise HTTPException(422,'Confirm that this vacancy explicitly accepts applications at this address.')
    if not body.eligibility_confirmed: raise HTTPException(422,'Confirm the location, eligibility and required application information for this job.')
    delivery={'recipient':body.recipient,'subject':body.subject,'accepts_email':True,'eligibility_confirmed':True,'sender':gmail_status(db,user.id).get('email'),
              'attachment_format':body.attachment_format,'template_version':'a4-text-v1'}
    result=db.execute(update(ApplicationDraft).where(ApplicationDraft.id==row.id,
        ApplicationDraft.current_document_id==old.id,ApplicationDraft.revision==row.revision).values(
        revision=row.revision+1,status='pending_approval',updated_at=now()))
    if result.rowcount!=1: raise HTTPException(409,'Application changed. Reload before configuring delivery.')
    db.refresh(row)
    add_document(db,row,own_cv(db,user,old.cv_version_id),old.payload.get('cover_letter',''),old.payload.get('answers',{}),delivery)
    db.execute(update(AgentTask).where(AgentTask.application_id==row.id,AgentTask.status=='queued').values(status='cancelled',error='Documents changed.',updated_at=now()))
    audit(db,user.id,'application.delivery_changed_approval_invalidated',row.id,{'document_id':row.current_document_id})
    commit(db)
    return serialize(db,row)


class QueueInput(DecisionInput):
    automatic: bool = False


def automatic_checks(db,user,row,doc,settings):
    from .core import match_job
    from .models import Job
    if settings.mode!='automatic' or settings.paused: raise HTTPException(409,'Automatic mode is paused or disabled.')
    delivery=doc.payload.get('delivery',{})
    if delivery.get('recipient','').rsplit('@',1)[-1].lower() not in settings.allowed_email_domains:
        raise HTTPException(409,'This employer email domain is not allowed by your automatic policy.')
    candidate=db.get(CandidateProfile,user.id);profile=candidate.profile
    if not row.job_snapshot.get('country') or row.job_snapshot['country'] not in profile.get('work_authorization_countries',[]):
        raise HTTPException(409,'Country and work authorization need per-application review.')
    cv=own_cv(db,user,doc.cv_version_id)
    if cv.facts.get('master_cv_id') and cv.facts['master_cv_id']!=candidate.preferences.get('master_cv_id'):
        raise HTTPException(409,'This draft uses an older master CV and needs review.')
    match=match_job(row.job_snapshot,{**profile,'skills':profile.get('skills',[])})
    if match['score']<settings.minimum_match: raise HTTPException(409,'The match is below your automatic submission threshold.')
    description=row.job_snapshot.get('description','')
    human_review=db.scalar(select(AuditEvent.id).where(AuditEvent.user_id==user.id,AuditEvent.entity_id==row.id,
        AuditEvent.action=='application.approved',AuditEvent.details['document_id'].as_string()==doc.id))
    if not human_review and re.search(r'(?:please|must|required|include|state|provide|send|attach|answer).{0,90}(?:salary expectations?|notice period|earliest start|availability|visa status|portfolio|certificates?|references?|screening questions?)|gehaltsvorstellung|eintrittstermin|kündigungsfrist|zeugnisse|arbeitsprobe',description,re.I|re.S):
        raise HTTPException(409,'This job requests extra information or documents. Review its requirements and answers before sending.')
    senior_target=any(any(word in title.lower() for word in ['senior','staff','principal','lead','head','director']) for title in profile.get('targets',{}).get('titles',[]))
    if any('seniority' in flag for flag in match['flags']) and not senior_target:
        raise HTTPException(409,'The seniority requirements need manual review.')
    record=db.get(Job,row.job_id) if row.job_id else None
    source=db.scalar(select(JobSource).where(JobSource.user_id==user.id,JobSource.kind==row.job_snapshot.get('source'),JobSource.identifier=='public-feed'))
    if not record or not source or source.last_error or record.id not in source.config.get('job_ids',[]) or not source.last_success_at or datetime.now(timezone.utc)>datetime.fromisoformat(source.last_success_at)+timedelta(hours=2):
        raise HTTPException(409,'The vacancy needs a fresh source check before automatic sending.')


def queue_application(db,user,row,automatic=False):
    doc=current_document(db,row)
    settings=policy(db,user.id)
    connection=gmail_status(db,user.id)
    if not connection['can_send']: raise HTTPException(409,'Connect Gmail with sending enabled first.')
    if row.job_snapshot.get('is_demo'): raise HTTPException(422,'Demo applications can never be submitted.')
    if row.status=='submitted': raise HTTPException(409,'This application was already submitted.')
    ensure_not_sending(db,row)
    delivery=doc.payload.get('delivery',{})
    if not delivery.get('accepts_email') or not delivery.get('eligibility_confirmed'):
        raise HTTPException(409,'Confirm the application email address and job eligibility first.')
    if delivery.get('sender')!=connection.get('email'):
        raise HTTPException(409,'The Gmail sender changed or was not connected when delivery was reviewed. Save the destination again and review that version.')
    if len(doc.payload.get('cv','').strip())<30 or len(doc.payload.get('cover_letter','').strip())<30:
        raise HTTPException(409,'Review a complete CV and cover letter before submission.')
    if not own_cv(db,user,doc.cv_version_id).verified: raise HTTPException(409,'Verify the source CV before submission.')
    if automatic:
        automatic_checks(db,user,row,doc,settings)
        if row.status=='pending_approval':
            db.add(Approval(application_id=row.id,user_id=user.id,document_id=doc.id,digest=doc.digest,decision='approved'))
            row.status='approved'
            audit(db,user.id,'application.authorized_by_policy',row.id,{'document_id':doc.id,'hash':doc.digest,'policy':settings.model_dump()})
            db.flush()
    if row.status!='approved': raise HTTPException(409,'Approve this exact application version first.')
    existing=db.scalar(select(AgentTask).where(AgentTask.application_id==row.id,AgentTask.document_id==doc.id))
    if existing:
        if existing.status=='cancelled' and not automatic:
            existing.status='queued';existing.automatic=False;existing.error=None;existing.updated_at=now()
            audit(db,user.id,'application.requeued_by_user',row.id,{'task_id':existing.id});commit(db)
            return task_json(existing)
        raise HTTPException(409,f'This exact version already has a submission task ({existing.status}).')
    task=AgentTask(user_id=user.id,application_id=row.id,document_id=doc.id,document_hash=doc.digest,automatic=automatic,status='queued')
    db.add(task);db.flush()
    audit(db,user.id,'application.queued',row.id,{'task_id':task.id,'document_id':doc.id,'automatic':automatic})
    commit(db)
    return task_json(task)


@router.post('/applications/{application_id}/queue',status_code=202)
async def queue(application_id:str,body:QueueInput,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    row=own_application(db,user,application_id)
    check_snapshot(db,row,body)
    result=queue_application(db,user,row,body.automatic)
    if os.getenv('JOBPILOT_AGENT_ENABLED','1')!='0': schedule(asyncio.to_thread(process_task,result['id']))
    return result


@router.post('/tasks/{task_id}/cancel')
def cancel(task_id:str,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    changed=db.execute(update(AgentTask).where(AgentTask.id==task_id,AgentTask.user_id==user.id,AgentTask.status=='queued')
                       .values(status='cancelled',updated_at=now()))
    if changed.rowcount!=1: raise HTTPException(409,'Only a queued task can be cancelled. Reload its current status.')
    audit(db,user.id,'agent.task_cancelled',task_id);commit(db)
    return {'cancelled':True}


def compose(value,payload,task_id):
    delivery=payload['delivery']
    message=EmailMessage()
    message['From']=value['email'];message['To']=valid_address(delivery['recipient'])
    message['Subject']=delivery['subject'];message['Date']=formatdate(localtime=False)
    message['Message-ID']=f"<{task_id}@{value['email'].rsplit('@',1)[-1]}>"
    body=payload['cover_letter']
    if payload.get('answers'):
        body+='\n\nApplication questions and answers\n\n'+'\n\n'.join(f'{question}\n{answer}' for question,answer in payload['answers'].items())
    message.set_content(body)
    kind=delivery.get('attachment_format','pdf')
    render=docx_bytes if kind=='docx' else pdf_bytes
    subtype='vnd.openxmlformats-officedocument.wordprocessingml.document' if kind=='docx' else 'pdf'
    message.add_attachment(render(payload['cv'],'cv'),maintype='application',subtype=subtype,filename=f'CV.{kind}')
    message.add_attachment(render(payload['cover_letter'],'cover-letter'),maintype='application',subtype=subtype,filename=f'Cover-letter.{kind}')
    return message


def process_task(task_id):
    """Reserve in SQLite before network I/O. Ambiguous sends are never retried."""
    with Session(initialize(),expire_on_commit=False) as db:
        task=db.get(AgentTask,task_id)
        if not task or task.status!='queued': return
        row=db.get(ApplicationDraft,task.application_id)
        doc=current_document(db,row)
        settings=policy(db,task.user_id)
        if task.automatic and (settings.paused or settings.mode!='automatic'): return
        if row.status!='approved' or doc.id!=task.document_id or doc.digest!=task.document_hash or digest(doc.payload)!=doc.digest:
            task.status='cancelled';task.error='Application or approval changed before submission.';commit(db);return
        if task.automatic:
            try: automatic_checks(db,db.get(User,task.user_id),row,doc,settings)
            except HTTPException as exc:
                task.status='cancelled';task.error=exc.detail;task.updated_at=now()
                if row.status=='approved': row.status='pending_approval'
                audit(db,task.user_id,'application.automatic_send_blocked',row.id,{'reason':exc.detail});commit(db);return
        approval=db.scalar(select(Approval).where(Approval.application_id==row.id,Approval.user_id==task.user_id,
            Approval.document_id==doc.id,Approval.digest==doc.digest,Approval.decision=='approved'))
        if not approval: task.status='cancelled';task.error='Exact-version authorization is missing.';commit(db);return
        value=credential(db,task.user_id)
        if not value or not value.get('allow_send'): return
        if doc.payload.get('delivery',{}).get('sender')!=value['email']:
            task.status='cancelled';task.error='The Gmail sender changed. Review the destination again.'
            row.status='pending_approval';commit(db);return
        if task.automatic and doc.payload['delivery']['recipient'].rsplit('@',1)[-1].lower() not in settings.allowed_email_domains: return
        used=set(db.scalars(select(SubmissionAttempt.application_id).where(SubmissionAttempt.user_id==task.user_id,
            SubmissionAttempt.created_at>=week_start(),SubmissionAttempt.result.in_(['sending','sent','uncertain','confirmed_by_user']))))
        used.update(db.scalars(select(RecruiterResponse.application_id).where(RecruiterResponse.user_id==task.user_id,
            RecruiterResponse.kind=='external_submitted',RecruiterResponse.received_at>=week_start())))
        if len(used)>=settings.weekly_limit:
            task.error='Weekly submission limit reached. Waiting until the next UTC week.';commit(db);return
        # Create files before reserving a send, so font/export errors never look like SMTP acceptance.
        try: message=compose(value,doc.payload,task.id)
        except Exception:
            task.status='failed';task.error='Could not render the reviewed documents. Check the PDF export before retrying.';commit(db);return
        claimed=db.execute(update(AgentTask).where(AgentTask.id==task.id,AgentTask.status=='queued').values(status='running',error=None,updated_at=now()))
        if claimed.rowcount!=1: db.rollback();return
        attachments=[{'filename':part.get_filename(),'sha256':hashlib.sha256(part.get_payload(decode=True)).hexdigest()} for part in message.iter_attachments()]
        attempt=SubmissionAttempt(user_id=task.user_id,application_id=row.id,approval_id=approval.id,
            idempotency_key=f'email:{task.id}:{uuid4()}',result='sending',confirmation=json.dumps({'message_id':str(message['Message-ID']),'attachments':attachments,'document_hash':doc.digest}))
        db.add(attempt);db.flush()
        task.attempt_id=attempt.id;attempt_id=attempt.id;application_id=row.id;user_id=task.user_id
        commit(db)
    try:
        confirmation=send_message(value,message)
        confirmation.update({'attachments':attachments,'document_hash':task.document_hash})
        outcome,error='sent',None
    except DeliveryError as exc:
        confirmation=None;outcome='uncertain' if exc.uncertain else 'failed';error=str(exc)
    except Exception:
        confirmation=None;outcome='uncertain';error='The sending result is uncertain. Inspect Gmail Sent mail before resolving.'
    with Session(initialize(),expire_on_commit=False) as db:
        task=db.get(AgentTask,task_id);attempt=db.get(SubmissionAttempt,attempt_id)
        attempt.result=outcome;attempt.error_message=error
        if confirmation: attempt.confirmation=json.dumps(confirmation)
        task.status='unknown' if outcome=='uncertain' else outcome;task.error=error;task.updated_at=now()
        if outcome=='sent':
            row=db.get(ApplicationDraft,application_id);row.status='submitted';row.updated_at=now()
        audit(db,user_id,f'application.email_{outcome}',application_id,{'task_id':task_id,'document_id':task.document_id})
        commit(db)


class ResolveInput(BaseModel):
    result: str = Field(pattern='^(sent|not_sent)$')
    inspected_sent_mail: bool = False


@router.post('/tasks/{task_id}/retry')
def retry(task_id:str,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    task=db.scalar(select(AgentTask).where(AgentTask.id==task_id,AgentTask.user_id==user.id))
    if not task or task.status!='failed': raise HTTPException(409,'Only a confirmed failed task can be retried.')
    row=own_application(db,user,task.application_id)
    if row.current_document_id!=task.document_id or row.status!='approved': raise HTTPException(409,'Review and approve the current documents before retrying.')
    task.status='queued';task.error=None;task.updated_at=now();commit(db)
    return task_json(task)


@router.post('/tasks/{task_id}/resolve')
def resolve(task_id:str,body:ResolveInput,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    task=db.scalar(select(AgentTask).where(AgentTask.id==task_id,AgentTask.user_id==user.id))
    if not task or task.status!='unknown': raise HTTPException(409,'Only an uncertain task can be resolved.')
    if not body.inspected_sent_mail: raise HTTPException(422,'Inspect Gmail Sent mail before resolving an uncertain send.')
    attempt=db.get(SubmissionAttempt,task.attempt_id)
    if body.result=='sent':
        confirmation=json.loads(attempt.confirmation or '{}')
        confirmation.update({'accepted_at':now(),'provider':'user_confirmed','meaning':'User confirmed the message in Gmail Sent mail.'})
        attempt.confirmation=json.dumps(confirmation);attempt.result='confirmed_by_user';task.status='sent'
        row=own_application(db,user,task.application_id);row.status='submitted';row.updated_at=now()
    else:
        attempt.result='not_sent_confirmed_by_user';task.status='failed'
    audit(db,user.id,'application.uncertain_send_resolved',task.application_id,{'result':body.result,'provenance':'user_reported'})
    task.error=None;task.updated_at=now();commit(db)
    return task_json(task)


def source_state(db,user_id):
    row=db.scalar(select(JobSource).where(JobSource.user_id==user_id,JobSource.kind=='agent',JobSource.identifier=='local'))
    if not row:
        row=JobSource(user_id=user_id,kind='agent',identifier='local',config={},enabled=False,polling_seconds=3600)
        db.add(row);db.flush()
    return row


def explicit_application_email(description):
    # Suggestions alone do not authorize sending. Automatic use requires an employer-domain allowlist.
    address=r"([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
    found=re.search(r'(?:apply|applications?|bewerbung(?:en)?)[^\n.!?]{0,100}?(?:\bto\b|\bat\b|\ban\b|e-?mail\s*:)\s*'+address,description,re.I)
    if not found: return None
    context=description[max(0,found.start()-60):found.end()]
    if re.search(r"do not|don't|not accept|no applications|keine bewerbung|nicht",context,re.I): return None
    try: return valid_address(found.group(1))
    except ValueError: return None


async def discover_and_prepare(user_id,force=False):
    from .live_jobs import SearchInput,search
    from .cv import tailor_cv
    from .core import match_job
    from .workflow import AutomationPolicy
    with Session(initialize(),expire_on_commit=False) as db:
        user=db.get(User,user_id);candidate=db.get(CandidateProfile,user_id)
        settings=AutomationPolicy(**candidate.preferences.get('automation',{}))
        if settings.paused and not force: return {'prepared':0}
        state=source_state(db,user_id)
        last=state.last_success_at
        if last and not force and datetime.now(timezone.utc)<datetime.fromisoformat(last)+timedelta(hours=1): return {'prepared':0}
        cv=db.get(CVVersion,candidate.preferences.get('master_cv_id',''))
        if not cv or cv.user_id!=user_id or not cv.verified:
            state.last_error='Save and verify a master CV in My profile before scheduled preparation.';commit(db);return {'prepared':0}
        preferences=candidate.preferences
        roles=preferences.get('roles') or candidate.profile.get('targets',{}).get('titles') or ['Frontend Engineer','React Developer','Software Engineer','Junior Developer']
        countries=preferences.get('countries') or ['Germany','Netherlands','France']
        arrangements=preferences.get('arrangements') or ['Remote','Hybrid','On-site']
        master_text=cv.text;master_id=cv.id;profile=candidate.profile;prepared=0;warnings=[];seen=set();stop_generation=False
        for feed in settings.discovery_sources:
            if stop_generation: break
            try: result=await search(SearchInput(source=feed,roles=roles,countries=countries,arrangements=arrangements),user,db)
            except HTTPException as exc: warnings.append(str(exc.detail));continue
            for job in result['jobs']:
                url=canonical_url(job['url'])
                if url in seen: continue
                seen.add(url)
                if job['match']['score']<settings.minimum_match: continue
                senior_target=any(any(word in title.lower() for word in ['senior','staff','principal','lead','head','director']) for title in roles)
                if any('seniority' in flag for flag in job['match']['flags']) and not senior_target: continue
                count=db.scalar(select(func.count()).select_from(ApplicationDraft).where(ApplicationDraft.user_id==user_id,ApplicationDraft.status.in_(['pending_approval','changes_requested','approved']),ApplicationDraft.job_snapshot['is_demo'].as_boolean().is_(False)))
                if count>=min(50,max(15,settings.weekly_limit*3)): break
                if db.scalar(select(ApplicationDraft.id).where(ApplicationDraft.user_id==user_id,ApplicationDraft.job_url==url)): continue
                from .models import Job
                record=db.scalar(select(Job).where(Job.external_id==job['id']))
                if not record or record.is_demo: continue
                tailored=tailor_cv(master_text,job['description'])
                letter=f"Dear hiring team,\n\nI am applying for the {job['title']} position at {job['company']}. Please find my CV attached for your consideration. I would welcome the opportunity to discuss my application.\n\nKind regards,\n{profile.get('name') or user.display_name}"
                ai_generated=False
                if settings.use_claude:
                    if not settings.cloud_consent: warnings.append('Claude consent is missing; generation was not attempted.');continue
                    from .document_studio import generate,Generation
                    try:
                        commit(db)
                        generated=await generate(Generation(cv=master_text,job_description=job['description'],consent=True),user)
                        tailored['text']=generated['cv_draft'];letter=generated['cover_letter'];ai_generated=True
                    except HTTPException as exc: warnings.append(str(exc.detail));stop_generation=True;break
                db.refresh(candidate)
                if candidate.preferences.get('master_cv_id')!=master_id:
                    warnings.append('The master CV changed during discovery. Run the agent again for the new version.');stop_generation=True;break
                version=new_cv(db,user_id,tailored['text'],'Agent tailored CV',{'master_cv_id':master_id,'method':'claude' if ai_generated else 'source_preserving_rules'})
                # AI rewrites require document review; source-preserving drafts keep the reviewed master facts.
                version.verified=not ai_generated
                snapshot={**job,'source_checked_at':result['source']['checked_at']};snapshot.pop('match',None)
                row=ApplicationDraft(user_id=user_id,job_id=record.id,job_external_id=job['id'],job_url=url,job_snapshot=snapshot,status='pending_approval',revision=1)
                db.add(row);db.flush()
                address=explicit_application_email(job['description'])
                domain=address.rsplit('@',1)[-1].lower() if address else None
                authorized=bool(domain and domain in settings.allowed_email_domains and job.get('country') in profile.get('work_authorization_countries',[]))
                delivery={'recipient':address,'subject':f"Application: {job['title']}"[:200],
                          'accepts_email':authorized,'eligibility_confirmed':authorized,'sender':gmail_status(db,user_id).get('email'),
                          'attachment_format':settings.attachment_format,'template_version':'a4-text-v1'} if address else None
                add_document(db,row,version,letter,{},delivery)
                audit(db,user_id,'agent.application_prepared',row.id,{'master_cv_id':master_id,'method':'claude' if ai_generated else 'rules','requires_review':ai_generated or not authorized})
                commit(db);prepared+=1
        state=source_state(db,user_id);state.last_success_at=now();state.last_error='; '.join(dict.fromkeys(warnings))[:2000] or None
        state.config={**state.config,'prepared_last_run':prepared};commit(db)
        return {'prepared':prepared,'warnings':warnings}


def queue_automatic(user_id):
    with Session(initialize(),expire_on_commit=False) as db:
        user=db.get(User,user_id);settings=policy(db,user_id)
        if settings.paused or settings.mode!='automatic': return
        rows=list(db.scalars(select(ApplicationDraft).where(ApplicationDraft.user_id==user_id,
            ApplicationDraft.status.in_(['pending_approval','approved'])).order_by(ApplicationDraft.created_at).limit(100)))
        for row in rows:
            if db.scalar(select(AgentTask.id).where(AgentTask.application_id==row.id,AgentTask.document_id==row.current_document_id)): continue
            try: queue_application(db,user,row,True)
            except HTTPException: db.rollback()


async def cycle(user_id=None,force=False):
    if _cycle_lock.locked(): return {'running':True}
    async with _cycle_lock:
        with Session(initialize()) as db:
            ids=[user_id] if user_id else list(db.scalars(select(User.id)))
        prepared=0
        for current_id in ids:
            try:
                result=await discover_and_prepare(current_id,force)
                prepared+=result.get('prepared',0)
                await asyncio.to_thread(queue_automatic,current_id)
                with Session(initialize()) as db:
                    tasks=list(db.scalars(select(AgentTask.id).where(AgentTask.user_id==current_id,AgentTask.status=='queued').order_by(AgentTask.created_at).limit(15)))
                    source=db.scalar(select(JobSource).where(JobSource.user_id==current_id,JobSource.kind=='gmail',JobSource.identifier=='inbox'))
                    sync_due=bool(source and source.enabled and (not source.last_success_at or datetime.now(timezone.utc)>datetime.fromisoformat(source.last_success_at)+timedelta(minutes=5)))
                for task_id in tasks: await asyncio.to_thread(process_task,task_id)
                if sync_due:
                    def synchronize():
                        with Session(initialize(),expire_on_commit=False) as db: sync_mail(db,current_id)
                    await asyncio.to_thread(synchronize)
            except Exception:
                with Session(initialize(),expire_on_commit=False) as db:
                    state=source_state(db,current_id);state.last_error='Agent cycle stopped safely. Check connection settings and retry.';commit(db)
        return {'running':False,'prepared':prepared,'checked_at':now()}


@router.get('/status')
def agent_status(user:User=Depends(signed_in),db:Session=Depends(get_session)):
    state=db.scalar(select(JobSource).where(JobSource.user_id==user.id,JobSource.kind=='agent',JobSource.identifier=='local'))
    tasks=list(db.scalars(select(AgentTask).where(AgentTask.user_id==user.id).order_by(AgentTask.created_at.desc()).limit(200)))
    return {'enabled':os.getenv('JOBPILOT_AGENT_ENABLED','1')!='0','running':_cycle_lock.locked(),
            'last_run':state.last_success_at if state else None,'error':state.last_error if state else None,'tasks':[task_json(task) for task in tasks],
            'last_prepared':state.config.get('prepared_last_run',0) if state else 0,'weekly_limit':policy(db,user.id).weekly_limit}


@router.post('/run',status_code=202)
async def run(user:User=Depends(signed_in)):
    if _cycle_lock.locked(): return {'scheduled':False,'running':True}
    schedule(cycle(user.id,force=True))
    return {'scheduled':True,'running':False}


def acquire_worker_lock():
    path=data_directory()/'agent.lock'
    file=open(path,'a+b');file.seek(0)
    if path.stat().st_size==0: file.write(b'0');file.flush();file.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        return file
    except OSError: file.close();return None


async def worker():
    lock=acquire_worker_lock()
    if not lock: return
    try:
        with Session(initialize(),expire_on_commit=False) as db:
            for task in db.scalars(select(AgentTask).where(AgentTask.status=='running')):
                task.status='unknown';task.error='The local agent restarted during sending. Inspect Gmail Sent mail before resolving.'
                if task.attempt_id: db.get(SubmissionAttempt,task.attempt_id).result='uncertain'
            commit(db)
        while True:
            await cycle()
            await asyncio.sleep(60)
    finally: lock.close()
