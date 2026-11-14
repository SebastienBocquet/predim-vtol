from importlib.metadata import version
from pathlib import Path

import predim_vtol as src_pkg

__version__ = version("predim-vtol")

SRC_DIR = Path(src_pkg.__path__[0]).resolve()
