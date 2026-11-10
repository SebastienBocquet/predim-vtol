# Third-party notices

predimrc_wrapper is distributed under the GNU LGPL version 3 (`LICENSE.txt`, which
supplements the GNU GPL version 3, `LICENSES/GPL-3.0.txt`). That licence covers this
project only, not the components below, which keep their own terms.

## PredimRC

PredimRC is the work of Franck Aguerre (RC Aero Lab, <https://www.rcaerolab.eu>). It is
**not part of this project and not covered by its licence**. This project is not affiliated
with or endorsed by its author; it drives the workbook through Microsoft Excel.

The source repository does not contain PredimRC. The Windows zip may include
`predimrc/PredimRC_SD7003.xls`: PredimRC v2.64f, by Franck Aguerre, set up with the SD7003
airfoil and saved by the author of this project. Its release note is shipped as
`LICENSES/PredimRC-ReleaseNote.txt`. It stays under the terms of its author, below.

The terms of PredimRC are not consistent between its documents. The user guide of
v2.64a (August 2019, page 3), the one shipped with v2.64f, states:

> PredimRC est réservé à un usage privé, et ne peut donc être ni copié, ni distribué, ni
> utilisé dans le cadre d'une application professionnelle ou commerciale sans l'avis de
> l'auteur. De même, ce logiciel est livré en l'état […]

Its release note says instead "devient open-source (licence GNU)" for v2.50 (2013) and
"passage à licence Creative Commons" for v2.60 (2018), without naming the Creative Commons
licence, and no licence text comes with it. Check the terms given with your own version of
PredimRC.

`src/predimrc_wrapper/data/drag_shapes.yaml` records three accessory drag coefficients read
from PredimRC by `tools/extract_drag_shapes.py`, with their source. They are not covered by
the LGPL.

## Microsoft Excel

Required for the PredimRC evaluations, not included, licensed separately by Microsoft.

## VIMSEO

`src/predimrc_wrapper/runs/{collection,operations,query}.py` are ported from VIMSEO,
Copyright 2021 IRT Saint Exupery, under the GNU LGPL version 3.

## uv

`uv.exe`, shipped in the Windows zip to run the installation, is by Astral Software Inc.,
under the MIT or Apache 2.0 licence (`LICENSES/uv-MIT.txt`, `LICENSES/uv-Apache-2.0.txt`).
<https://github.com/astral-sh/uv>

## Python and the Python packages

The Windows installer downloads a CPython build and the packages pinned in
`requirements.txt` from their public indexes. Each one keeps its own licence, whose text is
installed with it (`venv/Lib/site-packages/<package>-<version>.dist-info`). Most are under
permissive licences (BSD, MIT, Apache 2.0, PSF). Those with reciprocal terms are:

- GNU LGPL 3: GEMSEO, OpenTURNS, SPGL1;
- Mozilla Public License 2.0: certifi, tqdm (with MIT).

xlwings is used under its BSD licence; its separately licensed PRO features
(`LICENSE_PRO.txt`) are not used.
