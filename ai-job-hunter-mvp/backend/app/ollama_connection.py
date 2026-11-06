"""Account-owned Ollama Cloud credentials, encrypted with the local credential key."""
import json
import os
from uuid import uuid4

import httpx
from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import signed_in
from .db import data_directory, get_engine, get_session
from .gmail import cipher
from .local_routes import audit, commit
from .models import Credential, User, now

router = APIRouter(prefix='/connections/ollama', tags=['Ollama Cloud connection'])
CHAT_URL = 'https://ollama.com/api/chat'
DEFAULT_MODEL = 'gemma4:31b'


class OllamaConnection(BaseModel):
    api_key: str = Field(min_length=20, max_length=500, pattern=r'^\S+$')
    model: str = Field(default=DEFAULT_MODEL, min_length=3, max_length=100,
                       pattern=r'^[a-zA-Z0-9._:/-]+$')


def configuration(user_id):
    with Session(get_engine()) as db:
        row = db.scalar(select(Credential).where(
            Credential.user_id == user_id, Credential.provider == 'ollama'))
        try:
            if row:
                encrypted = row.encrypted_value.encode()
                source = 'account'
            else:
                shared = data_directory() / 'ollama-cloud.enc'
                if not shared.exists():
                    return {'key': None, 'model': None, 'tested_at': None, 'source': None}
                encrypted = shared.read_bytes()
                source = 'shared'
            value = json.loads(cipher().decrypt(encrypted))
            return {'key': value['api_key'], 'model': value['model'], 'tested_at': value['tested_at'], 'source': source}
        except (InvalidToken, ValueError, KeyError, OSError) as exc:
            raise HTTPException(503, 'Reconnect Ollama Cloud in Settings. The saved connection could not be read.') from exc


def public_status(user_id):
    value = configuration(user_id)
    return {'configured': bool(value['key'] and value['model']),
            'model': value['model'], 'tested_at': value['tested_at'], 'source': value['source']}


def save_shared_connection(body):
    """Called locally by the installation owner after verifying the key."""
    destination = data_directory() / 'ollama-cloud.enc'
    temporary = destination.with_name(f'.ollama-{uuid4().hex}.tmp')
    value = {'api_key': body.api_key, 'model': body.model, 'tested_at': now()}
    encrypted = cipher().encrypt(json.dumps(value).encode())
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(encrypted)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


async def verify_connection(body):
    try:
        async with httpx.AsyncClient(timeout=35, follow_redirects=False) as client:
            response = await client.post(CHAT_URL,
                headers={'Authorization': 'Bearer ' + body.api_key},
                json={'model': body.model, 'stream': False, 'think': False,
                      'messages': [{'role': 'user', 'content': 'Reply with the single word OK.'}],
                      'options': {'num_predict': 8}})
        if response.status_code != 200:
            raise HTTPException(502, f'Ollama Cloud connection check returned HTTP {response.status_code}. Check your key, model access and usage allowance.')
        payload = response.json()
        if not payload.get('done') or not payload.get('message', {}).get('content', '').strip():
            raise ValueError('Incomplete connection check')
    except httpx.HTTPError as exc:
        raise HTTPException(502, 'Could not reach Ollama Cloud. Existing settings were kept.') from exc
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(502, 'Ollama Cloud returned an invalid connection check. Existing settings were kept.') from exc


def save_connection(db, user_id, body):
    value = {'api_key': body.api_key, 'model': body.model, 'tested_at': now()}
    encrypted = cipher().encrypt(json.dumps(value).encode()).decode()
    row = db.scalar(select(Credential).where(
        Credential.user_id == user_id, Credential.provider == 'ollama'))
    if row:
        row.encrypted_value = encrypted
    else:
        db.add(Credential(user_id=user_id, provider='ollama', encrypted_value=encrypted))
    audit(db, user_id, 'ollama.connection_saved', details={'model': body.model})
    commit(db)


@router.get('')
def status(user: User = Depends(signed_in)):
    return public_status(user.id)


@router.post('')
async def connect(body: OllamaConnection, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    commit(db)
    await verify_connection(body)
    save_connection(db, user.id, body)
    return public_status(user.id)


@router.post('/disconnect')
def disconnect(user: User = Depends(signed_in), db: Session = Depends(get_session)):
    row = db.scalar(select(Credential).where(Credential.user_id == user.id, Credential.provider == 'ollama'))
    if row:
        db.delete(row)
    audit(db, user.id, 'ollama.connection_removed')
    commit(db)
    return public_status(user.id)
