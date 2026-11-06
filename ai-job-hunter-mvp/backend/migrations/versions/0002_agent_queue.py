"""Persistent local submission queue; preserve the existing application schema."""
from alembic import op

revision='0002_agent_queue'
down_revision='0001_local'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('''CREATE TABLE agent_tasks (
        id VARCHAR(36) NOT NULL PRIMARY KEY, user_id VARCHAR(36) NOT NULL REFERENCES users(id),
        application_id VARCHAR(36) NOT NULL, document_id VARCHAR(36) NOT NULL,
        document_hash VARCHAR(64) NOT NULL, status VARCHAR(30) NOT NULL,
        automatic BOOLEAN NOT NULL DEFAULT 0, attempt_id VARCHAR(36) REFERENCES submission_attempts(id),
        error TEXT, created_at VARCHAR NOT NULL, updated_at VARCHAR NOT NULL,
        UNIQUE(application_id, document_id),
        FOREIGN KEY(application_id,user_id) REFERENCES application_drafts(id,user_id),
        FOREIGN KEY(document_id,user_id) REFERENCES document_versions(id,user_id))''')
    for column in ['user_id','application_id','status']:
        op.execute(f'CREATE INDEX ix_agent_tasks_{column} ON agent_tasks({column})')


def downgrade():
    raise RuntimeError('Restore a database backup to roll back; queued application records must not be silently discarded.')
