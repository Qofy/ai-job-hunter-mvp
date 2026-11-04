"""Normalize the queue primary key on databases created before the final audit."""
from alembic import op
import sqlalchemy as sa

revision = '0003_queue_integrity'
down_revision = '0002_agent_queue'
branch_labels = None
depends_on = None


def upgrade():
    columns = sa.inspect(op.get_bind()).get_columns('agent_tasks')
    if next(column for column in columns if column['name'] == 'id')['nullable']:
        with op.batch_alter_table('agent_tasks') as batch:
            batch.alter_column('id', existing_type=sa.String(36), nullable=False)


def downgrade():
    raise RuntimeError('Restore a database backup to roll back; queue records must be preserved.')
