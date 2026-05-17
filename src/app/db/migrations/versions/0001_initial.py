"""initial tables

Revision ID: 0001
Revises:
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_projects",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("gitlab_project_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("allure_results_path", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_projects_user_id", "user_projects", ["user_id"])

    op.create_table(
        "custom_pipelines",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ref", sa.String(255), nullable=False, server_default="main"),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("seeded_from_schedule_id", sa.Integer(), nullable=True),
        sa.Column("last_pipeline_id", sa.Integer(), nullable=True),
        sa.Column("last_pipeline_status", sa.String(64), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["user_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_pipelines_user_id", "custom_pipelines", ["user_id"])

    op.create_table(
        "schedule_bookmarks",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["user_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schedule_bookmarks_user_id", "schedule_bookmarks", ["user_id"])

    op.create_table(
        "allure_reports",
        sa.Column("pipeline_id", sa.Integer(), nullable=False),
        sa.Column("gitlab_project_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="not_started"),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("pipeline_id"),
    )
    op.create_index("ix_allure_reports_gitlab_project_id", "allure_reports", ["gitlab_project_id"])


def downgrade() -> None:
    op.drop_index("ix_allure_reports_gitlab_project_id", "allure_reports")
    op.drop_table("allure_reports")
    op.drop_index("ix_schedule_bookmarks_user_id", "schedule_bookmarks")
    op.drop_table("schedule_bookmarks")
    op.drop_index("ix_custom_pipelines_user_id", "custom_pipelines")
    op.drop_table("custom_pipelines")
    op.drop_index("ix_user_projects_user_id", "user_projects")
    op.drop_table("user_projects")
