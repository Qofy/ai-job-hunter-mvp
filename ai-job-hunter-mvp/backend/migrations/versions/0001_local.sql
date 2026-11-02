
CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	username VARCHAR(32) NOT NULL, 
	display_name VARCHAR(120) NOT NULL, 
	password_hash TEXT NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
)

;

CREATE TABLE sessions (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at FLOAT NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (token_hash)
)

;

CREATE TABLE candidate_profiles (
	user_id VARCHAR(36) NOT NULL, 
	profile JSON NOT NULL, 
	preferences JSON NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE TABLE cv_versions (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	version INTEGER NOT NULL, 
	text TEXT NOT NULL, 
	digest VARCHAR(64) NOT NULL, 
	facts JSON NOT NULL, 
	verified BOOLEAN NOT NULL, 
	original_file TEXT, 
	source_name VARCHAR(255) NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, version), 
	UNIQUE (id, user_id), 
	CHECK (version > 0), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE TABLE job_sources (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	identifier TEXT NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	polling_seconds INTEGER NOT NULL, 
	last_success_at VARCHAR, 
	last_error TEXT, 
	config JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, kind, identifier), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE TABLE jobs (
	id VARCHAR(36) NOT NULL, 
	source VARCHAR(40) NOT NULL, 
	external_id TEXT NOT NULL, 
	canonical_url TEXT, 
	payload JSON NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	published_at VARCHAR, 
	first_seen_at VARCHAR NOT NULL, 
	last_seen_at VARCHAR NOT NULL, 
	source_updated_at VARCHAR, 
	source_metadata JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (source, external_id), 
	UNIQUE (canonical_url)
)

;

CREATE TABLE user_job_matches (
	user_id VARCHAR(36) NOT NULL, 
	job_id VARCHAR(36) NOT NULL, 
	score INTEGER NOT NULL, 
	reasons JSON NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (user_id, job_id), 
	CHECK (score >= 0 AND score <= 100), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE
)

;

CREATE TABLE application_drafts (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	job_id VARCHAR(36), 
	job_external_id TEXT NOT NULL, 
	job_url TEXT NOT NULL, 
	job_snapshot JSON NOT NULL, 
	current_document_id VARCHAR(36), 
	status VARCHAR(30) NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, job_external_id), 
	UNIQUE (user_id, job_url), 
	UNIQUE (id, user_id), 
	CHECK (status IN ('pending_approval','approved','rejected','changes_requested','submitted','failed')), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(job_id) REFERENCES jobs (id), 
	FOREIGN KEY(current_document_id) REFERENCES document_versions (id)
)

;

CREATE TABLE document_versions (
	id VARCHAR(36) NOT NULL, 
	application_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	cv_version_id VARCHAR(36) NOT NULL, 
	version INTEGER NOT NULL, 
	payload JSON NOT NULL, 
	digest VARCHAR(64) NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (application_id, version), 
	UNIQUE (id, user_id), 
	FOREIGN KEY(application_id, user_id) REFERENCES application_drafts (id, user_id) ON DELETE CASCADE, 
	FOREIGN KEY(cv_version_id, user_id) REFERENCES cv_versions (id, user_id), 
	CHECK (version > 0)
)

;

CREATE TABLE approvals (
	id VARCHAR(36) NOT NULL, 
	application_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	digest VARCHAR(64) NOT NULL, 
	decision VARCHAR(30) NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(application_id, user_id) REFERENCES application_drafts (id, user_id), 
	FOREIGN KEY(document_id, user_id) REFERENCES document_versions (id, user_id), 
	CHECK (decision IN ('approved','rejected','changes_requested'))
)

;

CREATE TABLE submission_attempts (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	application_id VARCHAR(36) NOT NULL, 
	approval_id VARCHAR(36) NOT NULL, 
	idempotency_key VARCHAR NOT NULL, 
	result VARCHAR NOT NULL, 
	confirmation TEXT, 
	error_message TEXT, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(application_id, user_id) REFERENCES application_drafts (id, user_id), 
	FOREIGN KEY(approval_id) REFERENCES approvals (id), 
	UNIQUE (idempotency_key)
)

;

CREATE TABLE notifications (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	dedupe_key VARCHAR NOT NULL, 
	payload JSON NOT NULL, 
	read_at VARCHAR, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, dedupe_key), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE TABLE recruiter_responses (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	application_id VARCHAR(36) NOT NULL, 
	kind VARCHAR NOT NULL, 
	evidence TEXT NOT NULL, 
	verified_at VARCHAR, 
	received_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(application_id, user_id) REFERENCES application_drafts (id, user_id)
)

;

CREATE TABLE audit_events (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	action VARCHAR NOT NULL, 
	entity_id VARCHAR, 
	details JSON NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE TABLE credentials (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	provider VARCHAR NOT NULL, 
	encrypted_value TEXT NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, provider), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_sessions_expires_at ON sessions (expires_at);
CREATE INDEX ix_sessions_user_id ON sessions (user_id);
CREATE INDEX ix_cv_versions_user_id ON cv_versions (user_id);
CREATE INDEX ix_job_sources_user_id ON job_sources (user_id);
CREATE INDEX ix_jobs_first_seen_at ON jobs (first_seen_at);
CREATE INDEX ix_jobs_is_demo ON jobs (is_demo);
CREATE INDEX ix_application_drafts_status ON application_drafts (status);
CREATE INDEX ix_application_drafts_user_id ON application_drafts (user_id);
CREATE INDEX ix_document_versions_user_id ON document_versions (user_id);
CREATE INDEX ix_document_versions_application_id ON document_versions (application_id);
CREATE INDEX ix_approvals_application_id ON approvals (application_id);
CREATE INDEX ix_approvals_user_id ON approvals (user_id);
CREATE INDEX ix_submission_attempts_user_id ON submission_attempts (user_id);
CREATE INDEX ix_submission_attempts_application_id ON submission_attempts (application_id);
CREATE INDEX ix_notifications_user_id ON notifications (user_id);
CREATE INDEX ix_recruiter_responses_application_id ON recruiter_responses (application_id);
CREATE INDEX ix_recruiter_responses_user_id ON recruiter_responses (user_id);
CREATE INDEX ix_audit_events_created_at ON audit_events (created_at);
CREATE INDEX ix_audit_events_user_id ON audit_events (user_id);
CREATE INDEX ix_credentials_user_id ON credentials (user_id);