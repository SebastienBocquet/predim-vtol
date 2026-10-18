from importlib.metadata import version
from pathlib import Path
import predimrc_wrapper as src_pkg

__version__ = version("predimrc_wrapper")

SRC_DIR = Path(src_pkg.__path__[0]).resolve()