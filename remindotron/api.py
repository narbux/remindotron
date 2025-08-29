from datetime import date, datetime
from typing import Optional

from fastapi import Depends, FastAPI, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, sessionmaker

from remindotron.models import Recurring, Reminder, ReminderCategory

engine = create_engine(url="sqlite:///data/remindotron.db?journal_mode=wal")
SessionLocal = sessionmaker(bind=engine)


class ReminderCategoryBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str


class ReminderIn(BaseModel):
    name: str
    description: Optional[str]
    date: date
    priority: int
    recurring: Recurring
    category: ReminderCategoryBase


class ReminderBase(ReminderIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_occurrence: Optional[datetime]
    occurrence_count: int
    created: datetime


class ReminderCategoryOut(ReminderCategoryBase):
    id: int
    reminders: list[ReminderBase]


class ReminderOut(ReminderBase):
    category: ReminderCategoryBase


app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/reminders")
async def get_reminders(db: Session = Depends(get_db)) -> list[ReminderOut]:
    db_reminders = db.query(Reminder).all()
    response = [ReminderOut.model_validate(item) for item in db_reminders]
    return response


@app.post("/reminders")
async def create_reminder(
    new_reminder: ReminderIn, db: Session = Depends(get_db)
) -> Response:
    try:
        cat = (
            db.query(ReminderCategory)
            .where(ReminderCategory.name == new_reminder.category.name)
            .one()
        )
    except NoResultFound:
        cat = ReminderCategory(name=new_reminder.name)
        db.add(cat)
        db.commit()
        db.refresh(cat)
    item = Reminder(
        name=new_reminder.name,
        description=new_reminder.description,
        date=new_reminder.date,
        priority=new_reminder.priority,
        recurring=new_reminder.recurring,
        category=cat,
    )
    db.add(item)
    db.commit()
    return Response(status_code=status.HTTP_201_CREATED)


@app.get("/categories")
async def get_categories(
    db: Session = Depends(get_db),
) -> list[ReminderCategoryOut]:
    db_categories = db.query(ReminderCategory).all()
    response = [
        ReminderCategoryOut.model_validate(item) for item in db_categories
    ]
    return response


@app.get("/healthcheck")
async def healthcheck():
    return {"status": "ok"}
