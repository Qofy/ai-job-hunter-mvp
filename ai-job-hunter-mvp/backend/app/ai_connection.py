"""Optional account-owned Claude API settings; web subscriptions still work manually."""
import json
import os
from urllib.parse import quote
import httpx
from cryptography.fernet import InvalidToken
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import signed_in
from .db import get_session,get_engine
from .gmail import cipher
from .models import Credential,User,CandidateProfile,now
from .local_routes import audit,commit

router=APIRouter(prefix='/connections/claude',tags=['Claude connection'])


def configuration(user_id):
    with Session(get_engine()) as db:
        row=db.scalar(select(Credential).where(Credential.user_id==user_id,Credential.provider=='claude'))
        if row:
            try:
                value=json.loads(cipher().decrypt(row.encrypted_value.encode()))
                return {'key':value['api_key'],'model':value['model'],'source':'account','tested_at':value['tested_at']}
            except (InvalidToken,ValueError,KeyError,OSError) as exc:
                raise HTTPException(503,'Reconnect your Claude API settings; the local credential key is unavailable.') from exc
    return {'key':os.getenv('ANTHROPIC_API_KEY'),'model':os.getenv('CLAUDE_MODEL'),'source':'server','tested_at':None}


def public_status(user_id):
    value=configuration(user_id)
    return {'configured':bool(value['key'] and value['model']),'model':value['model'] if value['key'] else None,
            'source':value['source'],'tested_at':value['tested_at']}


class ClaudeConnection(BaseModel):
    api_key: str = Field(min_length=20,max_length=500)
    model: str = Field(min_length=3,max_length=100,pattern=r'^[a-zA-Z0-9._:-]+$')


@router.get('')
def status(user:User=Depends(signed_in)):
    return public_status(user.id)


@router.post('')
async def connect(body:ClaudeConnection,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    commit(db)
    try:
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            result=await client.get('https://api.anthropic.com/v1/models/'+quote(body.model,safe=''),
                headers={'x-api-key':body.api_key,'anthropic-version':'2023-06-01'})
        if result.status_code!=200: raise HTTPException(502,f'Claude model check returned HTTP {result.status_code}. Check your API key, model ID and API account access.')
    except httpx.HTTPError as exc: raise HTTPException(502,'Could not reach the Claude API. No existing settings were replaced.') from exc
    value={'api_key':body.api_key,'model':body.model,'tested_at':now()}
    row=db.scalar(select(Credential).where(Credential.user_id==user.id,Credential.provider=='claude'))
    encrypted=cipher().encrypt(json.dumps(value).encode()).decode()
    if row: row.encrypted_value=encrypted
    else: db.add(Credential(user_id=user.id,provider='claude',encrypted_value=encrypted))
    audit(db,user.id,'claude.connection_saved',details={'model':body.model});commit(db)
    return public_status(user.id)


@router.post('/disconnect')
def disconnect(user:User=Depends(signed_in),db:Session=Depends(get_session)):
    row=db.scalar(select(Credential).where(Credential.user_id==user.id,Credential.provider=='claude'))
    if row: db.delete(row)
    candidate=db.get(CandidateProfile,user.id)
    automation=candidate.preferences.get('automation',{})
    if automation.get('use_claude'):
        candidate.preferences={**candidate.preferences,'automation':{**automation,'cloud_consent':False,'paused':True}}
    audit(db,user.id,'claude.connection_removed');commit(db)
    return public_status(user.id)
