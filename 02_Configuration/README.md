# 02 · Configuration

Anonymized schemas mirror the controlled configuration tables that will live in
`WFM_OS.xlsm`. Enterprise deployments change these values rather than rewriting
canonical source code.

Never store real employee identities, credentials, salaries, or production
system details in the repository copies.

`people.csv` defines the canonical workforce dimension. `identity_mapping.csv`
is a separate dated bridge because the same external ID can exist in multiple
tools or be recycled over time. `state_mapping.csv` governs presence,
productivity, and adherence behavior without embedding external state names in
facts or measures.

`forecast_policies.csv`, `intraday_profiles.csv`, `capacity_policies.csv`,
`hiring_policies.csv`, `shift_patterns.csv`, `shift_rules.csv`,
`leave_policies.csv`, and `calendar_events.csv` govern the planning slice.
Forecast, interval-shape, capacity, and hiring behavior is selected by
effective-dated policy; calendar impacts are approved inputs. The repository
rows are fabricated and disabled. Approved forecast, requirement, hiring, and
supply versions are operational decisions and therefore are not stored in
these configuration files. Schedule and leave approvals also remain controlled
workbook decisions, not configuration rows.
