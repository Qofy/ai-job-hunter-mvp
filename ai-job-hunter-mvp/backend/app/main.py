import os
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, or_
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.orm import Session
from .core import demo_jobs, greenhouse_jobs, match_job
from .db import initialize, get_session
from .auth import router as auth_router, signed_in
from .local_routes import router as local_router, canonical_url
from .cv_routes import router as cv_router
from .models import User, CandidateProfile, Job, now
from .live_jobs import router as live_jobs_router

app = FastAPI(title='JobPilot AI — Local', version='0.2.0')
app.include_router(auth_router)
app.include_router(local_router)
app.include_router(cv_router)
app.include_router(live_jobs_router)
origins = {os.getenv('FRONTEND_ORIGIN','http://localhost:3000'), 'http://localhost:3000',
           'http://127.0.0.1:3000','http://localhost:3001','http://127.0.0.1:3001'}
app.add_middleware(CORSMiddleware, allow_origins=sorted(origins), allow_credentials=True,
                   allow_methods=['GET','POST','PUT'], allow_headers=['Content-Type','Authorization'])


@app.middleware('http')
async def local_request_policy(request: Request, call_next):
    origin = request.headers.get('origin')
    if request.method not in {'GET','HEAD','OPTIONS'} and origin and origin not in origins:
        return JSONResponse({'detail':'Untrusted request origin.'}, status_code=403)
    try:
        response = await call_next(request)
    except OperationalError:
        return JSONResponse({'detail':'Local database is busy or unavailable. Retry the operation.'}, status_code=503)
    except IntegrityError:
        return JSONResponse({'detail':'A record conflict occurred. Refresh and retry.'}, status_code=409)
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/health')
def health():
    initialize()
    return {'ok':True,'database_configured':True,'database':'sqlite','schema_version':'0001_local'}


def discovered(rows, user, db):
    profile = db.get(CandidateProfile, user.id).profile
    profile = {**profile, 'skills':profile.get('skills',[])}
    for job in rows:
        url = canonical_url(job['url']) if job.get('url') else None
        conditions = [Job.external_id == job['id']]
        if url:
            conditions.append(Job.canonical_url == url)
        stored = db.scalar(select(Job).where(or_(*conditions)))
        if stored:
            stored.payload, stored.last_seen_at = job, now()
        else:
            db.add(Job(source=job['source'], external_id=job['id'], canonical_url=url,
                       payload=job, is_demo=job['is_demo']))
    db.commit()
    return [{**job,'match':match_job(job,profile)} for job in rows]


@app.get('/jobs/demo')
def demo(user: User = Depends(signed_in), db: Session = Depends(get_session)):
    return discovered(demo_jobs(), user, db)


@app.get('/jobs/greenhouse/{board}')
async def discover(board: str, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    db.commit()  # Do not hold a read transaction while waiting for an external board.
    try:
        jobs = await greenhouse_jobs(board)
    except Exception as exc:
        raise HTTPException(502, f'Job board unavailable: {type(exc).__name__}') from exc
    return discovered(jobs,user,db)
