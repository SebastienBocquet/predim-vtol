# MIC-REL — Motor-out hover

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Hover with one lift motor stopped |
| Model identifier | MIC-REL |
| Model description | For each lift motor stopped, whether the other lift motors can balance the weight and the pitch, roll and yaw moments within their thrust limits; remaining thrust-to-weight; single points of failure. |
| Release / date / type | 0.3.0-inc3 / 2026-10-18 / static balance (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** rank configurations by redundancy (Cost and reliability tab, discipline
  output `motor_out_tw`; `reliability.py`).

## Subject information

- **Modelled entity:** the static hover balance of a VTOL aircraft after the loss of one
  motor.

## Interface

### Inputs

| Name | Symbol | Unit | Description |
|---|---|---|---|
| motor positions | x_i, y_i | mm | lift and tilting motors (`Project.motors`) |
| spins | s_i | — | +1 CCW / −1 CW seen from above; alternating around the frame unless given (`MotorSlot.spin`) |
| propeller diameters | D_i | in | torque-to-thrust ratio ∝ D |
| maximum thrusts | T_max,i | N | maximum static thrust of the unit at the nominal voltage (MIC-PROP-UNIT) |
| weight | k_dl·m·g | N | download factor × mass × g |
| CG | x_CG, y_CG | mm | project CG, or the disc-area centroid |

### Outputs

| Name | Symbol | Unit | Description |
|---|---|---|---|
| survivable | — | — | balance found with every T_i ≤ T_max,i |
| remaining T/W | 1/z | — | z = max T_i / T_max,i of the balanced split; 0 when no balance exists |
| single points of failure | — | — | battery, 4-in-1 ESC, motors whose loss is not survivable |

## Implementation

### Modelling choices

1. Equations: Σ T_i = k_dl·m·g; Σ T_i (x_i − x_CG) = 0; Σ T_i (y_i − y_CG) = 0;
   Σ s_i·D_i·T_i = 0 (yaw torque Q = (C_Q / C_T)·D·T, the ratio cancels).
2. Yaw equation skipped when yaw is controlled by tilting a motor: tricopter (3 lift motors,
   rear motor on a yaw servo) and aircraft with tilting motors.
3. Linear programme (HiGHS): minimise z with 0 ≤ T_i ≤ z·T_max,i and the balances.

### Limitations

- Static balance only: no control margin, transient or ESC / motor dynamics; a hexacopter
  passes with reduced yaw authority in practice.
- Same C_Q / C_T for every propeller.

## Verification and validation

- **Criteria:** quadcopter X not survivable (yaw); hexacopter and octocopter survivable;
  tricopter loses pitch / roll balance with one motor stopped.
- **Report:** `tests/test_cost_reliability.py`.

## Traceability

- Requirements: REQ-COST-003
- Canvas: INC3-004
