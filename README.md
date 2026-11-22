# Predim VTOL

Pre-sizing of RC VTOL aircraft: quadplanes (wing + lift rotors + pusher), tricopters with a
wing and tilting motors, and multicopters. Enter your aircraft (wing, motors, propellers,
battery, masses) and get the flight time of a mission (take-off, hover, transition,
cruise, landing with a battery reserve), the power drawn by each motor and the centre of
gravity.

It runs on your computer, in your web browser. No programming needed.

- **Wing aerodynamics built in**: a Python model computes the wing, stabiliser and fuselage
  polar on Windows, Linux and macOS. The PredimRC Excel workbook can be used instead
  (Windows, optional).
- **Propulsion from real data**: motor database, propeller thrust tests, battery discharge,
  cables and ESC losses.
- **Explore and optimise**: vary battery, propellers, motors or wing panels and find the
  longest flight time.

## Install

You need an internet connection during the installation (about 1 GB downloaded once). No
administrator rights, no existing Python.

### Windows: one click

1. Download `predim-vtol-<version>-windows.zip` from the
   [latest release](https://github.com/SebastienBocquet/predim-vtol/releases/latest).
2. Extract the whole zip into a folder (right-click → *Extract All*).
3. Double-click **`install.bat`**. If Windows SmartScreen warns about an unknown publisher,
   choose *More info*, then *Run anyway*.

The application opens in your browser at the end. Afterwards, start it with the
**Predim VTOL** shortcut on the desktop.

### Windows: one line

Open **PowerShell** (Start menu → type *PowerShell*), paste this line and press Enter:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://github.com/SebastienBocquet/predim-vtol/releases/latest/download/install-windows.ps1 | iex"
```

It downloads the same package as above and installs it.

### Linux and macOS: one line

Open a **terminal**, paste this line and press Enter:

```sh
curl -LsSf https://github.com/SebastienBocquet/predim-vtol/releases/latest/download/install.sh | sh
```

Then start the application with:

```sh
predim-vtol
```

(open a new terminal first if the command is not found). On Linux it is also in the
applications menu as *Predim VTOL*.

### Update, uninstall

- **Update**: run the installation again (the zip of the new version, or the same line).
  Your projects and settings are kept.
- **Uninstall**: Windows, `uninstall.bat` in `%LOCALAPPDATA%\Programs\predim_vtol`; Linux and
  macOS, `uv tool uninstall predim-vtol`. Your projects are kept.

## Your first study in 5 minutes

1. **Start the application.** It opens a page in your web browser. Keep the black console
   (or terminal) window open: closing it stops the application.
2. **Pick a template** in the left panel, *Start from a template*: for example
   *Quadplane 4+1 (wing, 4 lift + 1 pusher)*. Every field is filled with a working example.
3. **Adjust your aircraft** in the tabs, from left to right: configuration (motors and
   their positions, wing geometry), masses and battery, mission. Hover the small ? next to a
   field to see what it means and its unit.
4. **Press Run** in the left panel. The **Results** tab shows the flight time, the hover and
   cruise power, the battery state along the flight, and the warnings (motor too small,
   centre of gravity off, …).
5. **Save** your project with *Save project file* in the left panel, and reopen it later
   with *Open a project file*.

Then try the **Studies** page to vary a few parameters (battery mass, propeller diameter,
motor) and let the tool find the best combination.

## Wing aerodynamics: built-in model or PredimRC

By default the wing, stabiliser and fuselage are computed by the built-in model
(*Aerodynamic model* = `simple`). It uses the same geometry description as PredimRC, so a
PredimRC user finds the same fields.

To use [PredimRC](THIRD_PARTY_NOTICES.md) (by Franck Aguerre) instead, on Windows with
Microsoft Excel:

1. get the PredimRC workbook from its author and copy it, named `PredimRC_<airfoil>.xls`
   (for example `PredimRC_SD7003.xls`), into `Documents\predim_vtol\profiles`;
2. set *Aerodynamic model* to `predimrc` in the wing geometry of your project.

Where PredimRC cannot run, the built-in model is used and a message tells you so. The two
models give close stability results; the built-in model finds less drag at low speed
(about 25 % less minimum power): see the *Model cards* page of the application,
card MIC-AERO-SIMPLE.

## Where your files are

| What | Windows | Linux, macOS |
|---|---|---|
| Projects, studies, PredimRC workbooks | `Documents\predim_vtol` | the folder where you start `predim-vtol` |
| Settings, your motors, propellers, airfoils | `%USERPROFILE%\.predim_vtol` | `~/.predim_vtol` |

## Learn more

- In the application: the **Glossary** page (every quantity, its unit and source) and the
  **Model cards** page (how each model works, its limits and how it was checked). The
  cards are also in [`src/predim_vtol/mic/`](src/predim_vtol/mic/index.md).
- [Changes between versions](CHANGELOG.md).
- Developers: [contributing](CONTRIBUTING.md). Quick start:
  `uv venv --python 3.12 && uv pip install -e ".[ui]" --group dev && predim-vtol`.

## Licence

Copyright (C) 2026 Sebastien Bocquet. Distributed under the GNU LGPL version 3:
[`LICENSE.txt`](LICENSE.txt) and [`LICENSES/GPL-3.0.txt`](LICENSES/GPL-3.0.txt).

**PredimRC is a separate work by Franck Aguerre, with its own terms of use. It is neither
included in this project nor covered by its licence.** See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
