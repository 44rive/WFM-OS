# Canonical data contracts

Contract version: `1.1.0`.

These are logical contracts. Physical types and required/optional status will be
implemented and tested in Power Query.

## Contact

```text
ContactKey, SystemKey, SourceContactID, ContactStart, ContactEnd,
ChannelKey, QueueKey, ActivityKey, AgentKey, Direction, Outcome,
WaitSeconds, TalkSeconds, HoldSeconds, AfterContactSeconds
```

## Work item

```text
WorkItemKey, SystemKey, SourceWorkItemID, CreatedAt, CompletedAt,
ChannelKey, WorkTypeKey, ActivityKey, AgentKey, Status, HandlingSeconds,
SlaDeadline
```

## Agent event

```text
AgentEventKey, SystemKey, AgentKey, EventStart, EventEnd,
StateKey, DurationSeconds
```

## Login session

```text
LoginSessionKey, SystemKey, AgentKey, LoginAt, LogoutAt
```

## Schedule segment

```text
ScheduleSegmentKey, SystemKey, AgentKey, ScheduledStart, ScheduledEnd,
ActivityKey, ScheduleTypeKey, PaidFlag, ProductiveFlag
```

## Person

```text
AgentKey, EmployeeBusinessID, DisplayName, ActivityKey, TeamKey, ManagerKey,
SiteKey, ContractHours, ValidFrom, ValidTo, EmploymentStatus
```

## Operational identity bridge

```text
IdentityKey, SystemKey, ExternalAgentID, AgentKey, ValidFrom, ValidTo
```

## Forecast

```text
ForecastVersionKey, ApprovedFlag, Scenario, ActivityKey, ChannelKey,
IntervalStart, ForecastVolume, ForecastAHT, CreatedAt, ApprovedAt
```

## Agent operational interval

```text
BusinessDate, IntervalStart, IntervalKey, ActivityKey, AgentKey,
ScheduledSeconds, ScheduledProductiveSeconds, LoggedScheduledSeconds,
ProductiveActualSeconds, AdherentSeconds, ExceptionSeconds
```

## Staffing requirement

```text
RequirementKey, BusinessDate, IntervalStart, IntervalKey, ActivityKey,
RequiredFTE, RequirementVersion, ApprovedFlag
```

## Operational snapshot

```text
SnapshotKey, Profile, BusinessDate, IntervalStart, ActivityKey,
ScheduledFTE, ScheduledProductiveFTE, PresentFTE, ProductiveFTE, RequiredFTE,
NetProductiveFTE, Status, ClosedAt, ClosedBy, SourceRunKey
```

## Minimum validation behavior

- Required columns missing: fail the affected adapter.
- Invalid types: quarantine the row with its source and reason.
- Unknown agent or queue: quarantine and expose visibly.
- Duplicate canonical key: fail the affected fact build.
- Live/closed date overlap: fail model approval.
- Source-to-fact volume mismatch: fail reconciliation.
- Overlapping dated identities: quarantine affected facts and block approval.
- Invalid or nonpositive time ranges: quarantine the source row.
- Overlapping schedule, login, or state events for one agent: expose and block
  operational approval.
- Snapshot duplicate grain or unapproved close request: refuse the close.
