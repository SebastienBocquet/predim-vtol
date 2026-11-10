# predimrc_wrapper

Pre-sizing of RC VTOL aircraft (quadplane) and multicopters, with the PredimRC Excel
workbook in the loop for the wing aerodynamics.

- Requirements (stable, all increments): [`docs/requirements/`](docs/requirements/index.md).
- Model cards (MIC): [`docs/models/`](docs/models/index.md).
- SPDD specifications per increment: [`spdd/mvp/`](spdd/mvp/README.md),
  [`spdd/inc2/`](spdd/inc2/README.md), [`spdd/inc3/`](spdd/inc3/README.md); analysis and
  first canvases in `spdd/analysis/`, `spdd/prompt/`.

Install (Python 3.10–3.12; PredimRC needs Windows and Excel):

```bash
uv venv .venv --python 3.12
uv pip install -e ".[mdo,ui]" pytest
```

Windows package (one-click installer, for users without a development environment):
`python packaging/windows/build_zip.py` writes the zip to `dist/`.

## Licence

Copyright (C) 2026 Sebastien Bocquet. Distributed under the GNU LGPL version 3:
[`LICENSE.txt`](LICENSE.txt) and [`LICENSES/GPL-3.0.txt`](LICENSES/GPL-3.0.txt).

**PredimRC is a separate work by Franck Aguerre, with its own terms of use. It is neither
included in this project nor covered by its licence.** See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
