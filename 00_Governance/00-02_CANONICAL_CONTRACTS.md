# Canonical data contracts

Contract version: `1.2.0`.

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
ForecastRowKey, Profile, ForecastVersionKey, ApprovalStatus, Scenario,
Method, ActivityKey, ChannelKey, BusinessDate, IntervalStart, IntervalKey,
ForecastVolume, ForecastAHTSeconds, CreatedAt, ApprovedAt, ApprovedBy,
SourceRunKey
```

## Forecast accuracy

```text
ForecastVersionKey, BusinessDate, IntervalStart, IntervalKey, ActivityKey,
ChannelKey, ActualVolume, ForecastVolume, SignedError, AbsoluteError
```

Signed forecast error is `ForecastVolume - ActualVolume`; positive bias means
over-forecast. WAPE and signed bias are undefined when total actual volume is
zero, while absolute error, MAE, and RMSE remain defined.

## Capacity candidate

```text
RequirementKey, Profile, ForecastVersionKey, CapacityPolicyKey, IntervalStart,
ActivityKey, ChannelKey, Method, ForecastVolume, ForecastAHTSeconds, RequiredFTE,
PaidFTE, RequiredHeads, ShrinkagePct, RequirementVersion, AchievedOccupancy,
AchievedServiceLevel
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
- Duplicate approved forecast grain: quarantine the rows and block publication.
- Duplicate approved staffing-requirement grain: quarantine the rows and block
  planning publication.
- Invalid or unmatched planning adjustment: fail the analytical candidate run.
- Python candidate without a stable version and approval evidence: exclude it
  from canonical facts.
