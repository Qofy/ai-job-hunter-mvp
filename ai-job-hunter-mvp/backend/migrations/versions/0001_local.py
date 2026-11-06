"""Initial local schema, frozen independently of future ORM model changes."""
from pathlib import Path
from alembic import op

revision = '0001_local'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for statement in Path(__file__).with_suffix('.sql').read_text(encoding='utf-8').split(';'):
        if statement.strip():
            op.execute(statement)
    op.execute('CREATE TRIGGER immutable_documents BEFORE UPDATE ON document_versions BEGIN SELECT RAISE(ABORT, \'Document versions are immutable\'); END')
    op.execute('CREATE TRIGGER immutable_cv_text BEFORE UPDATE OF text, digest, facts, user_id, version ON cv_versions BEGIN SELECT RAISE(ABORT, \'Create a new CV version instead\'); END')
    op.execute('CREATE TRIGGER immutable_approvals BEFORE UPDATE ON approvals BEGIN SELECT RAISE(ABORT, \'Approval decisions are immutable\'); END')


def downgrade():
    # A downgrade of the initial schema would destroy personal records.
    raise RuntimeError('Initial schema downgrade is intentionally disabled. Restore a backup to roll back.')
