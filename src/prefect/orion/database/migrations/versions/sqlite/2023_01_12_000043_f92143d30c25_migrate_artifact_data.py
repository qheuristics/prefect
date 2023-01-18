"""Migrates state data to the artifact table

Revision ID: f92143d30c25
Revises: f92143d30c24
Create Date: 2023-01-12 00:00:43.488367

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "f92143d30c25"
down_revision = "f92143d30c24"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    ### START DATA MIGRATION

    # insert nontrivial task run state results into the artifact table
    def update_task_run_artifact_data_in_batches(batch_size, offset):
        return f"""
            INSERT INTO artifact (task_run_state_id, task_run_id, artifact_data)
            SELECT id, task_run_id, _data
            FROM task_run_state
            WHERE _data IS NOT 'null' AND _data IS NOT NULL
            LIMIT {batch_size} OFFSET {offset};
        """

    # backpopulate the result artifact id on the task run state table
    def update_task_run_state_from_artifact_id_in_batches(batch_size, offset):
        return f"""
            UPDATE task_run_state
            SET result_artifact_id = (SELECT id FROM artifact WHERE task_run_state.id = task_run_state_id)
            WHERE task_run_state.id in (SELECT id FROM task_run_state WHERE (_data IS NOT 'null' AND _data IS NOT NULL) AND (result_artifact_id IS NULL) LIMIT {batch_size});
        """

    # insert nontrivial flow run state results into the artifact table
    def update_flow_run_artifact_data_in_batches(batch_size, offset):
        return f"""
            INSERT INTO artifact (flow_run_state_id, flow_run_id, artifact_data)
            SELECT id, flow_run_id, _data
            FROM flow_run_state
            WHERE _data IS NOT 'null' AND _data IS NOT NULL
            LIMIT {batch_size} OFFSET {offset};
        """

    # backpopulate the result artifact id on the flow run state table
    def update_flow_run_state_from_artifact_id_in_batches(batch_size, offset):
        return f"""
            UPDATE flow_run_state
            SET result_artifact_id = (SELECT id FROM artifact WHERE flow_run_state.id = flow_run_state_id)
            WHERE flow_run_state.id in (SELECT id FROM flow_run_state WHERE (_data IS NOT 'null' AND _data IS NOT NULL) AND (result_artifact_id IS NULL) LIMIT {batch_size});
        """

    data_migration_queries = [
        update_task_run_artifact_data_in_batches,
        update_task_run_state_from_artifact_id_in_batches,
        update_flow_run_artifact_data_in_batches,
        update_flow_run_state_from_artifact_id_in_batches,
    ]

    with op.get_context().autocommit_block():
        conn = op.get_bind()
        for query in data_migration_queries:

            batch_size = 500
            offset = 0

            while True:
                # execute until we've updated task_run_state_id and artifact_data
                # autocommit mode will commit each time `execute` is called
                sql_stmt = sa.text(query(batch_size, offset))
                result = conn.execute(sql_stmt)

                if result.rowcount <= 0:
                    break

                offset += batch_size

    ### END DATA MIGRATION


def downgrade():
    pass
