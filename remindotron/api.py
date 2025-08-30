import os
from datetime import date, datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, sessionmaker

from remindotron.models import Recurring, Reminder, ReminderCategory

load_dotenv()

DATABASE_LOCATION = os.getenv("DATABASE_LOCATION")
if not DATABASE_LOCATION:
    raise ValueError("Could not read database location from environment")

engine = create_engine(url=f"sqlite:///{DATABASE_LOCATION}?journal_mode=wal")
SessionLocal = sessionmaker(bind=engine)


class ReminderCategoryBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str


class ReminderCategoryIn(ReminderCategoryBase):
    pass


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
    return Response(
        f"Reminder {new_reminder.name} created",
        headers={"Content-Type": "text/plain"},
        status_code=status.HTTP_201_CREATED,
    )


@app.delete("/categories/{item_id}")
async def delete_category(
    item_id: int, db: Session = Depends(get_db)
) -> Response:
    try:
        item = db.query(Reminder).where(Reminder.id == item_id).one()
        db.delete(item)
        db.commit()
        return Response(
            f"Reminder with id #{item_id} deleted",
            status_code=status.HTTP_200_OK,
            headers={"Content-Type": "text/plain"},
        )
    except NoResultFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Reminder with id {item_id} not found"
        )


@app.get("/categories")
async def get_categories(
    db: Session = Depends(get_db),
) -> list[ReminderCategoryOut]:
    db_categories = db.query(ReminderCategory).all()
    response = [
        ReminderCategoryOut.model_validate(item) for item in db_categories
    ]
    return response


@app.post("/categories")
async def create_category(
    new_category: ReminderCategoryIn, db: Session = Depends(get_db)
) -> Response:
    try:
        db.query(ReminderCategory).where(
            ReminderCategory.name == new_category.name
        ).one()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Record already exists"
        )
    except NoResultFound:
        cat = ReminderCategory(name=new_category.name)
        db.add(cat)
        db.commit()
        db.refresh(cat)
    return Response(
        f"Category {cat.name} created",
        headers={"Content-Type": "text/plain"},
        status_code=status.HTTP_201_CREATED,
    )


@app.get("/healthcheck")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
