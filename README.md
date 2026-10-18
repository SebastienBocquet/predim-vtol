# predimrc_wrapper

Pre-sizing of RC VTOL aircraft (quadplane) and multicopters, with the PredimRC Excel
workbook in the loop for the wing aerodynamics.

- MVP scope, requirements, canvases and model cards: [`mvp/`](mvp/README.md).
- Full long-term specification: `docs/requirements/` and `spdd/`.

Install (Python 3.10–3.12; PredimRC needs Windows and Excel):

```bash
uv venv .venv --python 3.12
uv pip install -e ".[mdo,ui]" pytest
```
