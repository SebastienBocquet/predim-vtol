# MVP — Component data (DATA)

### REQ-DATA-001 — A small motor database is shipped

- **Statement:** The MVP shall ship about 6 motors in one YAML file: lift motors from
  the T-Motor MN range and cruise motors from the T-Motor AT range, each with Kv,
  winding resistance, no-load current, maximum current, maximum power, mass and role.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — the file loads; every entry is complete.
- **Satisfied by:** MVP-003
- **Deferred:** T-Motor Antigravity, SunnySky X, propellers, user folder, prices.

### REQ-DATA-003 — Every data entry has a provenance

- **Statement:** Every motor entry shall record its source (URL or document), its
  retrieval date and a status (`verified` or `estimated`). Values are copied from the
  source, never invented.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — an entry without source is rejected by the loader.
- **Satisfied by:** MVP-003
