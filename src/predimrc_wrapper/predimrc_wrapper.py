"""Python wrapper of the PredimRC Excel workbook (aero backend of the MVP).

PredimRC is driven through xlwings (Windows, Excel 16). The workbook is opened in place,
read-only, and closed without saving, so the template is never modified. Macros must be
enabled because the polar relies on VBA functions (``Cxp2``, ``CxpFuse``, ``CxpStab``);
events are disabled so that ``Workbook_Open`` (which shows a modal form) does not run.

Example:
    >>> wing = WingGeometry(
    ...     root_chord=200.0,
    ...     tip_chord=[200.0, 185.0, 140.0, 50.0],
    ...     length=[285.0, 300.0, 180.0, 105.0],
    ...     le_offset=[0.0, 7.0, 40.0, 150.0],
    ...     twist=[0.0, 0.0, 0.0, 0.0],
    ...     dihedral=[0.0, 1.0, 1.0, 20.0],
    ... )
    >>> stab = StabGeometry(
    ...     root_chord=140.0,
    ...     tip_chord=[100.0],
    ...     length=[320.0],
    ...     le_offset=[170.0],
    ...     lever=360.0,
    ...     stab_height=0.0,
    ...     profile="Biconvexe fin",
    ...     opening="120",
    ...     lateral_gap=20.0,
    ... )
    >>> fus = FuselageGeometry(
    ...     length=760.0,
    ...     width=85.0,
    ...     height=115.0,
    ...     nose_lever=270.0,
    ...     shape="Profilée",
    ...     beam="Normale",
    ...     wing_pos="médiane",
    ...     incidence="aile",
    ...     accessory_surface=0.6,
    ...     accessory_shape="Non profilé",
    ... )
    >>> settings = Settings(mass=1920.0, static_margin=5.0, cz_reg=0.30)
    >>> with PredimRCWrapper(profile="SD7003", template_dir="./profiles") as w:
    ...     result = w.run(wing, stab, fus, settings)
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import string
import threading
import time
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Protocol

import numpy as np

if TYPE_CHECKING:
    from typing_extensions import Self

LOGGER = logging.getLogger(__name__)

G = 9.81
"""Gravity (m/s²), the value used by PredimRC."""

PROFILE_PREFIX = "PredimRC_"
PROFILE_SUFFIXES = (".xls", ".xlsx", ".xlsm")


def discover_profiles(folder: str | Path) -> dict[str, Path]:
    """Profiles of a folder: ``PredimRC_<profile>.xls|xlsx|xlsm`` (no dot in the profile name).

    Raises:
        PredimRCError: When two workbooks give the same profile.
    """
    found: dict[str, Path] = {}
    folder = Path(folder)
    if not folder.is_dir():
        return found
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in PROFILE_SUFFIXES or not path.name.startswith(
            PROFILE_PREFIX
        ):
            continue
        name = path.stem[len(PROFILE_PREFIX) :]
        if not name or "." in name:
            continue
        if name in found:
            msg = f"Two workbooks for the profile '{name}': {found[name].name} and {path.name}."
            raise PredimRCError(msg)
        found[name] = path
    return found


def workbook_path(folder: str | Path, profile: str) -> Path:
    """The workbook of a profile in a folder.

    Raises:
        FileNotFoundError: With the available profiles when the profile is unknown.
    """
    profiles = discover_profiles(folder)
    if profile not in profiles:
        msg = (
            f"No PredimRC workbook for the profile '{profile}' in {Path(folder).resolve()}. "
            f"Available: {sorted(profiles)} (files named {PROFILE_PREFIX}<profile>.xls)."
        )
        raise FileNotFoundError(msg)
    return profiles[profile]


_SHEET_GEOM = "3-Geometrie"
_SHEET_CALC = "Calculs1"

_TRAP_COLS = ["C", "D", "E", "F", "G"]

_WING_ROWS = {
    "tip_chord": 7,
    "length": 8,
    "le_offset": 9,
    "twist": 10,
    "dihedral": 11,
}

_STAB_ROWS = {
    "tip_chord": 16,
    "length": 17,
    "le_offset": 18,
}

#: Drop-down field -> (linked cell on 3-Geometrie, label list on Calculs1).
_DROPDOWNS: dict[str, tuple[str, str]] = {
    "stab.profile": ("G19", "L180:L185"),
    "stab.opening": ("C20", "E146:E161"),
    "fuselage.shape": ("G24", "D162:D164"),
    "fuselage.beam": ("G25", "E162:E165"),
    "fuselage.wing_pos": ("C26", "A168:A171"),
    "fuselage.incidence": ("E26", "AC1:AC2"),
    "fuselage.accessory_shape": ("G26", "D169:D171"),
}

_WING_OUTPUT_CELLS = {
    "total_surface": "L5",
    "mean_chord": "L6",
    "span_aero": "L7",
    "span_total": "L8",
    "aspect_ratio": "L9",
    "aspect_ratio_el": "L10",
}

_ATMOSPHERE_CELLS = {"altitude_m": "T29", "temperature_c": "T30", "density": "U30"}
"""Altitude (m), temperature (°C) inputs and density output of 3-Geometrie."""

_IMPOSED_SPEED_CELLS = {1: "AB29", 2: "AB30"}
"""Vx 1, Vx 2 inputs (km/h) of "Performances à vitesse imposée" (3-Geometrie)."""

_IMPOSED_BLOCK_ROWS = {1: (62, 75), 2: (77, 90)}
"""Rows of the V1 and V2 blocks of Calculs1 (Cz aile B, Vx C, Rx (N) AK, P (W) AQ)."""

_XL_CALCULATION_MANUAL = -4135
"""Excel ``xlCalculationManual``: one explicit recalculation per evaluation."""

_CZ_REG_STEP = 0.05
"""Resolution of the PredimRC trim Cz spinner (F30 = N32 / 20)."""


class PredimRCError(RuntimeError):
    """An error raised by the PredimRC workbook or by its automation."""


def _pad(values: list[float | None]) -> list[float | None]:
    """Pad a list of panel values to the 5 PredimRC panels with ``None``."""
    if len(values) > 5:
        msg = f"PredimRC accepts at most 5 panels, got {len(values)}."
        raise ValueError(msg)
    return list(values) + [None] * (5 - len(values))


# ---------------------------------------------------------------------------
# Input dataclasses (PredimRC units)
# ---------------------------------------------------------------------------


@dataclass
class WingGeometry:
    """Wing geometry, up to 5 panels (PredimRC units)."""

    root_chord: float
    """Root chord (mm), cell C6."""

    tip_chord: list[float]
    """Tip chord of each panel (mm), C7:G7."""

    length: list[float]
    """Span length of each panel (mm), C8:G8."""

    le_offset: list[float]
    """Leading-edge offset of each panel tip, "Flèche /BA" (mm), C9:G9."""

    twist: list[float]
    """Twist of each panel (deg), C10:G10."""

    dihedral: list[float]
    """Dihedral of each panel (deg), C11:G11."""

    def __post_init__(self) -> None:
        for attr in _WING_ROWS:
            setattr(self, attr, _pad(getattr(self, attr)))


@dataclass
class StabGeometry:
    """Horizontal stabiliser geometry (PredimRC units)."""

    root_chord: float
    """Root chord (mm), C15."""

    tip_chord: list[float]
    """Tip chord of each panel (mm), C16:G16."""

    length: list[float]
    """Length of each panel (mm), C17:G17."""

    le_offset: list[float]
    """Leading-edge offset of each panel tip (mm), C18:G18."""

    lever: float
    """Stabiliser lever (mm), C19."""

    stab_height: float
    """Stabiliser height (mm), E19."""

    profile: str
    """Stabiliser airfoil, PredimRC label (drop-down G19)."""

    opening: str
    """V-tail opening, PredimRC label such as "120" or "--- / 180" (drop-down C20)."""

    lateral_gap: float
    """Lateral gap (mm), E20."""

    def __post_init__(self) -> None:
        for attr in _STAB_ROWS:
            setattr(self, attr, _pad(getattr(self, attr)))


@dataclass
class FuselageGeometry:
    """Fuselage geometry (PredimRC units)."""

    length: float
    """Length (mm), C24."""

    width: float
    """Width (mm), E24."""

    height: float
    """Height (mm), E25."""

    nose_lever: float
    """Nose lever (mm), C25."""

    shape: str
    """Shape, PredimRC label (drop-down G24)."""

    beam: str
    """Tail beam, PredimRC label (drop-down G25)."""

    wing_pos: str
    """Wing position, PredimRC label (drop-down C26)."""

    incidence: str
    """Linked incidence, PredimRC label (drop-down E26)."""

    accessory_surface: float
    """Accessory frontal area (dm²), F26."""

    accessory_shape: str
    """Accessory shape, PredimRC label (drop-down G26)."""


@dataclass
class Settings:
    """Global settings."""

    mass: float
    """Total mass (g), C33."""

    static_margin: float
    """Static margin (% of MAC), spinner N31."""

    cz_reg: float
    """Trim lift coefficient, multiple of 0.05 (spinner N32 = cz_reg · 20)."""

    altitude_m: float | None = None
    """Flight altitude (m), T29; not written when None."""

    temperature_c: float | None = None
    """Air temperature (°C), T30; not written when None."""

    vx1_kmh: float | None = None
    """Imposed speed Vx 1 (km/h), AB29; not written when None."""

    vx2_kmh: float | None = None
    """Imposed speed Vx 2 (km/h), AB30; not written when None."""


@dataclass
class ImposedSpeed:
    """PredimRC "Performances à vitesse imposée" block at one speed, versus the wing Cz."""

    vx_m_s: float
    cz_wing: np.ndarray
    drag_n: np.ndarray
    power_w: np.ndarray

    def at_cz(self, cz: float, cz_max: float | None = None) -> tuple[float, float]:
        """Drag (N) and power (W) at a wing Cz, NaN outside the usable nodes (no extrapolation).

        Parabola through the three nearest nodes (the induced drag varies as Cz²). The nodes
        above ``cz_max`` (the last Cz of the trimmed polar) are dropped: the block grid
        (0.15 in airfoil Cz) can keep one node in the stall drag rise, where the polar has
        already stopped, and interpolating towards it overestimates the power.
        """
        keep = np.ones(len(self.cz_wing), dtype=bool)
        if cz_max is not None:
            keep = self.cz_wing <= cz_max * (1.0 + 1e-9)
        order = np.argsort(self.cz_wing[keep])
        x = self.cz_wing[keep][order]
        drag, power = self.drag_n[keep][order], self.power_w[keep][order]
        if not len(x) or not x[0] <= cz <= x[-1]:
            return float("nan"), float("nan")
        if len(x) < 3:
            return float(np.interp(cz, x, drag)), float(np.interp(cz, x, power))
        i = min(max(int(np.argmin(np.abs(x - cz))) - 1, 0), len(x) - 3)
        w = _lagrange_weights(x[i : i + 3], cz)
        return float(w @ drag[i : i + 3]), float(w @ power[i : i + 3])


def _lagrange_weights(x: np.ndarray, x0: float) -> np.ndarray:
    """Weights of the quadratic through three nodes at x0."""
    return np.array([
        np.prod([(x0 - x[j]) / (x[i] - x[j]) for j in range(3) if j != i])
        for i in range(3)
    ])


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@dataclass
class AeroResults:
    """Aerodynamic results of PredimRC (mass 1, airfoil 1 block of Calculs1)."""

    cz: np.ndarray
    """Wing lift coefficient of each valid polar point."""

    cx: np.ndarray
    """Total drag coefficient."""

    vx: np.ndarray
    """Horizontal speed (m/s)."""

    sink_rate: np.ndarray
    """Vertical speed (m/s, negative when sinking)."""

    finesse_vx: np.ndarray
    """Lift-to-drag ratio."""

    drag_n: np.ndarray
    """Drag (N)."""

    power_required_w: np.ndarray
    """Power required for level flight (W)."""

    v_min: float
    """Lowest valid polar speed (m/s), stall side."""

    v_min_power: float
    """Speed of minimum required power (m/s)."""

    v_max_finesse: float
    """Speed of maximum lift-to-drag ratio (m/s)."""

    mass_kg: float
    """Mass used for the polar (kg)."""

    cg: float
    """Centre of gravity (% of MAC)."""

    foyer: float
    """Neutral point (% of MAC)."""

    total_surface: float
    """Wing area (dm²)."""

    mean_chord: float
    """Mean chord (mm)."""

    span_aero: float
    """Aerodynamic span (mm)."""

    span_total: float
    """Total span (mm)."""

    aspect_ratio: float
    """Aspect ratio."""

    aspect_ratio_el: float
    """Elliptic-equivalent aspect ratio."""

    wing_loading: float = field(default=float("nan"))
    """Wing loading (g/dm²)."""

    rho: float = field(default=float("nan"))
    """Air density used by PredimRC (kg/m³), Calculs1!B1."""

    power_predimrc_w: np.ndarray = field(default_factory=lambda: np.zeros(0))
    """PredimRC's own level-flight power column P (W), Calculs1!AQ (same points as ``vx``)."""

    imposed: dict[int, ImposedSpeed] = field(default_factory=dict)
    """Imposed-speed blocks V1 and V2, when Vx 1 / Vx 2 were written."""

    altitude_m: float = field(default=float("nan"))
    """Altitude read back from PredimRC (m)."""

    temperature_c: float = field(default=float("nan"))
    """Temperature read back from PredimRC (°C)."""

    cg_mm: float = field(default=float("nan"))
    """CG giving the static margin entered (mm from the wing root leading edge), 3-Geometrie!D30."""

    neutral_point_mm: float = field(default=float("nan"))
    """Neutral point (mm from the wing root leading edge), 3-Geometrie!D31."""

    static_margin: float = field(default=float("nan"))
    """Static margin used by PredimRC (% of MAC), 3-Geometrie!D29."""

    tail_volume: float = field(default=float("nan"))
    """Tail volume coefficient, 3-Geometrie!L21 (NaN without a stabiliser)."""

    stab_incidence_deg: float = field(default=float("nan"))
    """Stabiliser incidence at the trim Cz, airfoil 1 (°), 3-Geometrie!J31."""

    longitudinal_dihedral_deg: float = field(default=float("nan"))
    """Longitudinal dihedral (angle between wing and stabiliser) at the trim Cz, airfoil 1 (°),
    3-Geometrie!J32."""

    @property
    def mac_mm(self) -> float:
        """Mean aerodynamic chord (mm), from the CG and neutral point in % of MAC and in mm."""
        d_pct = self.foyer - self.cg
        return (
            100.0 * (self.neutral_point_mm - self.cg_mm) / d_pct
            if d_pct
            else float("nan")
        )


def derive_drag(
    vx_kmh: np.ndarray, sink_rate: np.ndarray, mass_kg: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert the PredimRC speed polar into SI speed, drag and required power.

    Args:
        vx_kmh: The horizontal speeds (km/h).
        sink_rate: The vertical speeds (m/s).
        mass_kg: The mass (kg).

    Returns:
        The speeds (m/s), the drag (N) and the required power (W):
        ``D = m·g·|Vz| / V`` and ``P = D·V``.
    """
    vx = np.asarray(vx_kmh, dtype=float) / 3.6
    power = mass_kg * G * np.abs(np.asarray(sink_rate, dtype=float))
    return vx, power / vx, power


def _number(value) -> float:
    """A cell value as a float; NaN for "-" or an empty cell."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _valid(values: list) -> np.ndarray:
    """Convert a column read from Excel to floats, errors and blanks becoming NaN."""
    return np.array(
        [v if isinstance(v, (int, float)) else np.nan for v in values], dtype=float
    )


def _cell_value(value: object) -> object:
    """A value as written to and compared with a cell (numpy scalars as Python ones)."""
    return value.item() if isinstance(value, np.generic) else value


def _column_index(letters: str) -> int:
    """1-based index of a column ("A" -> 1, "AQ" -> 43)."""
    index = 0
    for c in letters:
        index = 26 * index + ord(c) - ord("A") + 1
    return index


class _Block:
    """The values of a rectangle of cells, read in one COM call.

    Args:
        sheet: The COM worksheet.
        col: The first column.
        row: The first row.
        last: The bottom-right cell, e.g. ``"AQ30"``.
    """

    def __init__(self, sheet, col: str, row: int, last: str) -> None:
        self.col0, self.row0 = _column_index(col), row
        # Value2 gives numbers as floats and cell errors (#DIV/0!, #N/A) as int codes.
        self.values = [
            [None if isinstance(v, int) else v for v in r]
            for r in sheet.Range(f"{col}{row}:{last}").Value2
        ]

    def cell(self, ref: str) -> object:
        letters = ref.rstrip(string.digits)
        return self.values[int(ref[len(letters) :]) - self.row0][
            _column_index(letters) - self.col0
        ]

    def column(
        self, col: str, r0: int | None = None, r1: int | None = None
    ) -> np.ndarray:
        """A column as floats (errors and blanks as NaN), rows r0 to r1 (all by default)."""
        j = _column_index(col) - self.col0
        rows = self.values[
            (0 if r0 is None else r0 - self.row0) : (
                None if r1 is None else r1 - self.row0 + 1
            )
        ]
        return _valid([r[j] for r in rows])


class AeroBackend(Protocol):
    """An aerodynamic backend for the wing-borne aircraft."""

    def evaluate(
        self,
        wing: WingGeometry,
        stab: StabGeometry,
        fus: FuselageGeometry,
        settings: Settings,
    ) -> AeroResults:
        """Evaluate the aerodynamics of a geometry."""

    def close(self) -> None:
        """Release the backend resources."""


class PredimRCWrapper:
    """Drive the PredimRC workbook with xlwings.

    Args:
        profile: The wing airfoil: the workbook ``PredimRC_<profile>.xls`` of the folder.
        template_dir: The folder of the PredimRC workbooks.
        visible: Whether to show Excel (debug).
    """

    def __init__(
        self,
        profile: str = "SD7003",
        template_dir: str | Path = "./profiles",
        visible: bool = False,
    ) -> None:
        self.template_path = workbook_path(template_dir, profile)
        self.profile = profile
        self.visible = visible
        self.last_eval_seconds = float("nan")
        self._app = None
        self._wb = None
        self._labels: dict[str, list[str]] = {}
        self._geom_api = self._calc_api = None
        self._written: dict[str, object] = {}
        """Values written in this session, by cell: an unchanged input is not written again."""

    # --- session -------------------------------------------------------------

    def __enter__(self) -> Self:
        import xlwings as xw  # noqa: PLC0415  (Excel only needed here)

        self._app = xw.App(visible=self.visible, add_book=False)
        try:
            self._app.display_alerts = False
            self._app.screen_updating = False
            self._app.api.AutomationSecurity = 1  # macros enabled (VBA functions)
            self._app.api.EnableEvents = False  # skip Workbook_Open modal form
            self._wb = self._app.books.open(
                str(self.template_path.resolve()), update_links=False, read_only=True
            )
            self._wb.api.Activate()
            self._app.api.Calculation = _XL_CALCULATION_MANUAL
            # Raw COM on cached sheets: ~1 ms per cell instead of ~20 ms through xlwings.
            self._geom_api = self._wb.sheets[_SHEET_GEOM].api
            self._calc_api = self._wb.sheets[_SHEET_CALC].api
            self._written = {}
            calc = self._wb.sheets[_SHEET_CALC]
            for name, (_, rng) in _DROPDOWNS.items():
                self._labels[name] = [
                    self._label_text(v) for v in calc[rng].value if v is not None
                ]
        except Exception:
            self.close()
            raise
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the workbook without saving and quit the Excel instance."""
        try:
            if self._wb is not None:
                self._wb.close()
        except Exception:  # ruff: ignore[blind-except]
            LOGGER.warning(
                "Could not close the PredimRC workbook cleanly.", exc_info=True
            )
        finally:
            self._wb = self._geom_api = self._calc_api = None
            self._written = {}
            if self._app is not None:
                try:
                    self._app.quit()
                except Exception:  # ruff: ignore[blind-except]
                    LOGGER.warning(
                        "Could not quit Excel cleanly; killing it.", exc_info=True
                    )
                    self._app.kill()
                self._app = None

    def is_alive(self) -> bool:
        """Whether the Excel session still answers (Excel may have been closed outside)."""
        if self._wb is None or self._app is None:
            return False
        try:
            _ = self._geom["C6"].value
        except Exception:  # ruff: ignore[blind-except]  (COM errors when Excel is gone)
            return False
        return True

    @staticmethod
    def _label_text(value: object) -> str:
        """Return the label of a drop-down entry as text ("120" for 120.0)."""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    # --- helpers -------------------------------------------------------------

    @property
    def _geom(self):
        return self._wb.sheets[_SHEET_GEOM]

    @property
    def _calc(self):
        return self._wb.sheets[_SHEET_CALC]

    def labels(self, field_name: str) -> list[str]:
        """Return the allowed labels of a drop-down field (e.g. ``"fuselage.shape"``)."""
        return list(self._labels[field_name])

    def _index_of(self, field_name: str, label: str) -> int:
        """Return the 1-based index of a drop-down label.

        Raises:
            PredimRCError: When the label is not allowed.
        """
        labels = self._labels[field_name]
        text = self._label_text(label)
        if text not in labels:
            msg = f"{field_name}: '{label}' is not a PredimRC label. Allowed: {labels}"
            raise PredimRCError(msg)
        return labels.index(text) + 1

    def _set(self, cell: str, value: object) -> None:
        """Write a cell or a row range of 3-Geometrie, unless it holds this value already."""
        if isinstance(value, list):
            value = tuple(tuple(_cell_value(v) for v in row) for row in value)
        else:
            value = _cell_value(value)
        if self._written.get(cell) == value:
            return
        self._written.pop(cell, None)
        try:
            self._geom_api.Range(cell).Value2 = value
        except Exception as error:
            msg = f"Cannot write {value!r} to {_SHEET_GEOM}!{cell}: {error}"
            raise PredimRCError(msg) from error
        self._written[cell] = value

    def _write_trapeze(self, rows: dict[str, int], obj: object) -> None:
        """Write panel values, one range write per row (columns C to G)."""
        for attr, row in rows.items():
            self._set(f"C{row}:G{row}", [getattr(obj, attr)])

    def _write_dropdown(self, field_name: str, label: str) -> None:
        cell, _ = _DROPDOWNS[field_name]
        self._set(cell, self._index_of(field_name, label))

    # --- inputs --------------------------------------------------------------

    def _write_wing(self, wing: WingGeometry) -> None:
        self._set("C6", wing.root_chord)
        self._write_trapeze(_WING_ROWS, wing)

    def _write_stab(self, stab: StabGeometry) -> None:
        self._set("C15", stab.root_chord)
        self._write_trapeze(_STAB_ROWS, stab)
        self._set("C19", stab.lever)
        self._set("E19", stab.stab_height)
        self._write_dropdown("stab.profile", stab.profile)
        self._write_dropdown("stab.opening", stab.opening)
        self._set("E20", stab.lateral_gap)

    def _write_fuselage(self, fus: FuselageGeometry) -> None:
        self._set("C24", fus.length)
        self._set("E24", fus.width)
        self._set("C25", fus.nose_lever)
        self._set("E25", fus.height)
        self._write_dropdown("fuselage.shape", fus.shape)
        self._write_dropdown("fuselage.beam", fus.beam)
        self._write_dropdown("fuselage.wing_pos", fus.wing_pos)
        self._write_dropdown("fuselage.incidence", fus.incidence)
        self._set("F26", fus.accessory_surface)
        self._write_dropdown("fuselage.accessory_shape", fus.accessory_shape)

    def _write_settings(self, settings: Settings) -> None:
        steps = settings.cz_reg / _CZ_REG_STEP
        if not np.isclose(steps, round(steps)):
            msg = f"cz_reg must be a multiple of {_CZ_REG_STEP}, got {settings.cz_reg}."
            raise ValueError(msg)
        self._set("C33", settings.mass)
        self._set("N31", settings.static_margin)
        self._set("N32", round(steps))
        if settings.altitude_m is not None:
            self._set(_ATMOSPHERE_CELLS["altitude_m"], settings.altitude_m)
        if settings.temperature_c is not None:
            self._set(_ATMOSPHERE_CELLS["temperature_c"], settings.temperature_c)
        for k, value in ((1, settings.vx1_kmh), (2, settings.vx2_kmh)):
            if value is not None:
                self._set(_IMPOSED_SPEED_CELLS[k], value)

    # --- outputs -------------------------------------------------------------

    def _read_outputs(self, mass_g: float) -> AeroResults:
        # One COM read per block of cells (a read costs ~1 ms whatever its size).
        polar = _Block(self._calc_api, "B", 5, "AQ30")
        cz = polar.column("B")
        cx = polar.column("AE")
        vx_kmh = polar.column("AH")
        sink = polar.column("AK")
        finesse = polar.column("AN")
        power_col = polar.column("AQ")
        mask = ~(np.isnan(vx_kmh) | np.isnan(sink))
        if not mask.any():
            msg = "PredimRC returned no valid polar point (check macros and inputs)."
            raise PredimRCError(msg)
        mass_kg = mass_g / 1000.0
        vx, drag, power = derive_drag(vx_kmh[mask], sink[mask], mass_kg)
        order = np.argsort(vx)
        vx, drag, power = vx[order], drag[order], power[order]
        cz, cx, sink, finesse, power_col = (
            a[mask][order] for a in (cz, cx, sink, finesse, power_col)
        )
        geom = _Block(self._geom_api, "C", 5, "AB34")
        metrics = {k: float(geom.cell(c)) for k, c in _WING_OUTPUT_CELLS.items()}
        return AeroResults(
            cz=cz,
            cx=cx,
            vx=vx,
            sink_rate=sink,
            finesse_vx=finesse,
            drag_n=drag,
            power_required_w=power,
            v_min=float(vx[0]),
            v_min_power=float(vx[np.argmin(power)]),
            v_max_finesse=float(vx[np.nanargmax(finesse)]),
            mass_kg=mass_kg,
            cg=100.0 * float(geom.cell("C30")),
            foyer=100.0 * float(geom.cell("C31")),
            wing_loading=float(geom.cell("C34")),
            rho=float(self._calc_api.Range("B1").Value2),
            power_predimrc_w=power_col,
            imposed=self._read_imposed(),
            altitude_m=float(geom.cell(_ATMOSPHERE_CELLS["altitude_m"])),
            temperature_c=float(geom.cell(_ATMOSPHERE_CELLS["temperature_c"])),
            cg_mm=_number(geom.cell("D30")),
            neutral_point_mm=_number(geom.cell("D31")),
            static_margin=100.0 * _number(geom.cell("D29")),
            tail_volume=_number(geom.cell("L21")),
            stab_incidence_deg=_number(geom.cell("J31")),
            longitudinal_dihedral_deg=_number(geom.cell("J32")),
            **metrics,
        )

    def _read_imposed(self) -> dict[int, ImposedSpeed]:
        r_first = min(r0 for r0, _ in _IMPOSED_BLOCK_ROWS.values())
        r_last = max(r1 for _, r1 in _IMPOSED_BLOCK_ROWS.values())
        block, out = _Block(self._calc_api, "B", r_first, f"AQ{r_last}"), {}
        for k, (r0, r1) in _IMPOSED_BLOCK_ROWS.items():
            cz = block.column("B", r0, r1)
            vx = block.column("C", r0, r1)
            drag = block.column("AK", r0, r1)
            power = block.column("AQ", r0, r1)
            ok = np.isfinite(cz) & np.isfinite(drag) & np.isfinite(power)
            if ok.any():
                out[k] = ImposedSpeed(
                    float(np.nanmedian(vx)), cz[ok], drag[ok], power[ok]
                )
        return out

    # --- public API ----------------------------------------------------------

    def run(
        self,
        wing: WingGeometry,
        stab: StabGeometry,
        fus: FuselageGeometry,
        settings: Settings,
    ) -> AeroResults:
        """Evaluate one geometry.

        Args:
            wing: The wing geometry.
            stab: The stabiliser geometry.
            fus: The fuselage geometry.
            settings: The global settings.

        Returns:
            The aerodynamic results.
        """
        if self._wb is None:
            msg = "PredimRCWrapper must be used as a context manager."
            raise PredimRCError(msg)
        start = time.perf_counter()
        self._write_wing(wing)
        self._write_stab(stab)
        self._write_fuselage(fus)
        self._write_settings(settings)
        self._app.calculate()
        result = self._read_outputs(settings.mass)
        self.last_eval_seconds = time.perf_counter() - start
        LOGGER.debug("PredimRC evaluation in %.3f s", self.last_eval_seconds)
        return result

    evaluate = run

    def run_parametric(self, cases: list[dict]) -> list[AeroResults]:
        """Evaluate several cases in the same Excel session.

        Args:
            cases: Mappings with the keys ``wing``, ``stab``, ``fus`` and ``settings``.

        Returns:
            The results, in the order of the cases.
        """
        return [self.run(**case) for case in cases]


def _co_initialize() -> None:
    import pythoncom  # noqa: PLC0415  (pywin32, installed with xlwings)

    pythoncom.CoInitialize()


class ExcelThreadBackend:
    """A PredimRC session living in its own thread, usable from any thread.

    Excel COM objects only work in the thread that created them, and Streamlit runs each
    rerun in a new thread: the workbook is opened, evaluated and closed by one worker
    thread, the callers wait for its result. Excel is started at the first evaluation.

    Args:
        profile: The wing airfoil: the workbook ``PredimRC_<profile>.xls`` of the folder.
        template_dir: The folder of the PredimRC workbooks.
        wrapper_factory: Builds the session in the worker thread (tests); a
            ``PredimRCWrapper`` by default.
    """

    def __init__(
        self,
        profile: str = "SD7003",
        template_dir: str | Path = "./profiles",
        wrapper_factory=None,
    ) -> None:
        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

        self.profile = profile
        self.template_dir = template_dir
        self._factory = wrapper_factory or (
            lambda: PredimRCWrapper(profile, template_dir).__enter__()
        )
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="predimrc-excel",
            initializer=None if wrapper_factory else _co_initialize,
        )
        self._wrapper = None
        self._excel_pid = None
        """Excel process, read in the Excel thread, to kill it when that thread is gone."""
        self._closed = False
        # Closed at interpreter exit before concurrent.futures stops its threads (``atexit``
        # handlers run after, when the Excel thread no longer takes work).
        threading._register_atexit(self.close)  # noqa: SLF001

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _call(self, function, *args, **kwargs):
        return self._executor.submit(function, *args, **kwargs).result()

    def _session(self):
        if self._wrapper is None:
            self._wrapper = self._factory()
            app = getattr(self._wrapper, "_app", None)
            self._excel_pid = getattr(app, "pid", None)
        return self._wrapper

    @property
    def last_eval_seconds(self) -> float:
        return (
            float("nan") if self._wrapper is None else self._wrapper.last_eval_seconds
        )

    def evaluate(
        self,
        wing: WingGeometry,
        stab: StabGeometry,
        fus: FuselageGeometry,
        settings: Settings,
    ) -> AeroResults:
        """Evaluate in the Excel thread (opening Excel at the first call)."""
        return self._call(lambda: self._session().evaluate(wing, stab, fus, settings))

    run = evaluate

    def is_alive(self) -> bool:
        """Whether the session answers; True before Excel is started."""
        return self._wrapper is None or self._call(self._wrapper.is_alive)

    def close(self) -> None:
        """Close the workbook and quit Excel in the Excel thread, then stop the thread."""

        def close() -> None:
            if self._wrapper is not None:
                self._wrapper.close()
                self._wrapper = None

        if self._closed:
            return
        self._closed = True
        try:
            self._call(close)
        except RuntimeError:  # executor already shut down: Excel is out of reach
            self._kill_excel()
        finally:
            self._executor.shutdown(wait=True)

    def _kill_excel(self) -> None:
        if self._wrapper is None or self._excel_pid is None:
            return
        LOGGER.warning(
            "Excel thread already stopped: killing Excel (pid %d).", self._excel_pid
        )
        with contextlib.suppress(OSError):  # already gone
            os.kill(self._excel_pid, signal.SIGTERM)
        self._wrapper = None
