"""Remindotron - models.py

Copyright (C) 2025 Marnix Enthoven <info@marnixenthoven.nl>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>."""

from datetime import date as DTDate
from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, mapped_column, relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.sql import func


class Recurring(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class Base(DeclarativeBase):
    pass


class ReminderCategory(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)
    reminders: Mapped[list["Reminder"]] = relationship(
        "Reminder", back_populates="category"
    )

    def __repr__(self) -> str:
        return f"<ReminderCategory {self.name}>"


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[Optional[str]] = mapped_column(default=None)
    date: Mapped[DTDate] = mapped_column(nullable=False)
    priority: Mapped[Optional[int]] = mapped_column(default=5)
    recurring: Mapped[Recurring] = mapped_column(
        SQLAlchemyEnum(Recurring), default=Recurring.YEARLY
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id")
    )
    last_occurrence: Mapped[Optional[datetime]] = mapped_column(default=None)
    occurrence_count: Mapped[int] = mapped_column(default=0)
    created: Mapped[datetime] = mapped_column(default=func.now())
    category: Mapped["ReminderCategory"] = relationship(
        "ReminderCategory", back_populates="reminders"
    )

    def __repr__(self) -> str:
        return f"<Reminder {self.name=} for {self.date}>"

    def __str__(self) -> str:
        return f"""\
The reminder for "{self.name}" {self.id} has the following data:
    description: {self.description}
    date: {self.date}
    priority: {self.priority}
    recurring: {str(self.recurring)}
    last occurence: {self.last_occurrence}
    times triggered: {self.occurrence_count}
    created on: {str(self.created)}"""
