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

The v0.6 named-roster layer is configured through `skills.csv`,
`activity_eligibility.csv`, `activity_skill_requirements.csv`,
`agent_skills.csv`, `agent_contracts.csv`, `agent_availability.csv`,
`agent_preferences.csv`, `roster_policies.csv`, `leave_type_policies.csv`, and
`schedule_authority.csv`. Repository rows are disabled templates. These files
must never contain real names, protected attributes, diagnoses, or production
requests. A published roster becomes an operational schedule source only when
one non-overlapping authority row identifies its exact roster and publication
versions.
