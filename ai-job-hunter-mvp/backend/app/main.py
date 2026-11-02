import os
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .core import PROFILE, demo_jobs, greenhouse_jobs, match_job
from .db import get_db

app = FastAPI(title='AI Job Hunter MVP',version='0.1.0')
app.add_middleware(CORSMiddleware,allow_origins=[os.getenv('FRONTEND_ORIGIN','http://localhost:3000')],allow_methods=['GET','POST'],allow_headers=['*'])

@app.get('/health')
def health(): return {'ok':True,'database_configured':bool(get_db())}

@app.get('/profile')
def profile(): return PROFILE

@app.get('/jobs/demo')
def demo(): return [{**j,'match':match_job(j)} for j in demo_jobs()]

@app.get('/jobs/greenhouse/{board}')
async def discover(board: str):
    try: jobs = await greenhouse_jobs(board)
    except Exception as exc: raise HTTPException(502,detail=f'Job board unavailable: {type(exc).__name__}')
    return [{**j,'match':match_job(j)} for j in jobs]

class PreparedApplication(BaseModel):
    job_id: str
    job_url: str
    cv_version: str
    answers: dict[str,str] = {}
    cover_letter: str = ''

def verified_user(authorization: str | None):
    db = get_db()
    if not db: raise HTTPException(503,'Supabase not configured')
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401,'Supabase access token required')
    try:
        user = db.auth.get_user(authorization.removeprefix('Bearer ').strip()).user
        if not user: raise ValueError('Missing user')
        return db, str(user.id)
    except Exception: raise HTTPException(401,'Invalid access token')

@app.post('/applications/prepare')
def prepare(body: PreparedApplication, authorization: str | None = Header(None)):
    # Never submit. Verify the user through Supabase Auth.
    db, x_user_id = verified_user(authorization)
    row={'user_id':x_user_id,'job_external_id':body.job_id,'job_url':body.job_url,'cv_version':body.cv_version,'answers':body.answers,'cover_letter':body.cover_letter,'status':'pending_approval'}
    try: return db.table('applications').insert(row).execute().data[0]
    except Exception: raise HTTPException(500,'Unable to store application')

@app.post('/applications/{application_id}/approve')
def approve(application_id: str, authorization: str | None = Header(None)):
    # Approval is recorded, but there is deliberately NO automatic submit endpoint in MVP.
    db, x_user_id = verified_user(authorization)
    rows=db.table('applications').select('*').eq('id',application_id).eq('user_id',x_user_id).execute().data
    if not rows: raise HTTPException(404,'Application not found')
    if rows[0]['status']!='pending_approval': raise HTTPException(409,'Application not pending approval')
    from datetime import datetime, timezone
    updated=db.table('applications').update({'status':'approved','approved_at':datetime.now(timezone.utc).isoformat()}).eq('id',application_id).eq('user_id',x_user_id).eq('status','pending_approval').execute().data
    return {'approved':bool(updated),'submitted':False,'application':updated[0] if updated else None}
