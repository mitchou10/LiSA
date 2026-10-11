"""baseline: services, users, tasks

Databases created before Alembic already contain these tables (they were made
by ``create_all``); each table is only created when missing, so existing
installs are simply stamped at this revision.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("services"):
        op.create_table(
            "services",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("version", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("queue", sa.String(length=255), nullable=True),
            sa.Column(
                "tags",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=False,
            ),
            sa.Column(
                "type",
                sa.Enum("GUARD", "ANALYSER", "OTHER", name="service_type"),
                nullable=False,
            ),
            sa.Column(
                "input_schema",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=False,
            ),
            sa.Column(
                "output_schema",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_services_name"), "services", ["name"], unique=False)
    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("username", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column(
                "role", sa.Enum("ADMIN", "USER", name="user_role"), nullable=False
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    if not inspector.has_table("tasks"):
        op.create_table(
            "tasks",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("parent_task_id", sa.Uuid(), nullable=True),
            sa.Column("service_id", sa.Uuid(), nullable=True),
            sa.Column("user_id", sa.String(length=255), nullable=False),
            sa.Column(
                "status",
                sa.Enum(
                    "PENDING",
                    "RUNNING",
                    "SUCCESS",
                    "ERROR",
                    "REVOKED",
                    name="task_status",
                ),
                nullable=False,
            ),
            sa.Column("progress", sa.Integer(), nullable=False),
            sa.Column(
                "input_data",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=False,
            ),
            sa.Column(
                "output_data",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=True,
            ),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["parent_task_id"], ["tasks.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["service_id"], ["services.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_tasks_parent_task_id"), "tasks", ["parent_task_id"], unique=False
        )
        op.create_index(
            op.f("ix_tasks_service_id"), "tasks", ["service_id"], unique=False
        )
        op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
        op.create_index(op.f("ix_tasks_user_id"), "tasks", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("tasks")
    op.drop_table("users")
    op.drop_table("services")
