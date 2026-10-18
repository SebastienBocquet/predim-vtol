"""User data folder: ``$PREDIMRC_USER_DATA``, else ``~/.predimrc_wrapper/data``."""

from __future__ import annotations

import os
from pathlib import Path


def user_data_dir() -> Path:
    """Folder of the user data files merged with the shipped ones (may not exist)."""
    return Path(os.environ.get("PREDIMRC_USER_DATA", Path.home() / ".predimrc_wrapper" / "data"))
