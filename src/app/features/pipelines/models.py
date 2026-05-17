import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserProject(Base):
    __tablename__ = "user_projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    gitlab_project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    allure_results_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    custom_pipelines: Mapped[list["CustomPipeline"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    schedule_bookmarks: Mapped[list["ScheduleBookmark"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class CustomPipeline(Base):
    __tablename__ = "custom_pipelines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ref: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    variables: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    seeded_from_schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_pipeline_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_pipeline_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["UserProject"] = relationship(back_populates="custom_pipelines")


class ScheduleBookmark(Base):
    __tablename__ = "schedule_bookmarks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    schedule_id: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["UserProject"] = relationship(back_populates="schedule_bookmarks")


class AllureReport(Base):
    __tablename__ = "allure_reports"

    pipeline_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gitlab_project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
