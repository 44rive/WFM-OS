# ADR 0002: Schedule-led operational control spine

## Status

Accepted.

## Context

Intraday, attendance, conformance, and adherence all compare different source
events against the approved schedule. External systems use unrelated agent IDs,
state codes, activity codes, time zones, and event grains. Joining those sources
directly would make every business page vendor-specific and would permit silent
identity collisions or duration double-counting.

## Decision

Use the paid schedule as the operational comparison spine. Resolve every source
agent ID through an effective-dated identity bridge before creating facts. Split
schedules, login sessions, and agent-state events into half-open 30-minute
intervals, retain overlapped seconds, then build one canonical agent/interval
fact for operational metrics.

Keep staffing requirements as a separate interval/activity fact. This supports
both imported requirements now and forecast-derived requirements later without
changing the operational fact.

The stable grains are:

```text
Identity bridge        SystemKey + ExternalAgentID + ValidFrom
Schedule interval      ScheduleSegmentKey + IntervalStart
Login interval         LoginSessionKey + IntervalStart
Agent-state interval   AgentEventKey + IntervalStart
Operational interval  BusinessDate + IntervalStart + ActivityKey + AgentKey
Staffing requirement   BusinessDate + IntervalStart + ActivityKey
Closed snapshot        SnapshotKey + BusinessDate + IntervalStart + ActivityKey
```

Intervals are half-open: `[IntervalStart, IntervalEnd)`. Source adapters must
normalize timestamps into the deployment business time zone before interval
expansion. Overlapping identity validity, schedule segments, login sessions, or
agent-state events are blocking Data Quality results; they are never silently
deduplicated.

## Metric semantics

- Scheduled FTE is scheduled paid overlap seconds divided by interval seconds.
- Scheduled productive FTE uses productive scheduled overlap only.
- Present FTE is logged-in overlap inside paid schedule divided by interval
  seconds.
- Productive FTE is productive state overlap inside productively scheduled time
  divided by interval seconds.
- Conformance is logged-in seconds inside paid schedule divided by scheduled
  paid seconds.
- Adherence is correctly matched state seconds divided by scheduled paid
  seconds. A productive state matches productive scheduled time; otherwise the
  canonical state must match the canonical schedule type.
- Attendance is evaluated per agent/business date from login overlap inside paid
  schedule. Late and early-leave minutes compare the paid schedule envelope with
  the first login and last logout.

## Close day

Power Query prepares a bounded, reconciled snapshot candidate. A controlled VBA
action may replace exactly one provisional business date in the snapshot store
with a complete finalized set, using a stable key and an audit record. It must
refuse an unapproved date, duplicate grain, incomplete refresh, or blocking Data
Quality state. The `.xlsx` application shell does not claim that controller is
embedded.

## Consequences

- External system names and IDs stop at configuration and staging.
- One operational fact supports intraday, attendance, and adherence without
  duplicating metric definitions.
- Activity and identity mappings must be effective-dated and complete.
- Duration overlap logic is centralized and testable.
- Unscheduled work remains visible in Data Quality instead of being treated as
  planned staffing.
- Desktop Excel remains the execution authority for Power Query, Power Pivot,
  DAX, and the controlled close-day macro.
