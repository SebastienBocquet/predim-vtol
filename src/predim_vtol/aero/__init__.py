"""Aerodynamic backends of the wing-borne aircraft.

- ``simple`` (default): the Python model of :mod:`predim_vtol.aero.simple`, on any platform;
- ``predimrc`` (optional): the PredimRC workbook driven through Excel
  (:mod:`predim_vtol.aero.predimrc`), Windows only, behind the cache of :mod:`predim_vtol.aero.cache`.

A project asking for PredimRC where it cannot run (no Windows, Excel, xlwings or workbook)
is evaluated with the simple model, with a warning.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from predim_vtol.aero.base import AeroBackend
    from predim_vtol.aircraft.project import AeroSpec

LOGGER = logging.getLogger(__name__)

BACKENDS = ("simple", "predimrc")


def predimrc_unavailable(profile: str, folder: str | Path) -> str | None:
    """None when PredimRC can run for a profile, else the reason."""
    from predim_vtol.aero.predimrc import unavailable  # noqa: PLC0415

    return unavailable(profile, folder)


def backend_status(aero: AeroSpec, folder: str | Path) -> tuple[str, str | None]:
    """The backend that will evaluate a project and, when it is not the requested one or
    cannot run, the message to show.

    Returns:
        ``(backend, message)``: ``backend`` is ``simple`` or ``predimrc``.
    """
    if aero.backend == "predimrc":
        reason = predimrc_unavailable(aero.profile, folder)
        if reason is None:
            return "predimrc", None
        message = f"PredimRC unavailable ({reason}): the simple model is used."
    else:
        message = None
    from predim_vtol.aero.airfoils import airfoils  # noqa: PLC0415

    if aero.profile.casefold() not in {name.casefold() for name in airfoils("wing")}:
        return "simple", (
            f"The simple model has no airfoil '{aero.profile}'. "
            f"Available: {', '.join(sorted(airfoils('wing')))}."
        )
    return "simple", message


def open_aero_backend(
    aero: AeroSpec,
    folder: str | Path,
    cache_path: str | Path | None = None,
) -> AeroBackend:
    """The backend of a project's aerodynamics, to close after use.

    Args:
        aero: The project aero block (``backend`` and ``profile``).
        folder: The folder of the PredimRC workbooks.
        cache_path: The cache folder of the PredimRC evaluations; the settings one by default.

    Raises:
        KeyError: The simple model is used and has no airfoil of this name.
    """
    backend, message = backend_status(aero, folder)
    if message:
        LOGGER.warning(message)
    if backend == "predimrc":
        from predim_vtol.aero.cache import open_backend  # noqa: PLC0415

        return open_backend(aero.profile, folder, cache_path)
    from predim_vtol.aero.simple import SimpleAeroBackend  # noqa: PLC0415

    return SimpleAeroBackend(aero.profile)


def profiles(backend: str, folder: str | Path) -> list[str]:
    """Wing airfoils available with a backend: the simple model ones, or the workbooks
    ``PredimRC_<profile>.xls`` of the folder."""
    if backend == "predimrc":
        from predim_vtol.aero.predimrc import discover_profiles  # noqa: PLC0415

        return sorted(discover_profiles(folder))
    from predim_vtol.aero.airfoils import airfoils  # noqa: PLC0415

    return sorted(airfoils("wing"))
