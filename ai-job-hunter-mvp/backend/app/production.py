"""Production workspace reads from owned SQLite records, never demo fixtures."""
from datetime import datetime,timezone,timedelta
from typing import Literal
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import Response
from fastapi.responses import Response
from pydantic import BaseModel,Field,HttpUrl
from sqlalchemy import select,update,func,or_
from sqlalchemy.orm import Session
from .auth import signed_in
from .db import get_session
from .models import User,CandidateProfile,CVVersion,ApplicationDraft,AuditEvent,RecruiterResponse,SubmissionAttempt,JobSource,AgentTask,now
from .local_routes import ProfileFacts,new_cv,own_application,current_document,own_cv,add_document,serialize,audit,commit,ensure_not_sending,DecisionInput

router=APIRouter(prefix='/workspace',tags=['Real workspace'])


@router.get('/applications')
def application_page(offset:int=Query(default=0,ge=0),limit:int=Query(default=50,ge=1,le=100),q:str=Query(default='',max_length=200),review_only:bool=False,
        user:User=Depends(signed_in),db:Session=Depends(get_session)):
    query=select(ApplicationDraft).where(ApplicationDraft.user_id==user.id,
        ApplicationDraft.job_snapshot['is_demo'].as_boolean().is_not(True),
        or_(ApplicationDraft.job_snapshot['source'].as_string().is_(None),ApplicationDraft.job_snapshot['source'].as_string()!='demo'))
    if review_only: query=query.where(ApplicationDraft.status.in_(['pending_approval','changes_requested']))
    if q.strip():
        pattern='%'+q.strip()+'%'
        query=query.where(or_(ApplicationDraft.job_snapshot['title'].as_string().ilike(pattern),
                             ApplicationDraft.job_snapshot['company'].as_string().ilike(pattern)))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.scalars(query.order_by(ApplicationDraft.created_at.desc(),ApplicationDraft.id).offset(offset).limit(limit))
    items=[]
    for row in rows:
        doc=current_document(db,row)
        task=db.scalar(select(AgentTask).where(AgentTask.application_id==row.id,AgentTask.document_id==doc.id,AgentTask.user_id==user.id))
        replies=select(RecruiterResponse).where(RecruiterResponse.user_id==user.id,RecruiterResponse.application_id==row.id)
        significant=['interview','rejected','offer','withdrawn','mail_interview','mail_rejected','mail_offer','mail_withdrawn']
        latest=db.scalar(replies.where(RecruiterResponse.kind.in_(significant)).order_by(RecruiterResponse.received_at.desc()))
        if not latest: latest=db.scalar(replies.order_by(RecruiterResponse.received_at.desc()))
        items.append({'id':row.id,'job_url':row.job_url,'job':{key:row.job_snapshot.get(key,'') for key in ['title','company','url','is_demo']},
            'status':row.status,'revision':row.revision,'created_at':row.created_at,'document_id':doc.id,'document_hash':doc.digest,
            'delivery':doc.payload.get('delivery'),'submitted_at':row.updated_at if row.status=='submitted' else None,
            'latest_outcome':('submitted' if latest.kind=='external_submitted' else latest.kind.removeprefix('mail_')) if latest else None,
            'outcome_provenance':'gmail_detected' if latest and latest.kind.startswith('mail_') else 'user_reported' if latest else None,
            'submission_task':{key:getattr(task,key) for key in ['id','application_id','document_id','document_hash','status','automatic','error','created_at','updated_at']} if task else None})
    return {'items':items,'total':total,'offset':offset,'limit':limit}


class CandidateInput(BaseModel):
    profile: ProfileFacts
    master_cv: str = Field(min_length=30,max_length=60000)
    facts_confirmed: bool = False


@router.get('/candidate')
def candidate(user:User=Depends(signed_in),db:Session=Depends(get_session)):
    row=db.get(CandidateProfile,user.id)
    cv=db.get(CVVersion,row.preferences.get('master_cv_id',''))
    return {'profile':row.profile,'preferences':row.preferences,
            'master_cv':cv.text if cv and cv.user_id==user.id else '',
            'verified':bool(cv and cv.user_id==user.id and cv.verified)}


@router.put('/candidate')
def save_candidate(body:CandidateInput,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    if not body.facts_confirmed: raise HTTPException(422,'Review your CV and profile facts before verifying the master CV.')
    if not body.profile.name.strip() or not body.profile.skills: raise HTTPException(422,'Provide your name and verified skills.')
    if body.profile.email:
        from .gmail import valid_address
        try: valid_address(body.profile.email)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    row=db.get(CandidateProfile,user.id)
    facts=body.profile.model_dump()
    facts['unknowns']=[label for label,key in [('professional languages','professional_languages'),('work authorization by country','work_authorization_countries'),('salary expectations','salary_expectations'),('relocation preferences','relocation_preferences')] if not facts.get(key)]
    version=new_cv(db,user.id,body.master_cv,'User-verified master CV',facts)
    version.verified=True
    row.profile=facts;row.preferences={**row.preferences,'master_cv_id':version.id};row.updated_at=now()
    for task in db.scalars(select(AgentTask).where(AgentTask.user_id==user.id,AgentTask.status=='queued')):
        task.status='cancelled';task.error='Master CV or profile facts changed. Review before sending.';task.updated_at=now()
        application=db.get(ApplicationDraft,task.application_id)
        if application.status=='approved': application.status='pending_approval'
    audit(db,user.id,'candidate.master_verified',version.id,{'hash':version.digest})
    commit(db)
    return candidate(user,db)


class SearchPreferences(BaseModel):
    roles: list[str] = Field(min_length=1,max_length=10)
    countries: list[str] = Field(default_factory=list,max_length=40)
    arrangements: list[str] = Field(default_factory=lambda:['Remote','Hybrid','On-site'],max_length=4)
    target: int = Field(default=12,ge=1,le=15)


@router.put('/preferences')
def save_preferences(body:SearchPreferences,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    from .live_jobs import SearchInput
    try: validated=SearchInput(roles=body.roles,countries=body.countries,arrangements=body.arrangements)
    except ValueError as exc: raise HTTPException(422,'Use non-empty roles and supported work arrangements.') from exc
    row=db.get(CandidateProfile,user.id)
    row.preferences={**row.preferences,'roles':validated.roles,'countries':validated.countries,'arrangements':validated.arrangements,'target':body.target}
    row.profile={**row.profile,'targets':{**row.profile.get('targets',{}),'titles':validated.roles,'arrangements':validated.arrangements}}
    row.updated_at=now();audit(db,user.id,'preferences.saved');commit(db)
    return row.preferences


class PrepareJob(BaseModel):
    job_id: str = Field(min_length=1,max_length=500)
    job_url: HttpUrl
    cv_text: str = Field(default='',max_length=60000)
    facts_confirmed: bool = False


@router.post('/prepare',status_code=201)
def prepare_job(body:PrepareJob,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    from .models import Job
    from .local_routes import canonical_url
    from .cv import tailor_cv
    candidate=db.get(CandidateProfile,user.id)
    record=db.scalar(select(Job).where(Job.external_id==body.job_id))
    url=canonical_url(str(body.job_url))
    if not record or record.is_demo or canonical_url(record.payload['url'])!=url: raise HTTPException(422,'Choose a real discovered vacancy with its matching URL.')
    if db.scalar(select(ApplicationDraft.id).where(ApplicationDraft.user_id==user.id,ApplicationDraft.job_url==url)):
        raise HTTPException(409,'You already have an application for this vacancy. Open Applications to review it.')
    master=db.get(CVVersion,candidate.preferences.get('master_cv_id',''))
    if body.cv_text:
        if not body.facts_confirmed or len(body.cv_text.strip())<30: raise HTTPException(422,'Review the tailored CV facts before preparing this application.')
        text=body.cv_text
    elif master and master.user_id==user.id and master.verified:
        text=tailor_cv(master.text,record.payload['description'])['text']
    else: raise HTTPException(409,'Save and verify your master CV in My profile, or review a CV in CV Studio first.')
    facts={'master_cv_id':master.id} if master and master.user_id==user.id else {}
    version=new_cv(db,user.id,text,'Prepared application CV',facts);version.verified=True
    job=record.payload
    name=candidate.profile.get('name','')
    letter=f"Dear hiring team,\n\nI am applying for the {job['title']} position at {job['company']}. Please find my CV attached for your consideration. I would welcome an opportunity to discuss my application.\n\nKind regards,\n{name}"
    row=ApplicationDraft(user_id=user.id,job_id=record.id,job_external_id=record.external_id,job_url=url,job_snapshot=job,status='pending_approval',revision=1)
    db.add(row);db.flush();add_document(db,row,version,letter,{})
    audit(db,user.id,'application.prepared',row.id,{'cv_version':version.id});commit(db)
    return serialize(db,row)


@router.get('/jobs')
def jobs(user:User=Depends(signed_in),db:Session=Depends(get_session)):
    from .live_jobs import saved
    found={};sources=[]
    for kind in ['arbeitnow','germantechjobs']:
        result=saved(kind,user,db)
        sources.append(result['source'])
        for job in result['jobs']:
            if not job.get('is_demo'): found.setdefault(job['url'],job)
    return {'jobs':sorted(found.values(),key=lambda job:-job['match']['score']),'sources':sources}


class EditApplication(DecisionInput):
    cv_text: str = Field(min_length=30,max_length=60000)
    cover_letter: str = Field(max_length=20000)
    answers: dict[str,str] = Field(default_factory=dict,max_length=60)
    facts_confirmed: bool = False


class ApplicationExport(DecisionInput):
    kind: Literal['cv','cover-letter']
    format: Literal['pdf','docx']


@router.post('/applications/{application_id}/export')
def export_application(application_id:str,body:ApplicationExport,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    from .local_routes import check_snapshot
    from .document_studio import pdf_bytes,docx_bytes
    row=own_application(db,user,application_id);doc=check_snapshot(db,row,body)
    text=doc.payload['cv'] if body.kind=='cv' else doc.payload.get('cover_letter','')
    if len(text.strip())<30: raise HTTPException(422,'The selected document is empty or too short.')
    content=(pdf_bytes if body.format=='pdf' else docx_bytes)(text,body.kind)
    media='application/pdf' if body.format=='pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return Response(content,media_type=media,headers={'Cache-Control':'no-store',
        'Content-Disposition':f'attachment; filename="jobpilot-{body.kind}-v{row.revision}.{body.format}"'})


class ApplicationExport(DecisionInput):
    kind: Literal['cv','cover-letter']
    format: Literal['pdf','docx']


@router.post('/applications/{application_id}/export')
def export_application(application_id:str,body:ApplicationExport,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    from .local_routes import check_snapshot
    from .document_studio import pdf_bytes,docx_bytes
    row=own_application(db,user,application_id);doc=check_snapshot(db,row,body)
    text=doc.payload['cv'] if body.kind=='cv' else doc.payload.get('cover_letter','')
    if len(text.strip())<30: raise HTTPException(422,'The selected document is empty or too short.')
    content=(pdf_bytes if body.format=='pdf' else docx_bytes)(text,body.kind)
    media='application/pdf' if body.format=='pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return Response(content,media_type=media,headers={'Cache-Control':'no-store',
        'Content-Disposition':f'attachment; filename="jobpilot-{body.kind}-v{row.revision}.{body.format}"'})


@router.put('/applications/{application_id}')
def edit_application(application_id:str,body:EditApplication,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    from .local_routes import check_snapshot
    row=own_application(db,user,application_id);ensure_not_sending(db,row)
    if row.status=='submitted': raise HTTPException(409,'Submitted documents are immutable. Create a separate follow-up instead.')
    if not body.facts_confirmed: raise HTTPException(422,'Confirm that the edited CV still contains verified facts.')
    old=check_snapshot(db,row,body)
    original=own_cv(db,user,old.cv_version_id)
    facts={**original.facts}
    master=db.get(CandidateProfile,user.id).preferences.get('master_cv_id')
    if master: facts['master_cv_id']=master
    cv=new_cv(db,user.id,body.cv_text,'User-reviewed application edit',facts);cv.verified=True
    changed=db.execute(update(ApplicationDraft).where(ApplicationDraft.id==row.id,ApplicationDraft.current_document_id==old.id,
        ApplicationDraft.revision==row.revision).values(revision=row.revision+1,status='pending_approval',updated_at=now()))
    if changed.rowcount!=1: raise HTTPException(409,'Another edit occurred. Reload the current version.')
    db.refresh(row);add_document(db,row,cv,body.cover_letter,body.answers,old.payload.get('delivery'))
    db.execute(update(AgentTask).where(AgentTask.application_id==row.id,AgentTask.status=='queued').values(status='cancelled',error='Documents changed.',updated_at=now()))
    audit(db,user.id,'application.edited_approval_invalidated',row.id,{'document_id':row.current_document_id});commit(db)
    return serialize(db,row)


@router.get('/summary')
def summary(user:User=Depends(signed_in),db:Session=Depends(get_session)):
    applications=[row for row in db.scalars(select(ApplicationDraft).where(ApplicationDraft.user_id==user.id)) if not row.job_snapshot.get('is_demo')]
    ids={row.id for row in applications}
    replies=[item for item in db.scalars(select(RecruiterResponse).where(RecruiterResponse.user_id==user.id)) if item.application_id in ids]
    attempts=[item for item in db.scalars(select(SubmissionAttempt).where(SubmissionAttempt.user_id==user.id,
        SubmissionAttempt.result.in_(['sent','confirmed_by_user']))) if item.application_id in ids]
    external=[item for item in replies if item.kind=='external_submitted']
    submitted={item.application_id for item in attempts}|{item.application_id for item in external}
    interview_ids={item.application_id for item in replies if item.kind.removeprefix('mail_')=='interview'}
    rejected_ids={item.application_id for item in replies if item.kind.removeprefix('mail_')=='rejected'}
    response_ids={item.application_id for item in replies if item.kind.removeprefix('mail_') not in {'submitted','external_submitted','withdrawn'}}
    current=datetime.now(timezone.utc);start=(current-timedelta(days=current.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
    weeks=[]
    for index in reversed(range(8)):
        first=start-timedelta(weeks=index);last=first+timedelta(weeks=1)
        in_week=lambda value:first<=datetime.fromisoformat(value)<last
        weeks.append({'week':first.date().isoformat(),'prepared':sum(in_week(row.created_at) for row in applications),
            'submitted':len({item.application_id for item in attempts if in_week(item.created_at)}|{item.application_id for item in external if in_week(item.received_at)}),
            'responses':len({item.application_id for item in replies if in_week(item.received_at) and item.kind.removeprefix('mail_') not in {'submitted','external_submitted','withdrawn'}}),
            'interviews':len({item.application_id for item in replies if in_week(item.received_at) and item.kind.removeprefix('mail_')=='interview'})})
    sources={}
    for row in applications:
        name=row.job_snapshot.get('source','user_provided')
        source=sources.setdefault(name,{'source':name,'prepared':0,'submitted':0,'responses':0,'interviews':0})
        source['prepared']+=1;source['submitted']+=row.id in submitted;source['responses']+=row.id in response_ids;source['interviews']+=row.id in interview_ids
    events=[]
    for event in db.scalars(select(AuditEvent).where(AuditEvent.user_id==user.id).order_by(AuditEvent.created_at.desc()).limit(100)):
        if ('application.' in event.action or event.action.startswith('gmail.reply')) and event.entity_id not in ids: continue
        events.append({'id':event.id,'action':event.action,'at':event.created_at,'application_id':event.entity_id if event.entity_id in ids else None})
        if len(events)>=10: break
    candidate=db.get(CandidateProfile,user.id)
    return {'prepared':len(applications),'pending':sum(row.status=='pending_approval' for row in applications),
        'approved':sum(row.status=='approved' for row in applications),'submitted':len(submitted),
        'responses':len(response_ids),'interviews':len(interview_ids),'rejections':len(rejected_ids),
        'weekly_submitted':weeks[-1]['submitted'],'weekly_target':candidate.preferences.get('automation',{}).get('weekly_limit',12),
        'weeks':weeks,'sources':list(sources.values()),'activity':events,
        'outcome_note':'Submissions include Gmail acceptance records and exact-version external submissions reported by the user. Interview and rejection counts reflect Gmail detections and user reports; none guarantee employer receipt or outcomes.'}
