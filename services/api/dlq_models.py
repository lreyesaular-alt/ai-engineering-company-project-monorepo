
from datetime import datetime, timezone

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class DeadLetterTask(SQLModel, table=True):
    __tablename__ = "dead_letter_tasks"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    task_id: str = Field(
        index=True,
        unique=True,
    )

    task_name: str

    retry_count: int

    error: str = Field(
        sa_column=Column(Text, nullable=False),
    )

    failed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
