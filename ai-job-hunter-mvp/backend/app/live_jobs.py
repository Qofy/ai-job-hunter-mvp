"""Owner-scoped live search, persistent cache and truthful source status."""
from datetime import datetime, timezone, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, or_, update
from sqlalchemy.orm import Session
from .auth import signed_in
from .db import get_session
from .models import User, Job, JobSource, UserJobMatch, CandidateProfile, now
from .core import match_job
from .job_filters import DEFAULT_ROLES, DEFAULT_COUNTRIES, job_matches
from .job_sources import fetch_arbeitnow, FeedUnavailable, CACHE_SECONDS, SOURCE_HOME
from .local_routes import canonical_url, commit
from .germantechjobs import fetch_germantechjobs, HOME as GERMAN_HOME

router = APIRouter(tags=['Live job search'])


class SearchInput(BaseModel):
    source: Literal["arbeitnow", "germantechjobs"] = "arbeitnow"
    roles: list[str] = Field(default_factory=lambda:list(DEFAULT_ROLES), min_length=1,max_length=10)
    countries: list[str] = Field(default_factory=lambda:list(DEFAULT_COUNTRIES),max_length=40)
    arrangements: list[str] = Field(default_factory=lambda:['Remote','Hybrid','On-site'],max_length=4)

    @field_validator('roles','countries','arrangements')
    @classmethod
    def clean(cls, value):
        if any(not x.strip() or len(x)>100 for x in value):
            raise ValueError('Search terms must be non-empty and at most 100 characters each.')
        return list(dict.fromkeys(x.strip() for x in value))

    @field_validator('arrangements')
    @classmethod
    def known_arrangements(cls,value):
        if any(x not in {'Remote','Hybrid','On-site','Unspecified'} for x in value):
            raise ValueError('Unsupported work arrangement.')
        return value


def own_source(db,user,kind="arbeitnow"):
    return db.scalar(select(JobSource).where(JobSource.user_id==user.id,JobSource.kind==kind,JobSource.identifier=='public-feed'))


def cached_rows(db,source):
    ids = source.config.get('job_ids',[]) if source else []
    if not ids: return []
    return list(db.scalars(select(Job).where(Job.id.in_(ids),Job.is_demo.is_(False))))


def response(db,user,source,criteria,status):
    profile = db.get(CandidateProfile,user.id).profile
    matching_profile = {**profile,'skills':profile.get('skills',[]),
                        'targets':{**profile.get('targets',{}),'titles':criteria.roles}}
    matches=[]
    for record in cached_rows(db,source):
        job=record.payload
        if not job_matches(job,criteria.roles,criteria.countries,criteria.arrangements): continue
        match=match_job(job,matching_profile)
        if not job.get('country'):
            match['flags'].append('Country is not explicit in the listing. This feed focuses on Germany; confirm the original location and eligibility.')
        if job.get('description_truncated'):
            match['flags'].append('Description shortened; read the original vacancy before applying.')
        matches.append({**job,'match':match,'first_seen_at':record.first_seen_at,'last_seen_at':record.last_seen_at})
    matches.sort(key=lambda j:(-j['match']['score'],j['title'].lower(),j['id']))
    config=source.config if source else {}
    checked=source.last_success_at if source else None
    refresh=(datetime.fromisoformat(checked)+timedelta(seconds=CACHE_SECONDS)).isoformat() if checked else None
    return {'jobs':matches,'criteria':criteria.model_dump(),'source':{
        'name':'GermanTechJobs' if criteria.source=='germantechjobs' else 'Arbeitnow','url':GERMAN_HOME if criteria.source=='germantechjobs' else SOURCE_HOME,'status':status,'checked_at':checked,'next_refresh_at':refresh,
        'scanned':config.get('scanned',0),'pages':config.get('pages',0),'has_more':config.get('has_more',False),
        'notes':config.get('notes',[]),'error':source.last_error if source else None,
        'retry_at':config.get('retry_at'),
        'coverage':'Germany-focused public feed. Country and remote eligibility still require manual review.'}}


@router.get('/jobs/live')
def saved(source:Literal["arbeitnow","germantechjobs"]="arbeitnow",user:User=Depends(signed_in),db:Session=Depends(get_session)):
    kind=source
    source=own_source(db,user,kind)
    criteria=SearchInput(**source.config.get('search',{})) if source else SearchInput(source=kind)
    if not source or not source.last_success_at: return response(db,user,source,criteria,'not_searched')
    expired=datetime.now(timezone.utc)>=datetime.fromisoformat(source.last_success_at)+timedelta(seconds=CACHE_SECONDS)
    return response(db,user,source,criteria,'stale' if expired or source.last_error else 'cached')


@router.post('/jobs/search')
async def search(body:SearchInput,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    source=own_source(db,user,body.source)
    if not source:
        source=JobSource(user_id=user.id,kind=body.source,identifier='public-feed',enabled=False,polling_seconds=CACHE_SECONDS,config={})
        db.add(source)
        db.flush()
    source_id=source.id
    config={**source.config,'search':body.model_dump()}
    source.config=config
    current=datetime.now(timezone.utc)
    if source.last_success_at and current<datetime.fromisoformat(source.last_success_at)+timedelta(seconds=CACHE_SECONDS):
        commit(db)
        return response(db,user,source,body,'cached')
    retry_at=config.get('retry_at')
    if retry_at and current<datetime.fromisoformat(retry_at):
        commit(db)
        if source.last_success_at: return response(db,user,source,body,'stale')
        raise HTTPException(503,f"{source.last_error} Retry after {retry_at}.")
    # Release SQLite's read transaction during external network access.
    commit(db)
    try:
        result=await (fetch_germantechjobs() if body.source=="germantechjobs" else fetch_arbeitnow())
    except FeedUnavailable as exc:
        source=db.get(JobSource,source_id)
        source.last_error=str(exc)
        source.config={**source.config,'retry_at':(datetime.now(timezone.utc)+timedelta(seconds=exc.retry_seconds)).isoformat()}
        commit(db)
        if source.last_success_at: return response(db,user,source,body,'stale')
        raise HTTPException(503,str(exc)) from exc
    source=db.get(JobSource,source_id)
    ids=[]
    for job in result['jobs']:
        url=canonical_url(job['url'])
        record=db.scalar(select(Job).where(or_((Job.source==body.source)&(Job.external_id==job['id']),Job.canonical_url==url)))
        if record:
            record.payload,record.last_seen_at=job,result['checked_at']
            record.source_metadata={**record.source_metadata,'provider_created_at':job.get('source_created_at')}
        else:
            record=Job(source=body.source,external_id=job['id'],canonical_url=url,payload=job,is_demo=False,
                       first_seen_at=result['checked_at'],last_seen_at=result['checked_at'],
                       source_metadata={'provider_created_at':job.get('source_created_at')})
            db.add(record)
            db.flush()
        if record.id not in ids: ids.append(record.id)
    source.last_success_at=result['checked_at']
    source.last_error=None
    source.config={'job_ids':ids,'search':body.model_dump(),'scanned':len(result['jobs']),
                   'pages':result['pages'],'has_more':result['has_more'],'notes':result['notes']}
    output=response(db,user,source,body,'live')
    for job in output['jobs']:
        record=db.scalar(select(Job).where(Job.source==body.source,Job.external_id==job['id']))
        if record:
            match=db.get(UserJobMatch,(user.id,record.id))
            if match:
                match.score,match.reasons,match.updated_at=job['match']['score'],job['match'],now()
            else: db.add(UserJobMatch(user_id=user.id,job_id=record.id,score=job['match']['score'],reasons=job['match']))
    commit(db)
    return output
