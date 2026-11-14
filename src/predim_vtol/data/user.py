"""User data folder: ``$PREDIM_VTOL_USER_DATA``, else ``~/.predim_vtol/data``."""

from __future__ import annotations

import os
from pathlib import Path

from predim_vtol.settings import home_dir


def user_data_dir() -> Path:
    """Folder of the user data files merged with the shipped ones (may not exist)."""
    return Path(os.environ.get("PREDIM_VTOL_USER_DATA", home_dir() / "data"))
