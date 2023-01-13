"""Implements the artifact table and migrates run results

Revision ID: f92143d30c24
Revises: bb38729c471a
Create Date: 2023-01-12 00:00:42.488367

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "f92143d30c24"
down_revision = "bb38729c471a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    op.create_table(
        "artifact",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n        || lower(hex(randomblob(2)))\n        || '-4'\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || substr('89ab',abs(random()) % 4 + 1, 1)\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("key", sa.String(), nullable=True),
        sa.Column("artifact_type", sa.String(), nullable=True),
        sa.Column("artifact_data", sa.JSON(), nullable=True),
        sa.Column("artifact_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "task_run_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "task_run_state_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "flow_run_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "flow_run_state_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["flow_run_state_id"],
            ["flow_run_state.id"],
            name=op.f("fk_artifact__flow_run_state_id__flow_run_state"),
        ),
        sa.ForeignKeyConstraint(
            ["flow_run_id"],
            ["flow_run.id"],
            name=op.f("fk_artifact__flow_run_id__flow_run"),
        ),
        sa.ForeignKeyConstraint(
            ["task_run_state_id"],
            ["task_run_state.id"],
            name=op.f("fk_artifact__task_run_state_id__task_run_state"),
        ),
        sa.ForeignKeyConstraint(
            ["task_run_id"],
            ["task_run.id"],
            name=op.f("fk_artifact__task_run_id__task_run"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact")),
    )
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_artifact__flow_run_id"),
            ["flow_run_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_artifact__flow_run_state_id"),
            ["flow_run_state_id"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_artifact__key"), ["key"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_artifact__task_run_id"),
            ["task_run_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_artifact__task_run_state_id"),
            ["task_run_state_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_artifact__updated"), ["updated"], unique=False
        )

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "result_artifact_id",
                prefect.orion.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_flow_run_state__result_artifact_id"),
            ["result_artifact_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_flow_run_state__result_artifact_id__artifact"),
            "artifact",
            ["result_artifact_id"],
            ["id"],
            ondelete="SET NULL",
            use_alter=True,
        )

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "result_artifact_id",
                prefect.orion.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_task_run_state__result_artifact_id"),
            ["result_artifact_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_task_run_state__result_artifact_id__artifact"),
            "artifact",
            ["result_artifact_id"],
            ["id"],
            ondelete="SET NULL",
            use_alter=True,
        )

    ### START DATA MIGRATION

    # insert nontrivial task run state results into the artifact table
    def update_task_run_artifact_data_in_batches(batch_size, offset):
        return f"""
            INSERT INTO artifact (task_run_state_id, task_run_id, artifact_data)
            SELECT id, task_run_id, data
            FROM task_run_state
            WHERE data IS NOT 'null' AND data IS NOT NULL
            LIMIT {batch_size} OFFSET {offset};
        """

    # backpopulate the result artifact id on the task run state table
    def update_task_run_state_from_artifact_id_in_batches(batch_size, offset):
        return f"""
            UPDATE task_run_state
            SET result_artifact_id = (SELECT id FROM artifact WHERE task_run_state.id = task_run_state_id)
            WHERE task_run_state.id in (SELECT id FROM task_run_state WHERE (data IS NOT 'null' AND data IS NOT NULL) AND (result_artifact_id IS NULL) LIMIT {batch_size});
        """

    # insert nontrivial flow run state results into the artifact table
    def update_flow_run_artifact_data_in_batches(batch_size, offset):
        return f"""
            INSERT INTO artifact (flow_run_state_id, flow_run_id, artifact_data)
            SELECT id, flow_run_id, data
            FROM flow_run_state
            WHERE data IS NOT 'null' AND data IS NOT NULL
            LIMIT {batch_size} OFFSET {offset};
        """

    # backpopulate the result artifact id on the flow run state table
    def update_flow_run_state_from_artifact_id_in_batches(batch_size, offset):
        return f"""
            UPDATE flow_run_state
            SET result_artifact_id = (SELECT id FROM artifact WHERE flow_run_state.id = flow_run_state_id)
            WHERE flow_run_state.id in (SELECT id FROM flow_run_state WHERE (data IS NOT 'null' AND data IS NOT NULL) AND (result_artifact_id IS NULL) LIMIT {batch_size});
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

    # drop state id columns after data migration
    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_artifact__task_run_state_id"))
        batch_op.drop_column("task_run_state_id")
        batch_op.drop_index(batch_op.f("ix_artifact__flow_run_state_id"))
        batch_op.drop_column("flow_run_state_id")

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.alter_column("data", new_column_name="_data")
    #     batch_op.drop_column('data')

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.alter_column("data", new_column_name="_data")
    #     batch_op.drop_column('data')


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.alter_column("_data", new_column_name="data")
        # batch_op.add_column(sa.Column('data', sqlite.JSON(), nullable=True))

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.alter_column("_data", new_column_name="data")
        # batch_op.add_column(sa.Column('data', sqlite.JSON(), nullable=True))

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_task_run_state__result_artifact_id__artifact"),
            type_="foreignkey",
        )
        batch_op.drop_index(batch_op.f("ix_task_run_state__result_artifact_id"))
        batch_op.drop_column("result_artifact_id")

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_flow_run_state__result_artifact_id__artifact"),
            type_="foreignkey",
        )
        batch_op.drop_index(batch_op.f("ix_flow_run_state__result_artifact_id"))
        batch_op.drop_column("result_artifact_id")

    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_artifact__updated"))
        batch_op.drop_index(batch_op.f("ix_artifact__task_run_id"))
        batch_op.drop_index(batch_op.f("ix_artifact__key"))
        batch_op.drop_index(batch_op.f("ix_artifact__flow_run_id"))

    op.drop_table("artifact")
