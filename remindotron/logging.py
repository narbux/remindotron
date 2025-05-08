"""Remindotron - logging.py

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

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler
from rich.traceback import install

install(show_locals=False)


def get_logger() -> logging.Logger:
    file_formatter = logging.Formatter(
        fmt="%(asctime)s %(module)s:%(lineno)-4d %(levelname)-8s %(message)s"
    )
    file_handler = RotatingFileHandler(
        (Path.home() / ".cache/remindotron.log"), maxBytes=10240, backupCount=3
    )
    file_handler.setFormatter(file_formatter)

    rich_formatter = logging.Formatter(datefmt="[%X]", fmt="%(message)s")
    rich_handler = RichHandler(rich_tracebacks=True)
    rich_handler.setFormatter(rich_formatter)

    logger = logging.getLogger(__name__)
    logger.addHandler(hdlr=file_handler)
    logger.addHandler(hdlr=rich_handler)
    logger.setLevel(logging.INFO)

    return logger
