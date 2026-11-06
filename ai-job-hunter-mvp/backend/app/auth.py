import hashlib
import hmac
import os
import re
import secrets
import time
from collections import defaultdict
from threading import Lock
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import get_session
from .models import User, Session as LoginSession, CandidateProfile, AuditEvent

router = APIRouter(prefix='/auth', tags=['Local accounts'])
COOKIE = os.getenv('JOBPILOT_SESSION_COOKIE', 'jobpilot_session')
TTL = 12 * 3600
_attempts = defaultdict(list)
_attempt_lock = Lock()


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64 * 1024 * 1024).hex()
    return f'scrypt${salt}${value}'


def token_hash(token: str) -> str: return hashlib.sha256(token.encode()).hexdigest()


def public_user(user):
    return {'id': user.id, 'username': user.username, 'display_name': user.display_name}


def signed_in(request: Request, db: Session = Depends(get_session)) -> User:
    authorization = request.headers.get('authorization', '')
    token = authorization[7:] if authorization.startswith('Bearer ') else request.cookies.get(COOKIE, '')
    if not token or len(token) > 200:
        raise HTTPException(401, 'Sign in to a local JobPilot account.')
    login = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash(token), LoginSession.expires_at > time.time()))
    user = db.get(User, login.user_id) if login else None
    if not user:
        raise HTTPException(401, 'Session expired. Please sign in again.')
    request.state.login_id = login.id
    return user


class AccountInput(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r'^[a-zA-Z0-9_-]+$')
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(default='', max_length=120)


def throttle(request: Request):
    key = request.client.host if request.client else 'local'
    with _attempt_lock:
        _attempts[key] = [at for at in _attempts[key] if time.monotonic() - at < 60]
        if len(_attempts[key]) >= 15:
            raise HTTPException(429, 'Too many account attempts. Wait one minute and retry.')
        _attempts[key].append(time.monotonic())


def start_session(db, user, response):
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(user_id=user.id, token_hash=token_hash(token), expires_at=time.time() + TTL))
    db.add(AuditEvent(user_id=user.id, action='session.started'))
    db.commit()
    response.set_cookie(COOKIE, token, httponly=True, samesite='strict', secure=False, max_age=TTL, path='/')
    response.headers['Cache-Control'] = 'no-store'
    return {'user': public_user(user), 'access_token': token, 'token_type': 'bearer'}


@router.post('/register', status_code=201)
def register(body: AccountInput, request: Request, response: Response, db: Session = Depends(get_session)):
    throttle(request)
    user = User(username=body.username.lower(), display_name=body.display_name.strip() or body.username, password_hash=password_hash(body.password))
    db.add(user)
    try:
        db.flush()
        db.add(CandidateProfile(user_id=user.id, profile={
            'name': user.display_name, 'headline': '', 'location': '', 'experience_summary': '',
            'skills': [], 'experience': [], 'projects': [], 'education': '',
            'targets': {'titles': [], 'region': '', 'arrangements': [], 'weekly_approved_target': '10–15'},
            'unknowns': ['professional languages','work authorization by country','salary expectations','relocation preferences'],
            'source': 'No CV verified yet',
        }))
        return start_session(db, user, response)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'That username is already registered.') from exc


@router.post('/login')
def login(body: AccountInput, request: Request, response: Response, db: Session = Depends(get_session)):
    throttle(request)
    user = db.scalar(select(User).where(User.username == body.username.lower()))
    # Always hash a candidate password, even for an unknown username.
    stored = user.password_hash if user else password_hash('invalid-account-password')
    _, salt, expected = stored.split('$')
    actual = password_hash(body.password, salt).split('$')[-1]
    if not user or not hmac.compare_digest(actual, expected):
        raise HTTPException(401, 'Incorrect username or password.')
    return start_session(db, user, response)


@router.get('/me')
def me(user: User = Depends(signed_in)):
    return public_user(user)


@router.post('/logout')
def logout(request: Request, response: Response, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    db.execute(delete(LoginSession).where(LoginSession.id == request.state.login_id, LoginSession.user_id == user.id))
    db.add(AuditEvent(user_id=user.id, action='session.ended'))
    db.commit()
    response.delete_cookie(COOKIE, path='/')
    return {'ok': True}
