"""Account-owned Gmail SMTP/IMAP connection. Secrets never leave the backend."""
import email
from email import policy
from email.message import EmailMessage
from email.utils import parseaddr,parsedate_to_datetime
import imaplib
import json
import os
import re
import smtplib
import ssl
import time
import hashlib
from datetime import datetime,timezone,timedelta
from urllib.parse import quote
from cryptography.fernet import Fernet,InvalidToken
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from .auth import signed_in
from .db import data_directory,get_session
from .models import Credential,User,JobSource,SubmissionAttempt,RecruiterResponse,Notification,now
from .local_routes import audit,commit

router=APIRouter(prefix='/connections/gmail',tags=['Gmail connection'])


def valid_address(value):
    address=parseaddr(value)[1]
    if address!=value or not re.fullmatch(r'[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}',value):
        raise ValueError('Enter a single email address without a display name or line breaks.')
    return value


def cipher():
    path=data_directory()/'credential.key'
    if not path.exists():
        try:
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as file: file.write(Fernet.generate_key())
        except FileExistsError: pass
    return Fernet(path.read_bytes())


def credential(db,user_id):
    row=db.scalar(select(Credential).where(Credential.user_id==user_id,Credential.provider=='gmail'))
    if not row: return None
    try: return json.loads(cipher().decrypt(row.encrypted_value.encode()))
    except (InvalidToken,ValueError,OSError):
        raise HTTPException(503,'Saved Gmail credentials cannot be unlocked. Reconnect Gmail on this computer.')


def mailbox_source(db,user_id):
    row=db.scalar(select(JobSource).where(JobSource.user_id==user_id,JobSource.kind=='gmail',JobSource.identifier=='inbox'))
    if not row:
        row=JobSource(user_id=user_id,kind='gmail',identifier='inbox',enabled=False,polling_seconds=300,config={})
        db.add(row);db.flush()
    return row


def status(db,user_id):
    try: value=credential(db,user_id)
    except HTTPException as exc: return {'connected':False,'can_send':False,'can_sync':False,'email':None,'error':exc.detail}
    source=db.scalar(select(JobSource).where(JobSource.user_id==user_id,JobSource.kind=='gmail',JobSource.identifier=='inbox'))
    return {'connected':bool(value),'can_send':bool(value and value.get('allow_send')),
            'can_sync':bool(value and value.get('allow_read')),'email':value.get('email') if value else None,
            'tested_at':value.get('tested_at') if value else None,'last_sync_at':source.last_success_at if source else None,
            'error':source.last_error if source else None}


class GmailInput(BaseModel):
    email: str = Field(max_length=254)
    app_password: str = Field(min_length=16,max_length=100)
    allow_send: bool = False
    allow_read: bool = False

    @field_validator('email')
    @classmethod
    def address(cls,value): return valid_address(value.strip())

    @field_validator('app_password')
    @classmethod
    def app_password_only(cls,value):
        value=value.replace(' ','')
        if not re.fullmatch('[a-zA-Z0-9]{16}',value): raise ValueError('Use the 16-character Google app password, not your normal Google password.')
        return value


def test_connection(value):
    context=ssl.create_default_context()
    try:
        if value['allow_send']:
            with smtplib.SMTP_SSL('smtp.gmail.com',465,timeout=15,context=context) as smtp:
                smtp.login(value['email'],value['app_password'])
                smtp.noop()
        if value['allow_read']:
            with imaplib.IMAP4_SSL('imap.gmail.com',993,ssl_context=context,timeout=15) as mailbox:
                mailbox.login(value['email'],value['app_password'])
                result,_=mailbox.select('INBOX',readonly=True)
                if result!='OK': raise imaplib.IMAP4.error('Inbox unavailable')
    except (OSError,smtplib.SMTPException,imaplib.IMAP4.error) as exc:
        raise HTTPException(502,'Gmail connection failed. Check your email, Google app password, 2-Step Verification and network. Your normal Google password is not supported.') from exc


@router.get('')
def connection_status(user:User=Depends(signed_in),db:Session=Depends(get_session)):
    return status(db,user.id)


@router.post('')
async def connect(body:GmailInput,user:User=Depends(signed_in),db:Session=Depends(get_session)):
    if not body.allow_read and not body.allow_send: raise HTTPException(422,'Choose sending, reply tracking, or both.')
    value=body.model_dump()
    try: previous=credential(db,user.id)
    except HTTPException: previous=None
    commit(db)
    await run_in_threadpool(test_connection,value)
    value['tested_at']=now()
    row=db.scalar(select(Credential).where(Credential.user_id==user.id,Credential.provider=='gmail'))
    encrypted=cipher().encrypt(json.dumps(value).encode()).decode()
    if row: row.encrypted_value=encrypted
    else: db.add(Credential(user_id=user.id,provider='gmail',encrypted_value=encrypted))
    source=mailbox_source(db,user.id)
    if not previous or previous.get('email')!=body.email:
        source.config={};source.last_success_at=None
    source.enabled=body.allow_read
    source.last_error=None
    audit(db,user.id,'gmail.connected',details={'allow_send':body.allow_send,'allow_read':body.allow_read})
    commit(db)
    return status(db,user.id)


@router.post('/disconnect')
def disconnect(user:User=Depends(signed_in),db:Session=Depends(get_session)):
    row=db.scalar(select(Credential).where(Credential.user_id==user.id,Credential.provider=='gmail'))
    if row: db.delete(row)
    source=mailbox_source(db,user.id);source.enabled=False
    audit(db,user.id,'gmail.disconnected');commit(db)
    return {'connected':False}


class DeliveryError(Exception):
    def __init__(self,message,uncertain=False):
        super().__init__(message);self.uncertain=uncertain


def send_message(value,message):
    transferring=False
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com',465,timeout=20,context=ssl.create_default_context()) as smtp:
            smtp.login(value['email'],value['app_password'])
            transferring=True
            refused=smtp.send_message(message,from_addr=value['email'],to_addrs=[message['To']])
            if refused: raise DeliveryError('Gmail rejected the recipient. No successful submission was recorded.')
    except (smtplib.SMTPRecipientsRefused,smtplib.SMTPDataError,smtplib.SMTPSenderRefused) as exc:
        raise DeliveryError('Gmail explicitly rejected the message. Check the application address and account settings.') from exc
    except (OSError,smtplib.SMTPException) as exc:
        raise DeliveryError('Gmail disconnected during transfer. Inspect Gmail Sent mail before retrying.' if transferring else 'Gmail could not authenticate or connect. Check the connection settings.',uncertain=transferring) from exc
    return {'message_id':str(message['Message-ID']),'accepted_at':now(),'provider':'gmail_smtp',
            'meaning':'Gmail accepted the message for delivery; employer receipt is not guaranteed.',
            'sent_link':'https://mail.google.com/mail/u/0/#search/'+quote('rfc822msgid:'+str(message['Message-ID']).strip('<>'),safe='')}


def classify(subject,text):
    content=(subject+'\n'+text).lower()
    rejection=bool(re.search(r'not (?:be )?(?:moving|proceeding|progressing) (?:forward|with)|application (?:was|has been) (?:unsuccessful|rejected)|regret to inform|leider.{0,90}(?:absage|nicht berücksichtigen|nicht weiter)',content,re.S))
    interview=bool(re.search(r'(?:invite|invitation|schedule|arrange).{0,70}(?:interview|screening call)|(?:interview|screening call).{0,60}(?:invitation|availability)|(?:einladung|einladen).{0,80}(?:vorstellungsgespräch|kennenlerngespräch|interview)',content,re.S))
    if re.search(r'(?:if selected|if your application|should you|may invite|might invite|cannot|unable to|will not).{0,90}(?:invite|interview)',content,re.S): interview=False
    offer=bool(re.search(r'(?:pleased|delighted|happy).{0,50}offer you|offer of employment|employment offer|arbeitsvertragsangebot',content,re.S))
    candidates=[name for name,found in [('rejected',rejection),('interview',interview),('offer',offer)] if found]
    if len(candidates)==1: return candidates[0]
    if len(candidates)>1: return 'needs_review'
    if re.search(r'(?:received|thank you for).{0,60}(?:your application|applying)|bewerbung.{0,50}(?:eingegangen|erhalten)',content,re.S): return 'acknowledged'
    return 'needs_review'


def decode_message(raw):
    message=email.message_from_bytes(raw,policy=policy.default)
    bodies=[]
    for part in message.walk():
        if part.get_content_type()=='text/plain' and part.get_content_disposition()!='attachment':
            try: bodies.append(part.get_content())
            except (LookupError,UnicodeError): pass
    if not bodies:
        from .job_sources import plain_text
        for part in message.walk():
            if part.get_content_type()=='text/html' and part.get_content_disposition()!='attachment':
                try: bodies.append(plain_text(part.get_content()))
                except (LookupError,UnicodeError): pass
    text='\n'.join(bodies)
    text=re.split(r'(?im)^(?:On .{3,180}wrote:|Am .{3,180}schrieb|-----Original Message-----|_{8,})',text)[0]
    return message,'\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('>'))[:10000]


def fetch_replies(value,known,cursor):
    """Only fetch bodies for replies referencing one of our real sent messages."""
    items=[];started=time.monotonic();latest=int(cursor.get('last_uid',0))
    try:
        with imaplib.IMAP4_SSL('imap.gmail.com',993,ssl_context=ssl.create_default_context(),timeout=15) as mailbox:
            mailbox.login(value['email'],value['app_password'])
            result,_=mailbox.select('INBOX',readonly=True)
            if result!='OK': raise imaplib.IMAP4.error('Inbox unavailable')
            validity=(mailbox.response('UIDVALIDITY')[1] or [b''])[0].decode()
            if cursor.get('uidvalidity')!=validity: latest=0
            since=(datetime.now(timezone.utc)-timedelta(days=14)).strftime('%d-%b-%Y')
            result,data=mailbox.uid('search',None,'UID',f'{latest+1}:*','SINCE',since)
            if result!='OK': raise imaplib.IMAP4.error('Search unavailable')
            uids=sorted(int(x) for x in (data[0] or b'').split() if int(x)>latest)[:50]
            for uid in uids:
                if time.monotonic()-started>40: break
                result,parts=mailbox.uid('fetch',str(uid),'(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID REFERENCES IN-REPLY-TO FROM SUBJECT DATE)])')
                if result!='OK': break
                header=b''.join(part[1] for part in parts if isinstance(part,tuple))
                parsed=email.message_from_bytes(header,policy=policy.default)
                refs=set(re.findall(r'<[^<>\s]+>',str(parsed.get('References',''))+' '+str(parsed.get('In-Reply-To',''))))
                matches={known[reference] for reference in refs if reference in known}
                if len(matches)==1 and parseaddr(str(parsed.get('From','')))[1].lower()!=value['email'].lower():
                    result,parts=mailbox.uid('fetch',str(uid),'(BODY.PEEK[]<0.1048576>)')
                    if result!='OK': break
                    raw=b''.join(part[1] for part in parts if isinstance(part,tuple))
                    message,text=decode_message(raw)
                    try:
                        received=parsedate_to_datetime(str(message.get('Date','')))
                        if received.tzinfo is None: received=received.replace(tzinfo=timezone.utc)
                    except (ValueError,TypeError): received=datetime.now(timezone.utc)
                    items.append({'application_id':matches.pop(),'uid':uid,'uidvalidity':validity,
                        'message_id':str(message.get('Message-ID',''))[:500],'subject':str(message.get('Subject',''))[:500],
                        'from':str(message.get('From',''))[:500],'text':text,'kind':classify(str(message.get('Subject','')),text),
                        'received_at':received.isoformat(),'truncated':len(raw)>=1048576})
                latest=uid
    except (OSError,imaplib.IMAP4.error,ValueError) as exc:
        raise HTTPException(502,'Gmail inbox sync failed. Check the connection and retry. Existing application history was kept.') from exc
    return items,{'last_uid':latest,'uidvalidity':validity}


def sync_mail(db,user_id):
    value=credential(db,user_id)
    if not value or not value.get('allow_read'): raise HTTPException(409,'Connect Gmail with reply tracking enabled first.')
    source=mailbox_source(db,user_id)
    cursor=source.config
    known={}
    for attempt in db.scalars(select(SubmissionAttempt).where(SubmissionAttempt.user_id==user_id,SubmissionAttempt.result.in_(['sent','confirmed_by_user']))):
        try:
            confirmation=json.loads(attempt.confirmation or '{}')
            if confirmation.get('message_id'): known[confirmation['message_id']]=attempt.application_id
        except ValueError: pass
    commit(db)
    try: items,cursor=fetch_replies(value,known,cursor)
    except HTTPException:
        source=mailbox_source(db,user_id);source.last_error='Gmail sync failed. Check connection settings.';commit(db);raise
    count=0
    for item in items:
        dedupe='gmail:message:'+hashlib.sha256(item['message_id'].encode()).hexdigest() if item['message_id'] else f"gmail:{item['uidvalidity']}:{item['uid']}"
        if db.scalar(select(Notification.id).where(Notification.user_id==user_id,Notification.dedupe_key==dedupe)): continue
        db.add(RecruiterResponse(user_id=user_id,application_id=item['application_id'],kind='mail_'+item['kind'],
                evidence=json.dumps(item,ensure_ascii=False),verified_at=None,received_at=item['received_at']))
        db.add(Notification(user_id=user_id,dedupe_key=dedupe,payload={'kind':item['kind'],'application_id':item['application_id'],'subject':item['subject']}))
        audit(db,user_id,'gmail.reply_detected',item['application_id'],{'kind':item['kind'],'message_id':item['message_id']})
        count+=1
    source=mailbox_source(db,user_id);source.config=cursor;source.last_success_at=now();source.last_error=None
    commit(db)
    return {'matched_replies':count,'checked_at':source.last_success_at}


@router.post('/sync')
def sync(user:User=Depends(signed_in),db:Session=Depends(get_session)):
    return sync_mail(db,user.id)
