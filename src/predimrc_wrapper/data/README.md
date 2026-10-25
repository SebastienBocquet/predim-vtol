# Component data (MVP)

`motors_mvp.yaml` holds the MVP motor database (REQ-DATA-001, REQ-DATA-003). User motors,
same fields, go in `<user data>/motors.yaml` (`$PREDIMRC_USER_DATA`, else
`~/.predimrc_wrapper/data`), merged with the shipped ones (a user id overrides a shipped one);
the GUI form "Add a custom motor to the database" writes there. A user motor may leave out
`manufacturer`, `range`, `source` (default `user entry`), `retrieved` and `status` (default
`estimated`): no computation uses them.

| Field | Unit | Meaning |
|---|---|---|
| `kv` | rpm/V | speed constant |
| `rm_mohm` | mΩ | phase-to-phase winding resistance |
| `i0_a` | A | no-load current, measured at `i0_test_voltage_v` |
| `i_max_a` | A | maximum current published by the source (180 s rating) |
| `p_max_w` | W | maximum power (180 s) |
| `mass_g` | g | mass including cables when published |
| `source`, `retrieved`, `status` | — | provenance; `verified` = copied from the source |

Values are copied from the cited pages, never invented. Scope: motors of 150 W to 250 W
maximum power (180 s). Coverage on 2026-10-12:

- Lift: T-Motor MN2212 V2.0 KV780 (200 W) and KV920 (220 W), MN2806 KV400 (216 W) and
  KV650 (187 W) (LIGPOWER pages).
- Cruise: T-Motor AT2308 KV1450 (250 W).
- Added on 2026-10-25, outside the 150–250 W scope: T-Motor MT2216 KV1100 (380 W, data sheet
  and test table supplied by the user) and KV900 (`estimated`: read in reseller search
  results, to check against the T-Motor data sheet), with the T-Motor CF propellers of their
  tests (8x2.7 to 12x4).
- The unit type form pre-fills `motor_mass_g` with the database mass; the value entered
  there (e.g. a weighed motor) replaces the database mass in the mass budget.
- Not published: weight without cables of the MN2806 and AT2308 (weight with cables is used).

## User data

`<user data>` is `$PREDIMRC_USER_DATA`, else `~/.predimrc_wrapper/data`. Its files are merged
with the shipped ones (a user id overrides a shipped one):

| File | Content | GUI form |
|---|---|---|
| `motors.yaml` | motors | Configuration tab, "Add a custom motor to the database" |
| `propellers.yaml` | propellers | Hover tab, "Add a propeller to the database" |
| `thrust_tests/<id>.yaml` | thrust–power tests, one per file | Hover tab, "Add a thrust–power test" |

Provenance fields (manufacturer, name, bench, source, retrieved, status) are optional in the
user files: no computation uses them. The thrust–power surrogate is fitted on the shipped and
user tests together.
