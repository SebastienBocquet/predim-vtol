"""``predimrc-ui [streamlit options] [project.yaml]``: launch the Streamlit GUI."""

from __future__ import annotations

import sys
from pathlib import Path


def streamlit_argv(args: list[str]) -> list[str]:
    """Streamlit options (``--name value`` or ``--name=value``) first, the project file after ``--``."""
    options, rest = [], []
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            options.append(args[i])
            if (
                "=" not in args[i]
                and i + 1 < len(args)
                and not args[i + 1].startswith("--")
            ):
                options.append(args[i + 1])
                i += 1
        else:
            rest.append(args[i])
        i += 1
    app = Path(__file__).with_name("app.py")
    return ["streamlit", "run", str(app), *options, "--", *rest]


CONSOLE_CLOSING = (2, 5, 6)
"""CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT: the process is killed next."""


def on_console_event(event: int) -> bool:
    """Kill the Excel of PredimRC when the console closes, then let Windows end the process.

    Closing the console window ends Python a few seconds later without running the
    ``atexit`` handlers that quit Excel, which would stay open in the background.
    """
    if event in CONSOLE_CLOSING:
        from predimrc_wrapper.predimrc_wrapper import kill_open_excel  # noqa: PLC0415

        kill_open_excel()
    return False  # next handler: Ctrl+C keeps stopping Streamlit cleanly


def stop_excel_on_console_close() -> None:
    """Register :func:`on_console_event` (Windows; pywin32 comes with xlwings)."""
    if sys.platform != "win32":
        return
    try:
        import win32api  # noqa: PLC0415
    except ImportError:
        return
    win32api.SetConsoleCtrlHandler(on_console_event, True)


def main(argv: list[str] | None = None) -> None:
    from streamlit.web import cli as stcli  # noqa: PLC0415

    stop_excel_on_console_close()
    sys.argv = streamlit_argv(sys.argv[1:] if argv is None else argv)
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
