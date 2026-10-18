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
