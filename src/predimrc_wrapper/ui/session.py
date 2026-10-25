"""The PredimRC session of the GUI, kept between reruns (``st.cache_resource``)."""

from __future__ import annotations

import atexit
from typing import TYPE_CHECKING

import streamlit as st

from predimrc_wrapper.api import profiles_dir

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import Project


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
    of a context manager would; it is not called at shutdown, hence ``atexit`` (``close`` is
    idempotent).
    """
    from predimrc_wrapper.aero_cache import open_backend  # noqa: PLC0415

    backend = open_backend(profile, folder)
    atexit.register(backend.close)
    return backend


def backend_for(project: Project):
    """The PredimRC session of a quadplane (None for the other architectures)."""
    if project.architecture != "quadplane":
        return None
    return predimrc_session(project.aero.profile, str(profiles_dir()))
