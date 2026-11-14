"""The aerodynamic backend of the GUI; the PredimRC session is kept between reruns
(``st.cache_resource``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from predim_vtol.api import profiles_dir

if TYPE_CHECKING:
    from predim_vtol.aircraft import Project


def _release_session(backend) -> None:
    backend.close()


def _session_alive(backend) -> bool:
    """Whether Excel still answers; a dead session is closed here, since Streamlit discards
    an entry failing ``validate`` without calling ``on_release``."""
    if backend.is_alive():
        return True
    backend.close()
    return False


@st.cache_resource(
    max_entries=1,
    validate=_session_alive,
    on_release=_release_session,
)
def predimrc_session(profile: str, folder: str):
    """The PredimRC backend of the whole GUI: Excel in its own thread (each rerun runs in a new
    thread, COM objects stay in theirs), behind the HDF5 cache.

    One Excel at a time (another profile or folder releases the previous one); recreated when
    Excel no longer answers (closed outside). ``on_release`` closes Excel as the ``__exit__``
    of a context manager would; at shutdown, ``ExcelThreadBackend`` closes it itself.
    """
    from predim_vtol.aero.cache import open_backend  # noqa: PLC0415

    return open_backend(profile, folder)


def backend_for(project: Project):
    """The aerodynamic backend of a quadplane (None for the other architectures): the
    PredimRC session when the project asks for it and it can run, else the simple model."""
    if project.architecture != "quadplane":
        return None
    from predim_vtol.aero import backend_status  # noqa: PLC0415

    backend, _ = backend_status(project.aero, profiles_dir())
    if backend == "predimrc":
        return predimrc_session(project.aero.profile, str(profiles_dir()))
    from predim_vtol.aero.simple import SimpleAeroBackend  # noqa: PLC0415

    return SimpleAeroBackend(project.aero.profile)
