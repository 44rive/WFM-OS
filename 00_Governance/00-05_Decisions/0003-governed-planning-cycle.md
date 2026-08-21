# ADR 0003: Governed forecast-to-requirement planning cycle

## Status

Accepted.

## Context

Forecasting and capacity planning combine refreshable actuals, analytical model
output, business judgment, calendar effects, service objectives, and approval.
If Python output flows directly into staffing facts, a recalculation can silently
change an operational requirement. If forecast logic is embedded in worksheet
formulas, each enterprise deployment will create a different calculation engine.

The application must support synchronous queues and asynchronous work without
assuming a particular forecasting or scheduling product.

## Decision

Use a four-stage planning chain:

```text
closed canonical actuals
  -> Power Query planning history
  -> Python forecast candidates
  -> controlled Excel interval forecast approval
  -> Python capacity candidates
  -> controlled Excel requirement approval
  -> Power Query canonical forecast and staffing-requirement facts
```

Candidate output is advisory. It cannot enter the semantic model until a stable
key, version, approval state, approver, approval timestamp, and source run key
are recorded in a controlled input table.

The initial forecast baseline is daily. It must be reconciled to a reviewed
intraday profile before interval forecast approval; capacity must never treat a
daily total as an interval arrival rate.

The first governed baseline is daily seasonal-naive forecasting. It requires a
unique, contiguous history for each `ActivityKey + ChannelKey` grain. Approved
calendar percentage impacts are additive and apply to the baseline first. One
approved absolute override may then replace the adjusted value at a grain/date;
the override has final precedence.

Capacity policy is selected by canonical channel behavior:

- `ERLANG_C` for synchronous demand, subject to service-level and occupancy
  constraints;
- `WORKLOAD` for asynchronous demand that must be cleared inside the planning
  interval, subject to occupancy and concurrency.

Both methods convert productive FTE to paid FTE through governed shrinkage, then
to required heads through governed FTE-per-head. Erlang C assumptions and
workload-clearance assumptions must remain visible beside every candidate.

## Stable grains

```text
Forecast policy       Profile + PolicyKey + ValidFrom
Capacity policy       Profile + PolicyKey + ValidFrom
Forecast approval     ForecastVersionKey + IntervalStart + ActivityKey + ChannelKey
Forecast fact         BusinessDate + IntervalKey + ActivityKey + ChannelKey
Forecast accuracy     ForecastVersionKey + BusinessDate + IntervalKey + ActivityKey + ChannelKey
Requirement approval  RequirementKey
Requirement fact      BusinessDate + IntervalStart + ActivityKey
```

Only one approved forecast may be active for a forecast fact grain. Only one
approved staffing requirement may be active for a requirement fact grain.
Superseded versions remain traceable but do not load as active facts.

## Boundaries

- Power Query is the only external-data path into Python in Excel.
- Python source in Git is canonical; workbook cells are installed copies.
- Python cannot approve, publish, or mutate Excel tables.
- Forecast and capacity policies are configuration.
- Calendar events and scenarios are governed planning inputs.
- Forecast and requirement approval tables are controlled decision records.
- DAX reports approved facts; it does not reimplement forecasting or Erlang C.
- The workbook remains `NOT OPERATIONAL` until Python cells, queries, facts,
  relationships, measures, and approval gates execute in desktop Excel.

## Consequences

- The same calculation contract works with any upstream source product.
- Analytical recalculation cannot silently replace an approved operational plan.
- Daily seasonal-naive is deliberately a baseline, not a claim of optimality.
- Additional methods require backtests, policy registration, and an ADR update;
  they do not replace the approval boundary.
- Forecast and capacity can evolve independently while staffing requirements
  remain the stable handoff to intraday and scheduling modules.
