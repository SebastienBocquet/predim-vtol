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


def main(argv: list[str] | None = None) -> None:
    from streamlit.web import cli as stcli  # noqa: PLC0415

    sys.argv = streamlit_argv(sys.argv[1:] if argv is None else argv)
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
