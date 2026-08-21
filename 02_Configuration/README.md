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
