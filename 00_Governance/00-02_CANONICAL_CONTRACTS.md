# Canonical data contracts

Contract version: `1.5.0`.

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

## Shift rule

```text
Profile, RuleKey, ActivityKey, RuleType, PatternKey, Value, Unit,
ValidFrom, ValidTo, Approved, Owner, Notes
```

Implemented rule types are `MIN_PATTERN_COUNT`, `MAX_PATTERN_COUNT`, and
`PREFERENCE_COST`. Each approved pattern occurrence date requires exactly one
effective rule of each type.

## Shift-pattern segment

```text
Profile, PatternVersionKey, PatternKey, PatternName, ActivityKey, DayType,
SegmentKey, StartMinute, EndMinute, ScheduleTypeKey, PaidFlag,
ProductiveFlag, ValidFrom, ValidTo, Approved
```

Offsets are minutes from the pattern business date, use half-open bounds, align
to 30-minute intervals, and may range from 0 through 2880. Segments inside one
selected pattern must not overlap.

## Schedule plan

```text
SchedulePlanRowKey, Profile, SchedulePlanVersionKey, ScenarioKey,
ApprovalStatus, BusinessDate, ActivityKey, PatternVersionKey, PatternKey,
PatternCount, PaidHours, ProductiveHours, CoverageMethod, ApprovedAt,
ApprovedBy, SourceRunKey, Notes
```

## Schedule coverage

```text
SchedulePlanVersionKey, ScenarioKey, BusinessDate, IntervalStart, IntervalKey,
ActivityKey, RequiredFTE, ScheduledPaidFTE, ScheduledProductiveFTE, GapFTE,
OverFTE, CoverageStatus
```

## Leave policy

```text
Profile, PolicyKey, ActivityKey, CoverageFloorPct, ReserveFTE,
MaxLeavePctOfScheduled, AllowanceIncrementHours, ValidFrom, ValidTo, Approved
```

## Leave plan

```text
LeavePlanRowKey, Profile, LeavePlanVersionKey, SchedulePlanVersionKey,
ScenarioKey, PolicyKey, ApprovalStatus, IntervalStart, ActivityKey,
RequiredFTE, ScheduledProductiveFTE, CalculatedAllowanceHours,
ApprovedAllowanceHours, RemainingCoverageFTE, ApprovedAt, ApprovedBy,
SourceRunKey, Notes
```

## Skill

```text
Profile, SkillKey, SkillName, ValidFrom, ValidTo, Enabled
```

## Activity eligibility

```text
Profile, EligibilityKey, AgentKey, ActivityKey, ValidFrom, ValidTo, Approved
```

## Activity skill requirement

```text
Profile, RequirementKey, ActivityKey, PatternKey, SkillGroupKey, SkillKey,
MinimumLevel, ValidFrom, ValidTo, Approved
```

Every effective `SkillGroupKey` is required. Any qualifying skill inside one
group satisfies that group. An exact `PatternKey` definition takes precedence
over `ALL`.

## Agent skill

```text
Profile, AgentSkillKey, AgentKey, SkillKey, ProficiencyLevel,
ValidFrom, ValidTo, Approved
```

## Agent contract

```text
Profile, ContractKey, AgentKey, RosterPolicyKey, PeriodType, PeriodStartDay,
MinPaidHours, TargetPaidHours, MaxPaidHours, MaxPaidHoursPerDay,
MaxPaidHoursPerShift, MaxShiftSpanHours, MinRestHours,
MaxConsecutiveWorkdays, MaxAssignmentsPerWorkday, ValidFrom, ValidTo, Approved
```

v0.6 implements `PeriodType = WEEK`. Contract values are enterprise-approved
assertions and are not proof of statutory or collective-agreement compliance.

## Agent availability window

```text
Profile, AvailabilityWindowKey, AgentKey, WindowStart, WindowEnd,
AvailabilityType, SourceRole, Approved
```

Supported types are `AVAILABLE` and `UNAVAILABLE`; an unavailable intersection
overrides availability. Every paid interval of an assignment must be contained
inside dated availability.

## Agent preference

```text
Profile, PreferenceKey, AgentKey, PatternKey, DayType, PreferenceCost,
UnfavorableWeight, ValidFrom, ValidTo, Approved
```

Preferences are nonnegative soft costs. They cannot make an otherwise eligible
agent ineligible.

## Roster policy

```text
Profile, RosterPolicyKey, ActivityKey, AssignmentMethod, AvailabilityMode,
FairnessMethod, WorkdayAttributionMode, MinimumHoursMode, RepairDepth,
MaxCandidatePairs, ValidFrom, ValidTo, Approved
```

## Roster plan

```text
RosterPlanRowKey, AssignmentKey, Profile, RosterVersionKey, SchedulePlanVersionKey,
ScenarioKey, ApprovalStatus, OccurrenceKey, BusinessDate, ActivityKey,
PatternVersionKey, PatternKey, OccurrenceOrdinal, AgentKey, ContractKey,
PaidHours, ProductiveHours, AssignmentMethod, AssignmentStatus,
FairnessScore, PreferenceCost, ApprovedAt, ApprovedBy, SourceRunKey, Notes
```

`AssignmentKey` identifies the occurrence assignment and remains unchanged when
an approved swap changes its agent. It must not embed the agent identity.

## Leave type policy

```text
Profile, LeaveTypeKey, CapacityDecisionMode, EntitlementCheckMode,
PartialApprovalMode, PaidFlag, ValidFrom, ValidTo, Approved
```

## Leave request

```text
LeaveRequestKey, Profile, AgentKey, LeaveTypeKey, RequestedStart,
RequestedEnd, SubmittedAt, PriorityRank, RequestStatus, ExternalReference, Notes
```

## Leave entitlement snapshot

```text
EntitlementSnapshotKey, Profile, AgentKey, LeaveTypeKey, AsOfDate,
AvailableHours, SourceSystemKey, Approved
```

The snapshot is external evidence. WFM OS does not maintain entitlement
balances.

## Leave request decision

```text
LeaveDecisionRowKey, Profile, LeaveDecisionVersionKey, RosterVersionKey,
SwapDecisionVersionKey, LeavePlanVersionKey, LeaveRequestKey, ApprovalStatus, AgentKey, LeaveTypeKey,
RequestedStart, RequestedEnd, RequestedHours, ApprovedHours,
RecommendationStatus, DecisionReason, ApprovedAt, ApprovedBy, SourceRunKey,
Notes
```

## Swap request

```text
SwapRequestKey, Profile, RosterVersionKey, AssignmentKeyA, AgentKeyA,
AssignmentKeyB, AgentKeyB, ConsentAAt, ConsentBAt, SubmittedAt,
RequestStatus, Notes
```

## Swap decision

```text
SwapDecisionRowKey, Profile, SwapDecisionVersionKey, RosterVersionKey,
SwapRequestKey, ApprovalStatus, AssignmentKeyA, AgentKeyA, AssignmentKeyB,
AgentKeyB, RecommendationStatus, DecisionReason, ApprovedAt, ApprovedBy,
SourceRunKey, Notes
```

## Roster publication

```text
PublicationKey, Profile, PublicationVersionKey, RosterVersionKey,
LeaveDecisionVersionKey, SwapDecisionVersionKey, ScenarioKey, StartDate,
EndDate, ApprovalStatus, ApprovedAt, ApprovedBy, PublishedAt, PublishedBy,
SourceRunKey, Notes
```

## Published roster segment

```text
PublicationVersionKey, RosterVersionKey, OccurrenceKey, SegmentKey,
BusinessDate, IntervalStart, IntervalKey, AgentKey, ActivityKey,
ScheduleTypeKey, PaidFlag, ProductiveFlag, ScheduledSeconds, PublicationStatus
```

## Schedule authority

```text
Profile, AuthorityKey, ActivityKey, ValidFrom, ValidTo, ScheduleAuthority,
RosterVersionKey, PublicationVersionKey, Approved, Owner, Notes
```

`ScheduleAuthority` is either `IMPORTED_SCHEDULE` or `PUBLISHED_ROSTER`.
Published authority requires both version keys. Approved effective ranges may
not overlap for one activity. This prevents imported and WFM OS-published
schedules from being combined in adherence or staffing facts.

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
- Missing, overlapping, misaligned, or inconsistent shift-pattern segments:
  fail the candidate run and block schedule publication.
- Missing or overlapping effective shift count rule: fail the candidate run.
- Noninteger or out-of-bounds approved pattern count, altered derived hours,
  mixed approved schedule versions, or uncovered approved requirement: block
  schedule publication.
- Leave policy outside its numeric bounds, duplicate approved leave interval,
  allowance above the independently calculated maximum, invalid increment, or
  negative remaining coverage: block leave publication.
- Missing or overlapping effective roster policy, contract, activity
  eligibility, skill, or availability: fail named assignment and block roster
  approval.
- Duplicate, missing, extra, or unassigned approved roster occurrence; altered
  occurrence identity or hours; employee overlap; rest/hour/day assertion
  breach; or roster coverage mismatch: block roster publication.
- Named roster for a scenario other than `BASE`: block publication.
- Leave-request approval without a matching request/roster, above available
  entitlement or interval capacity, outside full-request mode, or with duplicate
  interval consumption: block publication.
- Approved swap without both consents, with assignment conflict, eligibility
  failure, coverage change, or version mismatch: block publication.
- Missing publication evidence, unresolved roster DQ, or a daylight-saving
  exception without explicit review: block publication.
- Invalid or unmatched planning adjustment: fail the analytical candidate run.
- Python candidate without a stable version and approval evidence: exclude it
  from canonical facts.
