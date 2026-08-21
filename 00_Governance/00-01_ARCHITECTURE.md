# Architecture

## Decision

WFM OS is a modular Excel monolith: one application workbook with one semantic
model and two refresh lanes. Raw data is external; application behavior is
configuration-driven.

## Layers

### 1. Source adapters

Adapters understand external filenames, formats, column names, locales, and
source-specific status values. They produce canonical tables and contain the
only vendor-specific logic.

### 2. Canonical data

The stable domains are:

- people and operational identities;
- activities, skills, queues, sites, teams, and channels;
- contacts and deferred work items;
- agent-state events and login sessions;
- schedule segments, leave, absence, and adherence;
- forecast versions and staffing requirements;
- quality, productivity, attendance, and incentive results.

### 3. Semantic model

Power Pivot stores dimensions and facts. Dimensions sit on the lookup side of
one-to-many relationships and must have unique keys. Operational source IDs are
mapped to dated internal keys before facts enter the model.

Closed and live facts are separate physical tables for refresh performance but
share dimensions, transformation functions, and DAX measures:

```text
Closed facts: BusinessDate < AsOfDate   refresh daily
Live facts:   BusinessDate = AsOfDate   refresh frequently
```

No date can exist in both lanes.

### 4. WFM modules

The model serves demand planning, forecasting, capacity, scheduling, leave,
intraday, attendance, adherence, performance, and governance pages.

Operational control uses the schedule-led interval spine defined in ADR 0002.
External agent identities are resolved through a dated bridge before facts are
built. Schedule, login, and agent-state durations are intersected at half-open
30-minute windows; overlap defects remain blocking quality results.

### 5. Analytical labs

Python in Excel consumes named Power Query results for forecast backtesting,
statistical models, scenarios, schedule experiments, and anomaly analysis.
Approved outputs are versioned before they affect operational decisions.

The planning cycle follows ADRs 0003 and 0004. Power Query supplies closed
actuals; Python creates forecast, interval scenario, capacity, supply, and
hiring candidates; controlled approval tables publish immutable versions into
canonical forecast, staffing, supply, and hiring facts. Python output never
enters an operational fact merely because a cell recalculated.

Daily demand is reconciled through approved, effective-dated 48-interval
profiles before capacity. Approved weekly requirements are compared with a
recursive paid-supply projection. Hiring waves and the resulting supply plan
have separate approvals and a blocking paid-FTE reconciliation.

Pattern scheduling and leave capacity follow ADR 0005. Python fits anonymous
pattern counts to approved interval requirements. Schedule approval remains
separate from named-agent schedules; Power Query recomputes approved interval
coverage from effective pattern segments. Leave planning then allocates an
interval allowance against that approved coverage without creating employee
leave decisions.

Named assignment and publication follow ADR 0006. Python expands the approved
`BASE` pattern plan into stable occurrences and recommends eligible pseudonymous
agents under configured skills, contracts, availability, preference, and
fairness assertions. Roster approval, leave-request decisions, bilateral swap
decisions, and publication are separate immutable controls. Published roster
segments never overwrite imported schedule facts or imply legal certification.
One non-overlapping authority row selects either imported schedule intervals or
an exact roster/publication version for operational staffing and adherence;
the two sources are never combined.

## Workbook sheet groups

```text
00-09  home, setup, configuration, quality, and audit
10-19  strategic and demand planning
20-29  forecast, capacity, hiring, scheduling, and leave
30-39  intraday, attendance, adherence, and actions
40-49  performance and executive reporting
90-94  Python initialization and analytical labs
95-99  controlled input, technical output, pivots, and tests
```

## Load policy

| Query prefix | Destination |
|---|---|
| `p_` | connection only |
| `fx_` | connection only |
| `src_` | connection only |
| `stg_` | connection only |
| `dim_` | Data Model only |
| `fact_` | Data Model only |
| `out_` | bounded worksheet table |
| `dq_` | bounded Data Quality table |

Close-day snapshots are append-only controlled records. Power Query may prepare
snapshot candidates but must not overwrite user decisions or pretend a refresh
is an immutable close.

## Portability

A deployment creates an enterprise profile and maps external fields and values
to the canonical contracts. Standard deployment must not require edits to M,
DAX, Python, or VBA.
