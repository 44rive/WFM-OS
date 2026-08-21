# ADR 0004: Governed interval planning and paid-supply cycle

## Status

Accepted.

## Context

ADR 0003 established the candidate-to-approval boundary for forecast and
capacity. A whole WFM planning cycle also needs a repeatable way to convert a
daily demand outlook into interval demand, compare requirements with the paid
workforce, and create recruitment and training actions. Hard-coded source-tool
names, worksheet-only formulas, and unversioned hiring assumptions would make
that chain impossible to transplant between enterprises or audit later.

## Decision

Extend the modular Excel monolith with one explicit, vendor-neutral chain:

```text
Python daily forecast candidate
  -> effective-dated 48-interval profile
  -> complete BASE and approved scenario interval candidates
  -> controlled interval forecast approval
  -> interval capacity candidates
  -> controlled requirement approval
  -> weekly PEAK paid-FTE requirement
  -> recursive base paid-supply projection
  -> deterministic hiring and training waves
  -> separate hiring approval
  -> reconciled supply-plan approval
  -> Power Pivot supply and hiring facts
```

An intraday profile contains exactly `I00` through `I47`. Its volume weights
sum to one and its volume-weighted AHT factors sum to one. An exact weekday
profile takes precedence over `ALL`; every selected row must be approved and
effective on the forecast date. Decimal residual allocation makes the 48
interval volumes reconcile exactly to the daily total.

Each approved scenario produces a complete copy of the BASE interval horizon.
Adjustments are relative percentages for volume, AHT, and shrinkage. Approved
scopes for the same scenario, activity, and channel may not overlap.

The first governed weekly requirement statistic is `PEAK PaidFTE`. Base paid
supply is projected recursively by canonical activity from opening FTE,
transfers, leavers, and other approved movements. A hiring policy supplies
recruitment, training, and nesting lead times, expected yield, FTE per head,
maximum class seats, and a paid-FTE buffer. Hiring waves are split at the seat
limit and contribute supply only from their proficiency date.

Hiring and supply are separate approvals. For the same plan version, scenario,
activity, and period, `PlannedHirePaidFTE` must equal cumulative expected paid
FTE from approved hiring waves proficient by that period. Approve hiring waves
first; a mismatched supply row is blocking.

Multiple approved scenarios may coexist at the planning approval grains.
`BASE` alone publishes into the operational forecast and staffing-requirement
facts; alternative scenarios remain available to capacity, supply, and hiring
planning without being summed into the live operating plan.

## Stable grains

```text
Intraday profile  Profile + ProfileKey + DayType + ValidFrom + IntervalKey
Scenario input    ScenarioRowKey
Supply assumption Profile + ActivityKey + PeriodStart
Supply plan       ScenarioKey + PeriodStart + ActivityKey
Hiring wave       WaveKey
```

## Boundaries

- Source products remain adapters; no scheduling or forecasting vendor is a
  canonical concept.
- Python produces candidates and cannot approve or publish them.
- Power Query owns approval validation, reconciliation, and fact publication.
- DAX reports approved facts and does not reproduce profile, queueing, supply,
  or hiring algorithms.
- The weekly statistic is deliberately PEAK for this release. Average,
  percentile, and service-period policies require an explicit contract change.
- Planned hires are retained in projected supply after proficiency. Separate
  post-hire attrition and pipeline actuals are later extensions.
- Shift optimization, schedule publication, and leave allowance are outside
  this release and remain required to complete the full WFM lifecycle.

## Consequences

- The same planning engine can be configured for a new enterprise without
  changing source code.
- Daily-to-interval and hiring-to-supply reconciliation become testable rather
  than manual spreadsheet conventions.
- Operational commitments remain traceable to versions, policies, approvers,
  timestamps, and source runs.
- The workbook remains `NOT OPERATIONAL` until all Excel engines and approval
  paths are executed and reconciled in supported desktop Excel.
