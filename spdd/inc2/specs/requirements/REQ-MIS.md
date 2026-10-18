# Increment 2 — Mission (MIS)

### REQ-MIS-008 — Two-phase flight time (hover + cruise at target speeds)

- **Statement:** The main evaluation shall reproduce the designer's process: a hover time
  t_h at the hover battery power P_h (REQ-PROP-005, REQ-PROP-009), then cruise at each
  target speed V_k at the cruise battery power P_c(V_k), until the reserve:
  t_c,k = (E_avail − P_h·t_h) / P_c(V_k), flight time t_h + t_c,k, range V_k·t_c,k.
  E_avail = (1 − reserve)·E_nom, reserve 20 % by default, E_nom = n_s·V_nom·C the
  nominal energy (decision 2026-10-14: 80 % of the nominal energy; the usable fraction
  is not applied); E_nom and E_avail are displayed. The target speeds
  default to the minimum-power and maximum-L/D speeds of the aerodynamic power curve,
  are editable, and are written into the PredimRC Vx 1 / Vx 2 inputs. Results give,
  for each target speed, P_h, P_c, energies, flight time, range, the uncertainty
  propagated from the surrogate, and the margins.
- **Rationale:** The designer adopts the tool only if it computes the flight time the
  way he does, so that he can check it by hand.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — flight time equals the formula from the displayed powers to
  1e-9; zero hover time gives the cruise-only endurance; Example — designer's tricopter
  and quadplane template.
- **Satisfied by:** INC2-007
- **Note:** the MVP segment scenarios (REQ-MIS-002) remain an advanced mode.
