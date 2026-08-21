# ADR 0006: Governed named roster and controlled publication

## Status

Accepted.

## Context

ADR 0005 deliberately stops at anonymous pattern counts. Turning that planning
result into a roster introduces employee identity, skills, contracts,
availability, preferences, fairness, leave requests, swaps, and publication.
Those concerns are sensitive, enterprise-specific, and frequently regulated.
They cannot safely be inferred from a scheduling product, hidden in a solver,
or represented as proof of legal compliance.

The workbook must remain transplantable between enterprises. It therefore
needs stable canonical inputs and configurable assertions while retaining a
human approval boundary between analytical candidates and published schedules.

## Decision

Add an immutable named-roster layer after the approved anonymous schedule:

```text
approved anonymous schedule plan
  + effective people, activity eligibility, skills, contracts, availability,
    preferences, and roster policy
  -> deterministic named-assignment candidate
  -> controlled roster-version approval
  -> Power Query independently reconstructs occurrences and segments
  -> approved immutable roster
      + bilateral swap requests and recorded consent
      -> swap eligibility recommendation -> controlled swap decision
      -> effective post-swap roster
      + leave requests and external entitlement snapshots
      -> full-request recommendation -> controlled leave decision
  -> separate publication approval
  -> immutable published 30-minute roster segments
  -> exactly one imported-or-published schedule authority
```

The assignment method is `CONSTRAINED_GREEDY_REPAIR_V1`. It is deterministic,
bounded, explainable, and not globally optimal. It expands every approved
pattern count into stable unit occurrences, assigns locked occurrences first,
then orders remaining occurrences by scarcity, earliest paid start, longest
span, and stable keys. Feasible agents are ranked by target-load ratio,
unfavorable burden, preference cost, assignment count, and `AgentKey`.

Hard eligibility includes active employment, explicit activity eligibility,
AND-of-OR skill groups, a single effective approved contract and policy,
complete dated availability, no occupied-span overlap, minimum rest, daily and
weekly paid-hour maxima, shift-hour/span maxima, assignment-per-workday maxima,
and consecutive-workday maxima. If configured, one deterministic displacement
may repair a simple greedy dead end. Any unresolved occurrence remains visibly
`UNASSIGNED`; the engine never forces an assignment.

The engine attributes occurrence identity and consecutive workdays to the
pattern business date. Paid time is charged to the actual calendar and weekly
period it occupies. The complete first-paid through last-paid span is occupied;
assigning another occurrence inside an unpaid split-shift gap is outside v0.6.

Leave evaluation is full-request only. Requests are ordered by configured
non-sensitive priority, submission time, and stable key. Recommendations
intersect the employee's approved productive roster with approved interval
leave capacity and an optional external entitlement snapshot. Protected or
locally regulated categories use `ALWAYS_REVIEW`; the engine must not recommend
rejection solely because capacity is unavailable.

Swap evaluation supports bilateral exchanges of whole roster occurrences. Both
consents are required. The exchanged roster must still satisfy activity,
skills, availability, overlap, rest, hours, and consecutive-workday assertions.
Conflicting requests touching the same assignment are blocking. Approved swaps
create an amended publication view; they never mutate the approved roster.

Python validates employee eligibility, skills, availability, overlap, rest,
hours, capacity consumption, and request/swap conflicts before those candidates
can be approved. Power Query independently validates structural contracts,
version lineage, approval evidence, occurrence uniqueness and completeness,
then reconstructs published interval segments. Publication requires a separate
approved control row and exactly one non-overlapping schedule-authority row;
imported and published schedule intervals are never appended together.

## Stable grains

```text
Activity eligibility  Profile + EligibilityKey
Agent skill           Profile + AgentSkillKey
Skill requirement     Profile + RequirementKey
Agent contract        Profile + ContractKey
Availability window   Profile + AvailabilityWindowKey
Agent preference      Profile + PreferenceKey
Roster occurrence     SchedulePlanVersionKey + OccurrenceKey
Roster assignment     RosterVersionKey + OccurrenceKey
Roster segment        RosterVersionKey + OccurrenceKey + SegmentKey
Leave request         Profile + LeaveRequestKey
Leave decision        LeaveDecisionVersionKey + LeaveRequestKey
Leave consumption     LeaveDecisionVersionKey + LeaveRequestKey + IntervalStart + ActivityKey
Swap request          Profile + SwapRequestKey
Swap decision         SwapDecisionVersionKey + SwapRequestKey
Publication control   Profile + PublicationKey
Published roster      PublicationVersionKey + OccurrenceKey + SegmentKey + IntervalStart
```

`OccurrenceKey` is the schedule version, scenario, business date, activity,
pattern version, pattern key, and zero-padded occurrence ordinal. Changing an
approved pattern count requires a new schedule version; published versions are
never updated in place.

## Privacy, policy, and legal boundary

- Only pseudonymous `AgentKey` enters facts and analytical output. Display names
  remain in the governed people dimension.
- Availability, contracts, requests, entitlement snapshots, and preferences
  require restricted workbook and SharePoint access. Hidden sheets and workbook
  protection are not security controls.
- Do not ingest diagnoses, protected characteristics, inferred health data, or
  other sensitive explanations into the analytical engine.
- Configured constraints are employer assertions, not legal certification.
  Each deployment requires local HR, legal, labor-relations, and works-council
  validation where applicable.
- Missing configuration is blocking; it is never evidence of compliance.
- Daylight-saving exception dates require explicit review because v0.6 retains
  normalized timezone-naive planning intervals.

## Boundaries

- Python recommends and explains; it cannot approve, publish, or mutate tables.
- Power Query validates and publishes approved versions; DAX only reports them.
- `BASE` is the only scenario eligible for named operational publication.
- Entitlement remains an external snapshot. The workbook does not become the
  leave-balance system of record.
- v0.6 excludes payroll, overtime valuation, medical/protected-leave
  adjudication, multi-party swaps, open-shift bidding, giveaways, split-shift
  gap reuse, solver-optimality claims, and DST legal calculations.

## Consequences

- A deployment can map its people and policies without changing the assignment
  engine.
- Fairness becomes measurable and auditable rather than an undocumented solver
  side effect.
- Prior approved rosters remain immutable while leave, swaps, and publication
  create traceable decision layers.
- Named roster data materially raises the access-control requirements of the
  deployment even though the repository artifact remains data-free.
- The workbook remains `NOT OPERATIONAL` until all installed Excel engines and
  publication controls execute and reconcile in the supported desktop release.
