# Cost and reliability (COST)

### REQ-COST-001 — The purchase cost is computed with its sources

- **Statement:** The system shall give the purchase cost of the aircraft: motors,
  propellers, ESCs (by current rating, 4-in-1 or separate), battery (price per Wh by
  chemistry), cables (price per metre per AWG, lengths from the power chain), frame
  (entered) and avionics (entered). Prices are copied from manufacturer or retailer pages
  with URL, date and currency; every price can be overridden in the project.
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Test — the total is the sum of the items; an override replaces the
  database price.
- **Satisfied by:** INC3-004

### REQ-COST-002 — The cost of use is given per flight hour and per flight

- **Statement:** The system shall give the wear cost: battery price / cycle life
  (defaults LiPo 300, Li-ion 500 cycles, editable) per flight; motors price × flight time
  / motor life (default 1000 h); propellers price / flights between replacements; per
  flight (two-phase flight time at V₁) and per flight hour.
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Test — formula on a hand case.
- **Satisfied by:** INC3-004

### REQ-COST-003 — Hover survives the loss of one motor, or the weak motors are shown

- **Statement:** For each lift (or tilting) motor removed, the system shall solve the
  hover balance of vertical force, pitch, roll and yaw moments (yaw from the spin
  direction and torque of each motor) with the remaining motors within their thrust
  limits, and report whether hover is survivable, the remaining thrust-to-weight and the
  single points of failure (4-in-1 ESC, single battery). A tricopter whose rear motor
  tilts for yaw balances yaw by the tilt.
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Test — quadcopter X not survivable (yaw), hexacopter survivable;
  tricopter rule.
- **Satisfied by:** INC3-004
