# MVP — Propulsion (PROP)

### REQ-PROP-001 — LiPo and Li-ion batteries are modelled

- **Statement:** The system shall model LiPo and Li-ion packs by pack-level specific
  energy, full / nominal / cut-off cell voltages, internal resistance per cell, maximum
  continuous discharge rate and usable fraction, with overridable defaults.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — `tests/propulsion/test_battery.py`.
- **Satisfied by:** MVP-003

### REQ-PROP-002 — A battery is defined by its cells or by its mass

- **Statement:** A battery shall be defined either by series count and capacity, or by
  series count and mass; the other quantities are derived.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — exact capacity → mass → capacity round trip.
- **Satisfied by:** MVP-003

### REQ-PROP-003 — The motor operating point is computed from its constants

- **Statement:** The system shall compute current, voltage, electric power and
  efficiency of a brushless motor from Kv, winding resistance, no-load current and the
  required torque and speed, and report the current and power margins.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — Q = 0 ⇒ I = I₀; efficiency < 1; undersized motor ⇒ negative
  current margin.
- **Satisfied by:** MVP-003

### REQ-PROP-004 — The propeller is modelled by momentum theory (MVP)

- **Statement:** In the MVP, the propeller is modelled by its diameter, mass, a figure
  of merit in hover (default 0.65) and a constant propulsive efficiency in cruise
  (default 0.70); rotation speed is estimated from a static thrust coefficient.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — with FM = 1, hover power equals the ideal momentum power.
- **Satisfied by:** MVP-003
- **Deferred:** CT/CP(J) tables and the PredimRC "propeller choice" fallback.

### REQ-PROP-005 — The hover power is computed per rotor

- **Statement:** The system shall compute the thrust per rotor (weight × download
  factor / rotor count) and the resulting shaft, electric and battery power, at the air
  density of the flight altitude.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — P ∝ T^1.5, P ∝ ρ^−0.5, P ∝ D^−1 (model-form tests).
- **Satisfied by:** MVP-003, MVP-005

### REQ-PROP-006 — The cruise power is computed from the drag

- **Statement:** The system shall compute the battery power in level cruise from the
  drag, the propeller, motor and ESC efficiencies (ESC efficiency constant, default
  0.95) and the avionics power.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — P_b ≥ P_el ≥ P_shaft ≥ T·V.
- **Satisfied by:** MVP-003, MVP-005
- **Deferred:** η_esc as a function of duty cycle (REQ-PROP-010), wiring (REQ-PROP-009).

### REQ-PROP-008 — Operating limits are reported as margins

- **Statement:** The system shall report, at the most demanding segment, the margins
  on motor current, battery discharge rate, battery voltage under load and lift
  thrust-to-weight (minimum 1.5 by default).
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — undersized motor or battery ⇒ negative margin.
- **Satisfied by:** MVP-003, MVP-005
