# Canonical data contracts

These are logical contracts. Physical types and required/optional status will be
implemented and tested in Power Query.

## Contact

```text
ContactKey, SourceSystem, SourceContactID, ContactStart, ContactEnd,
ChannelKey, QueueKey, ActivityKey, AgentKey, Direction, Outcome,
WaitSeconds, TalkSeconds, HoldSeconds, AfterContactSeconds
```

## Work item

```text
WorkItemKey, SourceSystem, SourceWorkItemID, CreatedAt, CompletedAt,
ChannelKey, WorkTypeKey, ActivityKey, AgentKey, Status, HandlingSeconds,
SlaDeadline
```

## Agent event

```text
AgentEventKey, SourceSystem, AgentKey, EventStart, EventEnd,
StateKey, DurationSeconds
```

## Login session

```text
LoginSessionKey, SourceSystem, AgentKey, LoginAt, LogoutAt
```

## Schedule segment

```text
ScheduleSegmentKey, SourceSystem, AgentKey, ScheduledStart, ScheduledEnd,
ActivityKey, ScheduleTypeKey, PaidFlag, ProductiveFlag
```

## Person and identity

```text
AgentKey, EmployeeBusinessID, OperationalID, SourceSystem, DisplayName,
ActivityKey, TeamKey, ManagerKey, SiteKey, ContractHours, ValidFrom,
ValidTo, EmploymentStatus
```

## Forecast

```text
ForecastVersionKey, ApprovedFlag, Scenario, ActivityKey, ChannelKey,
IntervalStart, ForecastVolume, ForecastAHT, CreatedAt, ApprovedAt
```

## Minimum validation behavior

- Required columns missing: fail the affected adapter.
- Invalid types: quarantine the row with its source and reason.
- Unknown agent or queue: quarantine and expose visibly.
- Duplicate canonical key: fail the affected fact build.
- Live/closed date overlap: fail model approval.
- Source-to-fact volume mismatch: fail reconciliation.
