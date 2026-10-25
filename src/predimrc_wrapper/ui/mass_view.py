"""Masses and battery tab: mass recap by component and the battery mass ↔ capacity link."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import AircraftModel


def mass_rows(aircraft: AircraftModel) -> list[dict]:
    """Every mass of the budget: user items, motors, propellers, ESCs (separate and 4-in-1), cables, battery."""
    from predimrc_wrapper.propulsion.wiring import wiring_mass_kg  # noqa: PLC0415

    project = aircraft.project
    rows = [
        {
            "component": "user item",
            "item": f"{i.name} ({i.category})",
            "count": 1,
            "unit mass (g)": round(i.mass_g, 1),
            "mass (g)": round(i.mass_g, 1),
            "mass from": "entered",
        }
        for i in project.mass_items
    ]
    counts: dict[str, int] = {}
    separate: dict[str, int] = {}
    for m in project.motors:  # a tilting motor counts once
        counts[m.unit] = counts.get(m.unit, 0) + 1
        if not project.on_four_in_one(m):
            separate[m.unit] = separate.get(m.unit, 0) + 1
    for name, n in counts.items():
        spec = project.propulsion_units[name]
        record = aircraft.db.motor(spec.motor_id)
        for component, item, count, unit_g, origin in (
            (
                "motor",
                spec.motor_id,
                n,
                1000.0 * record.mass_kg
                if spec.motor_mass_g is None
                else spec.motor_mass_g,
                f"data sheet ({record.source})"
                if spec.motor_mass_g in (None, round(1000.0 * record.mass_kg, 3))
                else "entered (unit type)",
            ),
            (
                "propeller",
                spec.propeller_id or f"{spec.prop_diameter_in:g} in",
                n,
                spec.prop_mass_g,
                "entered (unit type)",
            ),
            (
                "ESC",
                f"separate ESC of '{name}'",
                separate.get(name, 0),
                spec.esc_mass_g,
                "entered (unit type)",
            ),
        ):
            if count == 0:  # every motor of the type on the 4-in-1 board
                continue
            rows.append({
                "component": component,
                "item": f"{item} — unit type '{name}'",
                "count": count,
                "unit mass (g)": round(unit_g, 1),
                "mass (g)": round(count * unit_g, 1),
                "mass from": origin,
            })
    if project.wiring is not None and project.wiring.lift_esc == "four_in_one":
        board_g = project.wiring.four_in_one_mass_g
        driven = [
            i + 1 for i, m in enumerate(project.motors) if project.on_four_in_one(m)
        ]
        rows.append({
            "component": "ESC",
            "item": f"4-in-1 ESC board — motors {', '.join(map(str, driven))}",
            "count": 1,
            "unit mass (g)": round(board_g, 1),
            "mass (g)": round(board_g, 1),
            "mass from": "entered (Power chain tab)",
        })
    wiring_g = 1000.0 * wiring_mass_kg(project)
    rows.append({
        "component": "cables",
        "item": "main, DC and phase cables (Power chain tab)",
        "count": 1,
        "unit mass (g)": round(wiring_g, 1),
        "mass (g)": round(wiring_g, 1),
        "mass from": "computed: copper + silicone insulation × lengths of the power chain",
    })
    battery_g = 1000.0 * aircraft.battery.p.mass_kg
    rows.append({
        "component": "battery",
        "item": f"{project.battery.chemistry} {project.battery.n_series}S",
        "count": 1,
        "unit mass (g)": round(battery_g, 1),
        "mass (g)": round(battery_g, 1),
        "mass from": "entered"
        if project.battery.mode == "mass"
        else "computed from the capacity (specific energy of the chemistry)",
    })
    return rows


def battery_text(aircraft: AircraftModel) -> str:
    """The derived battery quantity with the formula of the chemistry (MIC-PROP-BAT)."""
    spec = aircraft.project.battery
    b = aircraft.battery.p
    e_wh = aircraft.battery.energy_wh()
    v_nom = e_wh / (spec.n_series * b.capacity_ah) if b.capacity_ah else float("nan")
    rho_e = b.specific_energy_wh_kg
    if spec.mode == "mass":
        return (
            f"Mass {1000 * b.mass_kg:.0f} g × {rho_e:g} Wh/kg ({spec.chemistry}) = "
            f"**{e_wh:.1f} Wh** → capacity E / (n_s·V_nom) = {e_wh:.1f} / ({spec.n_series} × "
            f"{v_nom:.2f} V) = **{1000 * b.capacity_ah:.0f} mAh**. The capacity follows from the "
            "mass through the pack-level specific energy of the chemistry (MIC-PROP-BAT)."
        )
    return (
        f"Capacity {1000 * b.capacity_ah:.0f} mAh × {spec.n_series} × {v_nom:.2f} V = "
        f"**{e_wh:.1f} Wh** → mass E / {rho_e:g} Wh/kg ({spec.chemistry}) = "
        f"**{1000 * b.mass_kg:.0f} g**. The mass follows from the capacity through the "
        "pack-level specific energy of the chemistry (MIC-PROP-BAT)."
    )
