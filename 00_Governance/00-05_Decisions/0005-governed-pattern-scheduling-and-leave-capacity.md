# ADR 0005: Governed pattern scheduling and leave capacity

## Status

Accepted.

## Context

Approved interval requirements and paid-supply plans do not by themselves show
which shift shapes cover demand or how much leave capacity remains. A portable
Excel product must solve those questions without assuming a scheduling vendor,
silently publishing analytical output as an agent roster, or allowing the same
coverage surplus to be consumed more than once.

Named-agent assignment also introduces skills, contracts, preferences,
fairness, labor law, and personal data. Combining it with first-stage coverage
design would make the baseline difficult to explain and unsafe to transplant.

## Decision

Add two governed planning stages after approved requirements and paid supply:

```text
approved interval requirements
  + effective-dated shift-pattern segments and count rules
  -> deterministic anonymous pattern-count candidate
  -> controlled schedule-plan approval
  -> Power Query recomputed interval schedule coverage
  -> deterministic interval leave-capacity candidate
  -> controlled leave-plan approval
  -> approved schedule and leave facts
```

A shift pattern is an effective-dated set of half-open segments at 30-minute
boundaries. Segment offsets are minutes from the pattern business date and may
extend into the next day. Paid and productive flags are explicit. An occurrence
is an integer count of one pattern on one business date for one activity and
scenario.

The first fitting method is `GREEDY_DEFICIT_V1`. It starts at every governed
minimum count and adds one pattern occurrence at a time. Its deterministic
selection order is:

1. greatest reduction in uncovered productive FTE-intervals;
2. least incremental overcoverage;
3. least preference-weighted paid hours;
4. earliest business date, then pattern version and pattern key.

The method stops when coverage is complete or all effective maximum counts are
exhausted. An infeasible fit remains a visible candidate with uncovered
intervals; it is never described as optimal and cannot pass schedule approval.

Power Query independently resolves the approved pattern version and segments,
recomputes paid/productive hours, expands approved occurrences to intervals,
and compares the result with approved requirements. Stored derived totals that
do not reconcile are blocking.

Leave v0.5 is capacity planning, not individual request adjudication. For each
approved schedule interval, an effective leave policy calculates the maximum
staff-hours that may be removed while preserving the required coverage floor,
reserve FTE, percentage cap, and allowance increment. The controlled leave plan
may approve any value from zero through that calculated maximum. Its stable
interval grain prevents two plan rows from consuming the same surplus.

## Stable grains

```text
Shift rule          Profile + RuleKey
Shift segment       Profile + PatternVersionKey + PatternKey + DayType + SegmentKey
Schedule plan       ScenarioKey + BusinessDate + ActivityKey + PatternVersionKey + PatternKey
Schedule coverage   SchedulePlanVersionKey + ScenarioKey + IntervalStart + ActivityKey
Leave policy        Profile + PolicyKey + ValidFrom
Leave plan          ScenarioKey + IntervalStart + ActivityKey
```

## Boundaries

- Schedule candidates contain anonymous pattern counts, never employee names.
- An approved schedule plan is a planning fact. It does not become a canonical
  agent `ScheduleSegment` and cannot drive adherence until a later named-agent
  assignment/publication stage is approved.
- Python fits and recommends; it cannot approve or mutate controlled tables.
- Power Query recomputes approved schedule coverage and leave limits from
  governed source rows rather than trusting pasted derived totals.
- DAX reports approved planning facts and does not repeat fitting or allowance
  algorithms.
- Alternative scenarios remain planning alternatives and do not silently
  replace the operational `BASE` requirement or imported agent schedule.
- Segment offsets use the deployment's normalized local planning calendar.
  Exceptional daylight-saving days require a later calendar-aware extension.
- Individual leave requests, entitlement balances, labor-law adjudication,
  skills-based agent assignment, fairness optimization, swaps, and roster
  publication remain outside v0.5.

## Consequences

- Enterprises configure patterns and policies instead of modifying code.
- Coverage, overcoverage, infeasibility, and leave headroom are visible at the
  same 30-minute grain as the approved requirement.
- Pattern fitting remains deterministic and testable without external solver
  dependencies, while its heuristic limitation stays explicit.
- The workbook still remains `NOT OPERATIONAL` until the installed Excel engines
  execute and reconcile in the supported desktop environment.
