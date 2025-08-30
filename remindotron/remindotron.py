"""Remindotron - remindotron.py

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

import argparse
import logging
import os
import subprocess
from datetime import date as DTDate
from datetime import datetime
from pathlib import Path
from typing import Any

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from gotify import Gotify
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from sqlalchemy import create_engine
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import (
    joinedload,
    sessionmaker,
)

from remindotron import __version__
from remindotron.logging import get_logger
from remindotron.models import Base, Recurring, Reminder, ReminderCategory

### GLOBAL SETUP ###
load_dotenv(".env")
GOTIFY_URL = os.getenv("GOTIFY_URL")
GOTIFY_APP_TOKEN = os.getenv("GOTIFY_APP_TOKEN")
DATABASE_LOCATION = os.getenv("DATABASE_LOCATION")


console = Console()
logger = get_logger()
logging.getLogger("httpx").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.INFO)


### MAIN FUNCTIONS ###
def insert_reminder(**kwargs: Any) -> None:
    category_result = None

    if kwargs["type"]:
        category_name = kwargs["type"]
        with Session() as db:
            try:
                category_result = (
                    db.query(ReminderCategory)
                    .where(ReminderCategory.name == category_name)
                    .one()
                )
                logger.debug(f"Found category {category_name} already in db")
            except NoResultFound:
                logger.info(f"Category {category_name} not in db")
                answer = Confirm.ask(
                    f"Do you want to add {category_name} to the database?"
                )
                if answer:
                    logger.info(f"Adding category {category_name} to database")
                    category_result = ReminderCategory(name=category_name)

                    db.add(category_result)
                    db.commit()
                else:
                    logger.warning("Ignoring category")
    try:
        parsed_date = DTDate.fromisoformat(kwargs["date"])
    except ValueError as e:
        logger.error(f"Date should be of format YYYY-MM-DD: {e}")
        raise SystemExit(1)
    item = Reminder(
        name=kwargs["name"],
        description=kwargs["description"],
        date=parsed_date,
        priority=kwargs["priority"],
        recurring=kwargs["recurring"],
        category=category_result,
    )
    try:
        with Session() as db:
            db.add(item)
            db.commit()
            db.refresh(item)
        logger.info(f"Added {item.name} to database")
    except Exception as e:
        logger.error(f"Error querying database: {e}")
        raise SystemExit(1) from e


def show_all(**kwargs: Any) -> None:
    try:
        with Session() as db:
            result = db.query(Reminder).all()
    except Exception as e:
        logger.error(f"Error querying database: {e}")
        raise SystemExit(1) from e

    if not result:
        logger.error("No results found to show")
        raise SystemExit(1)

    table = Table(title="Reminders")
    table.add_column("name")
    table.add_column("description", max_width=15)
    table.add_column("date")
    table.add_column("priority")
    table.add_column("recurring")
    table.add_column("last occurrence")
    table.add_column("times triggered")
    table.add_column("created on")

    for item in result:
        table.add_row(
            item.name,
            item.description,
            str(item.date),
            str(item.priority),
            str(item.recurring),
            str(item.last_occurrence),
            str(item.occurrence_count),
            str(item.created),
        )
    console.print(table)


def send_gotify_notification(reminders: list[Reminder]) -> None:
    if not GOTIFY_URL or not GOTIFY_APP_TOKEN:
        logger.error("No valid Gotify credentials available")
        logger.debug(f"{GOTIFY_URL=}; {GOTIFY_APP_TOKEN}")
        raise SystemExit(1)
    gotify = Gotify(base_url=GOTIFY_URL, app_token=GOTIFY_APP_TOKEN)
    message = f"**{str(datetime.now().strftime('%d-%m-%Y'))}**\n\n"
    priority_calc = []
    for reminder in reminders:
        if reminder.category:
            message += (
                f"- {reminder.category.name.capitalize()}: {reminder.name}\n\n"
            )
            priority_calc.append(reminder.priority)

    extras = {"client::display": {"contentType": "text/markdown"}}

    gotify.create_message(
        message=message,
        title="Reminders for today",
        priority=(int(sum(priority_calc) / len(priority_calc))),
        extras=extras,
    )


def handle_cron_hit(reminders: list[Reminder]) -> None:
    try:
        with Session() as db:
            for item in reminders:
                result = db.get(Reminder, item.id)
                # SEND NOTIFICATION HERE
                if not result:
                    logger.error(
                        f"Could not retrieve reminder with id {item.id}"
                    )
                    raise SystemExit(1)

                # UPDATE OCCURENCE COUNT
                result.occurrence_count += 1

                # UPDATE DATE ACCORDING TO RECURRING VALUE
                match item.recurring:
                    case Recurring.ONCE:
                        pass
                    case Recurring.DAILY:
                        result.date = item.date + relativedelta(days=1)
                    case Recurring.WEEKLY:
                        result.date = item.date + relativedelta(weeks=1)
                    case Recurring.MONTHLY:
                        result.date = item.date + relativedelta(months=1)
                    case Recurring.QUARTERLY:
                        result.date = item.date + relativedelta(months=3)
                    case Recurring.YEARLY:
                        result.date = item.date + relativedelta(years=1)
                    case _:
                        logger.error("item.recurring not found in Enum")
                        raise ValueError("item.recurring not found in Enum")

                # UPDATE LAST_OCCURRENCE
                result.last_occurrence = datetime.now()
            db.commit()
    except Exception as e:
        logger.error(f"Error querying database: {e}")
        raise SystemExit(1) from e


def run_date_comparison(**kwargs: Any) -> None:
    try:
        with Session() as db:
            items = (
                db.query(Reminder)
                .where(Reminder.date == datetime.now().date())
                .options(joinedload(Reminder.category))
                .all()
            )
    except Exception as e:
        logger.error(f"Error querying database: {e}")
        raise SystemExit(1) from e

    if items:
        logger.info(f"Found reminders for today: {items}")
        handle_cron_hit(items)
        if not kwargs["silent"]:
            logger.info("Sending notification through Gotify")
            send_gotify_notification(items)
        else:
            logger.warning(
                "The sending of notifications will be skipped in this run"
            )
    else:
        logger.info("No items found for today")


def check_or_create_db(db_path: Path) -> bool:
    just_created = False

    if not db_path.exists():
        answer = Confirm.ask(
            f"Database doesn't seem to exist, do you want to create it at {db_path}?"
        )
        if not answer:
            logger.critical(
                "Can't continue without a database, add --database option to command or create a new database."
            )
            raise SystemExit(1)
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_path.touch(exist_ok=True)
            just_created = True
        except Exception as e:
            logger.critical(
                f"Error: Cannot create or access database file at {db_path}"
            )
            raise SystemExit(1) from e

    try:
        with db_path.open("rb") as f:
            header = f.read(16)
            if (
                header and header != b"SQLite format 3\x00"
            ):  # Check if the file is a valid SQLite file (if it's not empty)
                logger.critical(
                    f"File at {db_path} exists and is not a valid SQLite database."
                )
                raise SystemExit(1)
    except Exception as e:
        logger.critical(f"Error while checking SQLite header: {e}")
        raise SystemExit(1) from e

    return just_created


def check_linger() -> None:
    try:
        check_linger = subprocess.run(
            ("loginctl", "show-user", os.getlogin(), "--property=Linger"),
            text=True,
            check=True,
            stdout=subprocess.PIPE,
        )
        if "Linger=yes" not in check_linger.stdout:
            raise subprocess.SubprocessError("Linger not enabled")
    except subprocess.SubprocessError as e:
        logger.warning(e)

        warning_text = Text.from_ansi(
            "\33[31mWARNING! Lingering for tracker is not enabled, please run as root:\n\t\33[34m$ loginctl enable-linger $USER"
        )
        console.print(warning_text)


def install_systemd_units(**kwargs: Any) -> None:
    gotify_url = Prompt.ask("What is your Gotify server url?")
    gotify_token = Prompt.ask("What is your Gotify token?")
    logger.warning(
        "The url and token you entered will be saved plaintext to the systemd service unit!"
    )
    service_file = f"""\
[Unit]
Description=Run Remindotron
Wants=network-online.target
After=network-online.target

[Service]
ExecStart=%h/.local/bin/remindotron --database {Path(kwargs["database"]).expanduser().resolve()} run
Environment=GOTIFY_URL={gotify_url}
Environment=GOTIFY_APP_TOKEN={gotify_token}
Type=oneshot

[Install]
WantedBy=default.target
"""
    timer_file = """\
[Unit]
Description=Run Remindotron daily

[Timer]
OnCalendar=Mon..Fri 08:30
OnCalendar=Sat,Sun 11:00
Persistent=True

[Install]
WantedBy=timers.target
"""
    systemd_user_dir = Path.home() / ".config/systemd/user"
    service_file_path = systemd_user_dir / "remindotron.service"
    timer_file_path = systemd_user_dir / "remindotron.timer"

    if not systemd_user_dir.exists():
        systemd_user_dir.mkdir(parents=True, exist_ok=True)
    if not service_file_path.exists():
        service_file_path.write_text(service_file, encoding="utf-8")
    if not timer_file_path.exists():
        timer_file_path.write_text(timer_file, encoding="utf-8")

    try:
        enable_tracker = subprocess.run(
            ["systemctl", "--user", "enable", "--now", "remindotron.timer"],
            stdout=subprocess.DEVNULL,
        )
        enable_tracker.check_returncode()
        check_linger()
    except subprocess.SubprocessError as e:
        logger.error(f"Failed to enable the remindotron systemd timer: {e}")
        raise SystemExit(1) from e


def remove_systemd_units(**kwargs: Any) -> None:
    answer = Confirm.ask(
        "Are you sure you want to uninstall the systemd unit files and stop the timer?"
    )
    if answer:
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", "remindotron.timer"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        systemd_user_dir = Path.home() / ".config/systemd/user"
        (systemd_user_dir / "remindotron.service").unlink(missing_ok=True)
        (systemd_user_dir / "remindotron.timer").unlink(missing_ok=True)


### ARGUMENTPARSER ###
def get_arguments() -> dict[str, Any]:
    parser = argparse.ArgumentParser(prog="Remindotron")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show version",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="show debug information",
    )
    subparsers = parser.add_subparsers(required=True)

    insert_parser = subparsers.add_parser(
        "insert", help="Insert new item in database"
    )
    insert_parser.set_defaults(func=insert_reminder)
    insert_parser.add_argument("name", help="name or title of new reminder")
    insert_parser.add_argument(
        "date", help="the date to trigger the new reminder"
    )
    insert_parser.add_argument(
        "--recurring",
        choices=list(Recurring),
        help="type of recurrence (default: yearly)",
    )
    insert_parser.add_argument(
        "--description", help="description of the new reminder (optional)"
    )
    insert_parser.add_argument(
        "--priority", type=int, help="priority of the new reminder (optional)"
    )
    insert_parser.add_argument("--type", help="category of the reminder")

    show_all_parser = subparsers.add_parser(
        "show", help="Show all database items"
    )
    show_all_parser.set_defaults(func=show_all)

    run_parser = subparsers.add_parser("run", help="Run the cronjob")
    run_parser.set_defaults(func=run_date_comparison)
    run_parser.add_argument(
        "--silent",
        action="store_true",
        help="do not send external notifications",
    )

    install_parser = subparsers.add_parser(
        "install", help="Install systemd unit files"
    )
    install_parser.set_defaults(func=install_systemd_units)

    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Remove systemd unit files"
    )
    uninstall_parser.set_defaults(func=remove_systemd_units)

    return vars(parser.parse_args())


def main() -> None:
    logger.setLevel(logging.INFO)

    arguments = get_arguments()

    if arguments["debug"]:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    ### Check and setup database ###
    if not DATABASE_LOCATION:
        raise ValueError("Could not find database location in environment")
    db_path = Path(DATABASE_LOCATION).expanduser().resolve()
    empty_database = check_or_create_db(db_path)

    global Session
    engine = create_engine(
        url=f"sqlite:///{db_path}?journal_mode=wal",
        echo=arguments["debug"],
    )
    Session = sessionmaker(bind=engine)

    if empty_database or db_path.stat().st_size == 0:
        logger.info("Databasefile empty; populating it now...")
        Base.metadata.create_all(bind=engine)

    ### Start requested function ###
    arguments["func"](**arguments)


if __name__ == "__main__":
    main()
