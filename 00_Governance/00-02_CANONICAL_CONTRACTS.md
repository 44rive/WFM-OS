# Canonical data contracts

Contract version: `1.3.0`.

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
RequirementKey, Profile, ForecastVersionKey, CapacityPolicyKey, ScenarioKey,
IntervalStart, ActivityKey, ChannelKey, Method, ForecastVolume, ForecastAHTSeconds, RequiredFTE,
PaidFTE, RequiredHeads, ShrinkagePct, RequirementVersion, AchievedOccupancy,
AchievedServiceLevel
```

## Intraday profile

```text
Profile, ProfileKey, DayType, IntervalKey, VolumeWeight, AHTFactor,
ValidFrom, ValidTo, Approved
```

The stable grain is `Profile + ProfileKey + DayType + ValidFrom + IntervalKey`.
An active profile has exactly 48 unique 30-minute intervals, volume weights
that sum to one, and volume-weighted AHT factors that sum to one.

## Scenario input

```text
ScenarioRowKey, Profile, ScenarioKey, ScenarioName, ActivityKey, ChannelKey,
StartDate, EndDate, VolumeChangePct, AHTChangePct, ShrinkageChangePct,
ApprovalStatus, ApprovedAt, ApprovedBy, SourceRunKey
```

## Weekly supply assumption

```text
SupplyRowKey, Profile, ActivityKey, PeriodStart, OpeningPaidFTE,
TransfersInFTE, TransfersOutFTE, LeaversFTE, OtherChangeFTE, ApprovalStatus,
ApprovedAt, ApprovedBy, SourceRunKey
```

## Supply plan

```text
PlanRowKey, Profile, PlanVersionKey, ScenarioKey, PolicyKey, ApprovalStatus,
PeriodStart, ActivityKey, RequiredPaidFTE, BufferPaidFTE, BaselinePaidFTE,
PlannedHirePaidFTE, ProjectedPaidFTE, ResidualGapPaidFTE, ApprovedAt,
ApprovedBy, SourceRunKey
```

## Hiring wave

```text
WaveKey, Profile, PlanVersionKey, ScenarioKey, PolicyKey, ApprovalStatus,
ActivityKey, RecruitmentStart, TrainingStart, NestingStart, ProficiencyDate, PlannedHeads,
ExpectedPaidFTE, TimingStatus, ApprovedAt, ApprovedBy, SourceRunKey
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
- Duplicate approved forecast grain within one scenario: quarantine the rows
  and block publication. Only `BASE` publishes to the operational forecast fact.
- Duplicate approved staffing-requirement grain within one scenario: quarantine
  the rows and block planning publication. Only `BASE` publishes to operational
  staffing facts.
- Intraday profile missing an interval, containing a duplicate interval, or
  failing volume/AHT reconciliation: fail the candidate run.
- Duplicate or overlapping approved scenario scope: fail the candidate run.
- Weekly supply period not Monday, noncontiguous supply assumptions, or negative
  projected base supply: block supply publication.
- Missing or overlapping effective hiring policy: fail the hiring run.
- Duplicate approved hiring wave or supply grain: block publication.
- Supply planned-hire FTE not equal to cumulative approved proficient hiring
  FTE for the same version/scenario/activity: block publication.
- Invalid or unmatched planning adjustment: fail the analytical candidate run.
- Python candidate without a stable version and approval evidence: exclude it
  from canonical facts.
