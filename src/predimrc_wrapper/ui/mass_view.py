"""Masses and battery tab: mass recap by component and the battery mass ↔ capacity link."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import AircraftModel


def mass_rows(aircraft: AircraftModel) -> list[dict]:
    """Every mass of the budget: user items, motors, propellers, ESCs, cables, battery."""
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
    for m in project.motors:  # a tilting motor counts once
        counts[m.unit] = counts.get(m.unit, 0) + 1
    for name, n in counts.items():
        spec = project.propulsion_units[name]
        record = aircraft.db.motor(spec.motor_id)
        for component, item, unit_g, origin in (
            (
                "motor",
                spec.motor_id,
                1000.0 * record.mass_kg,
                f"data sheet ({record.source})",
            ),
            (
                "propeller",
                spec.propeller_id or f"{spec.prop_diameter_in:g} in",
                spec.prop_mass_g,
                "entered (unit type)",
            ),
            ("ESC", f"ESC of '{name}'", spec.esc_mass_g, "entered (unit type)"),
        ):
            rows.append({
                "component": component,
                "item": f"{item} — unit type '{name}'",
                "count": n,
                "unit mass (g)": round(unit_g, 1),
                "mass (g)": round(n * unit_g, 1),
                "mass from": origin,
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
