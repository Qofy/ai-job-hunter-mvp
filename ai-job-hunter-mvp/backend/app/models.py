"""Local persistent domain. Public jobs are shared; all personal records have owners."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (Boolean, CheckConstraint, Float, ForeignKey, ForeignKeyConstraint,
                        Integer, JSON, String, Text, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase): pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Session(Base):
    __tablename__ = 'sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[float] = mapped_column(Float, index=True)
    created_at: Mapped[str] = mapped_column(String, default=now)


class CandidateProfile(Base):
    __tablename__ = 'candidate_profiles'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class CVVersion(Base):
    __tablename__ = 'cv_versions'
    __table_args__ = (UniqueConstraint('user_id','version'), UniqueConstraint('id','user_id'), CheckConstraint('version > 0'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    version: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    digest: Mapped[str] = mapped_column(String(64))
    facts: Mapped[dict] = mapped_column(JSON, default=dict)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    original_file: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(255), default='Pasted CV')
    created_at: Mapped[str] = mapped_column(String, default=now)


class JobSource(Base):
    __tablename__ = 'job_sources'
    __table_args__ = (UniqueConstraint('user_id','kind','identifier'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    identifier: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    polling_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    last_success_at: Mapped[str | None] = mapped_column(String)
    last_error: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class Job(Base):
    __tablename__ = 'jobs'
    __table_args__ = (UniqueConstraint('source','external_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text, unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[str | None] = mapped_column(String)
    first_seen_at: Mapped[str] = mapped_column(String, default=now, index=True)
    last_seen_at: Mapped[str] = mapped_column(String, default=now)
    source_updated_at: Mapped[str | None] = mapped_column(String)
    source_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class UserJobMatch(Base):
    __tablename__ = 'user_job_matches'
    __table_args__ = (CheckConstraint('score >= 0 AND score <= 100'),)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey('jobs.id', ondelete='CASCADE'), primary_key=True)
    score: Mapped[int] = mapped_column(Integer)
    reasons: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class ApplicationDraft(Base):
    __tablename__ = 'application_drafts'
    __table_args__ = (UniqueConstraint('user_id','job_external_id'), UniqueConstraint('user_id','job_url'),
                     UniqueConstraint('id','user_id'), CheckConstraint("status IN ('pending_approval','approved','rejected','changes_requested','submitted','failed')"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey('jobs.id'))
    job_external_id: Mapped[str] = mapped_column(Text)
    job_url: Mapped[str] = mapped_column(Text)
    job_snapshot: Mapped[dict] = mapped_column(JSON)
    current_document_id: Mapped[str | None] = mapped_column(ForeignKey('document_versions.id', use_alter=True))
    status: Mapped[str] = mapped_column(String(30), default='pending_approval', index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class DocumentVersion(Base):
    __tablename__ = 'document_versions'
    __table_args__ = (UniqueConstraint('application_id','version'), UniqueConstraint('id','user_id'),
                     ForeignKeyConstraint(['application_id','user_id'],['application_drafts.id','application_drafts.user_id'],ondelete='CASCADE'),
                     ForeignKeyConstraint(['cv_version_id','user_id'],['cv_versions.id','cv_versions.user_id']), CheckConstraint('version > 0'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    cv_version_id: Mapped[str] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String, default=now)


class Approval(Base):
    __tablename__ = 'approvals'
    __table_args__ = (ForeignKeyConstraint(['application_id','user_id'],['application_drafts.id','application_drafts.user_id']),
                     ForeignKeyConstraint(['document_id','user_id'],['document_versions.id','document_versions.user_id']),
                     CheckConstraint("decision IN ('approved','rejected','changes_requested')"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    document_id: Mapped[str] = mapped_column(String(36))
    digest: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[str] = mapped_column(String, default=now)


class SubmissionAttempt(Base):
    __tablename__ = 'submission_attempts'
    __table_args__ = (ForeignKeyConstraint(['application_id','user_id'],['application_drafts.id','application_drafts.user_id']),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    application_id: Mapped[str] = mapped_column(String(36), index=True)
    approval_id: Mapped[str] = mapped_column(ForeignKey('approvals.id'))
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    result: Mapped[str] = mapped_column(String)
    confirmation: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Notification(Base):
    __tablename__ = 'notifications'
    __table_args__ = (UniqueConstraint('user_id','dedupe_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    dedupe_key: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    read_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now)


class RecruiterResponse(Base):
    __tablename__ = 'recruiter_responses'
    __table_args__ = (ForeignKeyConstraint(['application_id','user_id'],['application_drafts.id','application_drafts.user_id']),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    application_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String)
    evidence: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[str | None] = mapped_column(String)
    received_at: Mapped[str] = mapped_column(String)


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    action: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str | None] = mapped_column(String)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, default=now, index=True)


class Credential(Base):
    __tablename__ = 'credentials'
    __table_args__ = (UniqueConstraint('user_id','provider'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    provider: Mapped[str] = mapped_column(String)
    encrypted_value: Mapped[str] = mapped_column(Text)
