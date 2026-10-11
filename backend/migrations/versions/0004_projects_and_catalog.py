"""projects and what they look for (classifications, entities, relations, safety)

Adds the ``projects`` table, the definition tables the detection services run
(with their labels) and an optional ``project_id`` on tasks and files.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

THRESHOLD_CHECK = "threshold IS NULL OR (threshold >= 0 AND threshold <= 1)"


def _timestamps() -> list[sa.Column]:
    return [
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
        sa.Column("created_by", sa.String(length=255), nullable=False),
    ]


def _project_id() -> sa.Column:
    return sa.Column(
        "project_id",
        sa.Uuid(),
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )


def _definition_id(parent: str) -> sa.Column:
    return sa.Column(
        "definition_id",
        sa.Uuid(),
        sa.ForeignKey(f"{parent}.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("created_by", "name", name="uq_project_name"),
    )
    op.create_index("ix_projects_created_by", "projects", ["created_by"])

    # -- classification -------------------------------------------------------
    op.create_table(
        "classification_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        _project_id(),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("multi_label", sa.Boolean(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_classification_name"),
        sa.CheckConstraint(THRESHOLD_CHECK, name="ck_classification_threshold"),
    )
    op.create_index(
        "ix_classification_definitions_project_id",
        "classification_definitions",
        ["project_id"],
    )
    op.create_index(
        "ix_classification_definitions_created_by",
        "classification_definitions",
        ["created_by"],
    )
    op.create_table(
        "classification_labels",
        sa.Column("id", sa.Uuid(), nullable=False),
        _definition_id("classification_definitions"),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("definition_id", "name", name="uq_classification_label"),
    )
    op.create_index(
        "ix_classification_labels_definition_id",
        "classification_labels",
        ["definition_id"],
    )

    # -- entity extraction ----------------------------------------------------
    op.create_table(
        "entity_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        _project_id(),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("LOW", "MEDIUM", "HIGH", name="entity_severity"),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.Enum("ALLOW", "REDACT", "BLOCK", name="entity_action"),
            nullable=False,
        ),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "label", name="uq_entity_label"),
        sa.CheckConstraint(THRESHOLD_CHECK, name="ck_entity_threshold"),
    )
    op.create_index(
        "ix_entity_definitions_project_id", "entity_definitions", ["project_id"]
    )
    op.create_index(
        "ix_entity_definitions_created_by", "entity_definitions", ["created_by"]
    )

    # -- relation extraction --------------------------------------------------
    op.create_table(
        "relation_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        _project_id(),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_relation_name"),
        sa.CheckConstraint(THRESHOLD_CHECK, name="ck_relation_threshold"),
    )
    op.create_index(
        "ix_relation_definitions_project_id", "relation_definitions", ["project_id"]
    )
    op.create_index(
        "ix_relation_definitions_created_by", "relation_definitions", ["created_by"]
    )

    # -- safety ---------------------------------------------------------------
    op.create_table(
        "safety_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        _project_id(),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("multi_label", sa.Boolean(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_safety_name"),
        sa.CheckConstraint(THRESHOLD_CHECK, name="ck_safety_threshold"),
    )
    op.create_index(
        "ix_safety_definitions_project_id", "safety_definitions", ["project_id"]
    )
    op.create_index(
        "ix_safety_definitions_created_by", "safety_definitions", ["created_by"]
    )
    op.create_table(
        "safety_labels",
        sa.Column("id", sa.Uuid(), nullable=False),
        _definition_id("safety_definitions"),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_ok", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("definition_id", "name", name="uq_safety_label"),
    )
    op.create_index(
        "ix_safety_labels_definition_id", "safety_labels", ["definition_id"]
    )

    # -- tasks and files can belong to a project ------------------------------
    for table in ("tasks", "files"):
        op.add_column(
            table,
            sa.Column(
                "project_id",
                sa.Uuid(),
                sa.ForeignKey("projects.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])


def downgrade() -> None:
    for table in ("files", "tasks"):
        op.drop_index(f"ix_{table}_project_id", table_name=table)
        op.drop_column(table, "project_id")
    for table in (
        "safety_labels",
        "safety_definitions",
        "relation_definitions",
        "entity_definitions",
        "classification_labels",
        "classification_definitions",
        "projects",
    ):
        op.drop_table(table)
    sa.Enum(name="entity_action").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="entity_severity").drop(op.get_bind(), checkfirst=True)
