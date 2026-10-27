"""text replacements and corrected boxes of a run

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_by", sa.String(length=255), nullable=False),
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
    ]


def upgrade() -> None:
    op.create_table(
        "text_replacements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=2000), nullable=False),
        sa.Column("replacement", sa.String(length=255), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "key"),
    )
    op.create_index(
        op.f("ix_text_replacements_run_id"), "text_replacements", ["run_id"]
    )
    op.create_index(
        op.f("ix_text_replacements_created_by"), "text_replacements", ["created_by"]
    )

    op.create_table(
        "box_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("bbox_index", sa.Integer(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "page_number", "entity_id", "bbox_index"),
    )
    op.create_index(op.f("ix_box_overrides_run_id"), "box_overrides", ["run_id"])
    op.create_index(
        op.f("ix_box_overrides_created_by"), "box_overrides", ["created_by"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_box_overrides_created_by"), table_name="box_overrides")
    op.drop_index(op.f("ix_box_overrides_run_id"), table_name="box_overrides")
    op.drop_table("box_overrides")
    op.drop_index(
        op.f("ix_text_replacements_created_by"), table_name="text_replacements"
    )
    op.drop_index(op.f("ix_text_replacements_run_id"), table_name="text_replacements")
    op.drop_table("text_replacements")
