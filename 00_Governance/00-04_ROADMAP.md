# Roadmap

## Milestone 1 — foundation

- Create `WFM_OS.xlsm` shell and configuration tables.
- Implement generic folder, field-mapping, value-mapping, and assertion functions.
- Build contact staging, dimensions, live/closed facts, and refresh audit.
- Reconcile offered, handled, service level, abandon rate, and AHT.

Exit gate: the same anonymized source produces identical reconciled metrics on
repeat refreshes, with no unmapped values hidden.

## Milestone 2 — operational control

- Add schedules, login sessions, agent states, and people identities.
- Deliver intraday, attendance, conformance, adherence, and action logging.
- Implement close-day and append-only decision snapshots.

Source status: implemented in v0.2 with anonymized acceptance fixtures. Desktop
Excel engine installation, execution, and visual validation remain the release
gate before this milestone can be called operational.

## Milestone 3 — planning cycle

- Add forecast versions, calendar events, backtesting, and Python models.
- Add interval capacity, shrinkage, hiring, training waves, and scenarios.
- Add shift coverage, schedule proposals, and leave allowance planning.

Source status: the governed forecast/capacity foundation is implemented in
v0.3. It includes versioned approval tables, forecast accuracy, a deterministic
daily seasonal-naive baseline, governed event/override precedence, and Erlang C
or workload capacity candidates. Desktop Excel execution and interval-profile
reconciliation remain release gates. Hiring, training waves, schedule
generation, and leave allowance are not yet implemented.

## Milestone 4 — performance and publication

- Add agent/team performance and executive pages.
- Add optional restricted incentive calculation and frozen payout runs.
- Add controlled exports and sanitized leadership packs.

## Milestone 5 — portability

- Package a blank `.xltm` distribution template.
- Validate a second enterprise profile without changing canonical code.
- Publish deployment and upgrade runbooks.
