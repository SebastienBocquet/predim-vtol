# Component data (MVP)

`motors_mvp.yaml` holds the MVP motor database (REQ-DATA-001, REQ-DATA-003).

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
- Not published: weight without cables of the MN2806 and AT2308 (weight with cables is used).
