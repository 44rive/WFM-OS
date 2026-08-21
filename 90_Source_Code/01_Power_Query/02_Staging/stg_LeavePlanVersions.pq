let
    Source = Excel.CurrentWorkbook(){[Name = "tblLeavePlanVersions"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "LeavePlanRowKey", "Profile", "LeavePlanVersionKey", "SchedulePlanVersionKey",
            "ScenarioKey", "PolicyKey", "ApprovalStatus", "IntervalStart", "ActivityKey",
            "RequiredFTE", "ScheduledProductiveFTE", "CalculatedAllowanceHours",
            "ApprovedAllowanceHours", "RemainingCoverageFTE", "ApprovedAt", "ApprovedBy",
            "SourceRunKey", "Notes"
        },
        "tblLeavePlanVersions"
    ),
    NonBlank = Table.SelectRows(
        Contract,
        each [LeavePlanRowKey] <> null and Text.Trim(Text.From([LeavePlanRowKey])) <> ""
    ),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {
            {"LeavePlanRowKey", type text}, {"Profile", type text},
            {"LeavePlanVersionKey", type text}, {"SchedulePlanVersionKey", type text},
            {"ScenarioKey", type text}, {"PolicyKey", type text},
            {"ApprovalStatus", type text}, {"IntervalStart", type nullable datetime},
            {"ActivityKey", type text}, {"RequiredFTE", type nullable number},
            {"ScheduledProductiveFTE", type nullable number},
            {"CalculatedAllowanceHours", type nullable number},
            {"ApprovedAllowanceHours", type nullable number},
            {"RemainingCoverageFTE", type nullable number}, {"ApprovedAt", type nullable datetime},
            {"ApprovedBy", type nullable text}, {"SourceRunKey", type nullable text},
            {"Notes", type nullable text}
        }
    ),
    ProfileRows = Table.SelectRows(Typed, each Text.From([Profile]) = p_Profile),
    Normalized = Table.TransformColumns(
        ProfileRows,
        {
            {"ApprovalStatus", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {"ScenarioKey", each Text.Upper(Text.Trim(Text.From(_))), type text}
        }
    ),
    WithApprovedFlag = Table.AddColumn(
        Normalized,
        "ApprovedFlag",
        each [ApprovalStatus] = "APPROVED",
        type logical
    ),
    WithBusinessDate = Table.AddColumn(
        WithApprovedFlag,
        "BusinessDate",
        each if [IntervalStart] = null then null else Date.From([IntervalStart]),
        type nullable date
    ),
    WithIntervalKey = Table.AddColumn(
        WithBusinessDate,
        "IntervalKey",
        each
            if [IntervalStart] = null then null
            else "I" & Text.PadStart(
                Text.From(
                    Time.Hour(Time.From([IntervalStart])) * 2
                        + Number.IntegerDivide(Time.Minute(Time.From([IntervalStart])), 30)
                ),
                2,
                "0"
            ),
        type nullable text
    ),
    ActivityScope = Table.SelectColumns(dim_Activity, {"ActivityKey"}),
    WithActivity = Table.NestedJoin(
        WithIntervalKey,
        {"ActivityKey"},
        ActivityScope,
        {"ActivityKey"},
        "ActivityMatch",
        JoinKind.LeftOuter
    ),
    WithActivityCount = Table.AddColumn(WithActivity, "ActivityMatchCount", each Table.RowCount([ActivityMatch]), Int64.Type),
    WithoutActivityTable = Table.RemoveColumns(WithActivityCount, {"ActivityMatch"}),
    CoverageScope = Table.SelectColumns(
        fact_ScheduleCoverage,
        {
            "SchedulePlanVersionKey", "ScenarioKey", "IntervalStart", "ActivityKey",
            "RequiredFTE", "ScheduledProductiveFTE", "CoverageStatus"
        }
    ),
    WithScheduleCoverage = Table.NestedJoin(
        WithoutActivityTable,
        {"SchedulePlanVersionKey", "ScenarioKey", "IntervalStart", "ActivityKey"},
        CoverageScope,
        {"SchedulePlanVersionKey", "ScenarioKey", "IntervalStart", "ActivityKey"},
        "ScheduleCoverage",
        JoinKind.LeftOuter
    ),
    WithScheduleMatchCount = Table.AddColumn(
        WithScheduleCoverage,
        "ScheduleMatchCount",
        each Table.RowCount([ScheduleCoverage]),
        Int64.Type
    ),
    ExpandedSchedule = Table.ExpandTableColumn(
        WithScheduleMatchCount,
        "ScheduleCoverage",
        {"RequiredFTE", "ScheduledProductiveFTE", "CoverageStatus"},
        {"ExpectedRequiredFTE", "ExpectedScheduledProductiveFTE", "ScheduleCoverageStatus"}
    ),
    PolicySource = Excel.CurrentWorkbook(){[Name = "tblLeavePolicies"]}[Content],
    PolicyContract = fxAssertColumns(
        PolicySource,
        {
            "Profile", "PolicyKey", "ActivityKey", "CoverageFloorPct", "ReserveFTE",
            "MaxLeavePctOfScheduled", "AllowanceIncrementHours", "ValidFrom", "ValidTo", "Approved"
        },
        "tblLeavePolicies"
    ),
    PolicyTyped = Table.TransformColumnTypes(
        PolicyContract,
        {
            {"Profile", type text}, {"PolicyKey", type text}, {"ActivityKey", type text},
            {"CoverageFloorPct", type number}, {"ReserveFTE", type number},
            {"MaxLeavePctOfScheduled", type number}, {"AllowanceIncrementHours", type number},
            {"ValidFrom", type date}, {"ValidTo", type nullable date}
        }
    ),
    PolicyNormalized = Table.TransformColumns(PolicyTyped, {{"Approved", each fxAsLogical(_), type logical}}),
    ApprovedPolicies = Table.SelectRows(PolicyNormalized, each [Profile] = p_Profile and [Approved]),
    WithPolicy = Table.AddColumn(
        ExpandedSchedule,
        "Policy",
        each
            if [BusinessDate] = null then Table.FirstN(ApprovedPolicies, 0)
            else let
                CurrentDate = [BusinessDate],
                CurrentActivity = [ActivityKey],
                CurrentPolicy = [PolicyKey]
            in
                Table.SelectRows(
                    ApprovedPolicies,
                    (PolicyRow) =>
                        PolicyRow[PolicyKey] = CurrentPolicy
                            and PolicyRow[ActivityKey] = CurrentActivity
                            and PolicyRow[ValidFrom] <= CurrentDate
                            and (PolicyRow[ValidTo] = null or PolicyRow[ValidTo] >= CurrentDate)
                ),
        type table
    ),
    WithPolicyMatchCount = Table.AddColumn(WithPolicy, "PolicyMatchCount", each Table.RowCount([Policy]), Int64.Type),
    ExpandedPolicy = Table.ExpandTableColumn(
        WithPolicyMatchCount,
        "Policy",
        {"CoverageFloorPct", "ReserveFTE", "MaxLeavePctOfScheduled", "AllowanceIncrementHours"},
        {"CoverageFloorPct", "ReserveFTE", "MaxLeavePctOfScheduled", "AllowanceIncrementHours"}
    ),
    WithExpectedAllowance = Table.AddColumn(
        ExpandedPolicy,
        "ExpectedCalculatedAllowanceHours",
        each
            if [ScheduleMatchCount] <> 1 or [PolicyMatchCount] <> 1 then null
            else let
                FloorFTE = [ExpectedRequiredFTE] * [CoverageFloorPct] + [ReserveFTE],
                HeadroomFTE = List.Max({0, [ExpectedScheduledProductiveFTE] - FloorFTE}),
                PercentageCapFTE = [ExpectedScheduledProductiveFTE] * [MaxLeavePctOfScheduled],
                RawHours = List.Min({HeadroomFTE, PercentageCapFTE}) * 0.5
            in
                Number.RoundDown(RawHours / [AllowanceIncrementHours]) * [AllowanceIncrementHours],
        type nullable number
    ),
    WithExpectedRemaining = Table.AddColumn(
        WithExpectedAllowance,
        "ExpectedRemainingCoverageFTE",
        each
            if [ScheduleMatchCount] <> 1 or [ApprovedAllowanceHours] = null then null
            else [ExpectedScheduledProductiveFTE] - [ApprovedAllowanceHours] / 0.5,
        type nullable number
    ),
    WithRowValidation = Table.AddColumn(
        WithExpectedRemaining,
        "RowValidationStatus",
        each
            if not [ApprovedFlag] then "NOT_APPLICABLE"
            else if [LeavePlanVersionKey] = null or Text.Trim([LeavePlanVersionKey]) = "" then "MISSING_LEAVE_VERSION"
            else if [SchedulePlanVersionKey] = null or Text.Trim([SchedulePlanVersionKey]) = "" then "MISSING_SCHEDULE_VERSION"
            else if [ScenarioKey] = null or Text.Trim([ScenarioKey]) = "" then "MISSING_SCENARIO"
            else if [PolicyKey] = null or Text.Trim([PolicyKey]) = "" then "MISSING_POLICY"
            else if [IntervalStart] = null then "MISSING_INTERVAL_START"
            else if (Time.Minute(Time.From([IntervalStart])) <> 0 and Time.Minute(Time.From([IntervalStart])) <> 30) or Time.Second(Time.From([IntervalStart])) <> 0 then "INVALID_INTERVAL_START"
            else if [ActivityKey] = null or Text.Trim([ActivityKey]) = "" then "MISSING_ACTIVITY"
            else if [ActivityMatchCount] <> 1 then "UNKNOWN_ACTIVITY"
            else if [ScheduleMatchCount] <> 1 then "SCHEDULE_COVERAGE_NOT_FOUND"
            else if [PolicyMatchCount] <> 1 then "LEAVE_POLICY_NOT_EFFECTIVE"
            else if [CoverageFloorPct] < 1 or [CoverageFloorPct] > 2 then "INVALID_COVERAGE_FLOOR"
            else if [ReserveFTE] < 0 then "INVALID_RESERVE_FTE"
            else if [MaxLeavePctOfScheduled] < 0 or [MaxLeavePctOfScheduled] > 1 then "INVALID_LEAVE_PERCENTAGE"
            else if [AllowanceIncrementHours] <= 0 or [AllowanceIncrementHours] > 0.5 then "INVALID_ALLOWANCE_INCREMENT"
            else if [RequiredFTE] = null or Number.Abs([RequiredFTE] - [ExpectedRequiredFTE]) > 0.000001 then "REQUIRED_FTE_MISMATCH"
            else if [ScheduledProductiveFTE] = null or Number.Abs([ScheduledProductiveFTE] - [ExpectedScheduledProductiveFTE]) > 0.000001 then "SCHEDULED_FTE_MISMATCH"
            else if [CalculatedAllowanceHours] = null or Number.Abs([CalculatedAllowanceHours] - [ExpectedCalculatedAllowanceHours]) > 0.000001 then "CALCULATED_ALLOWANCE_MISMATCH"
            else if [ApprovedAllowanceHours] = null or [ApprovedAllowanceHours] < 0 or [ApprovedAllowanceHours] > [ExpectedCalculatedAllowanceHours] then "APPROVED_ALLOWANCE_OUT_OF_RANGE"
            else if [RemainingCoverageFTE] = null or Number.Abs([RemainingCoverageFTE] - [ExpectedRemainingCoverageFTE]) > 0.000001 then "REMAINING_COVERAGE_MISMATCH"
            else if [ApprovedAt] = null then "MISSING_APPROVAL_TIMESTAMP"
            else if [ApprovedBy] = null or Text.Trim(Text.From([ApprovedBy])) = "" then "MISSING_APPROVER"
            else if [SourceRunKey] = null or Text.Trim(Text.From([SourceRunKey])) = "" then "MISSING_SOURCE_RUN"
            else "VALID",
        type text
    ),
    ApprovedValid = Table.SelectRows(WithRowValidation, each [ApprovedFlag] and [RowValidationStatus] = "VALID"),
    ApprovedCounts = Table.Group(
        ApprovedValid,
        {"SchedulePlanVersionKey", "ScenarioKey", "IntervalStart", "ActivityKey"},
        {{"ApprovedGrainCount", each Table.RowCount(_), Int64.Type}}
    ),
    WithCounts = Table.NestedJoin(
        WithRowValidation,
        {"SchedulePlanVersionKey", "ScenarioKey", "IntervalStart", "ActivityKey"},
        ApprovedCounts,
        {"SchedulePlanVersionKey", "ScenarioKey", "IntervalStart", "ActivityKey"},
        "ApprovedCounts",
        JoinKind.LeftOuter
    ),
    ExpandedCounts = Table.ExpandTableColumn(WithCounts, "ApprovedCounts", {"ApprovedGrainCount"}, {"ApprovedGrainCount"}),
    FilledCounts = Table.ReplaceValue(ExpandedCounts, null, 0, Replacer.ReplaceValue, {"ApprovedGrainCount"}),
    ScopeVersions = Table.Group(
        ApprovedValid,
        {"SchedulePlanVersionKey", "ScenarioKey", "ActivityKey"},
        {{"ApprovedVersionCount", each List.Count(List.Distinct([LeavePlanVersionKey])), Int64.Type}}
    ),
    WithScopeVersions = Table.NestedJoin(
        FilledCounts,
        {"SchedulePlanVersionKey", "ScenarioKey", "ActivityKey"},
        ScopeVersions,
        {"SchedulePlanVersionKey", "ScenarioKey", "ActivityKey"},
        "ScopeVersions",
        JoinKind.LeftOuter
    ),
    ExpandedScopeVersions = Table.ExpandTableColumn(WithScopeVersions, "ScopeVersions", {"ApprovedVersionCount"}, {"ApprovedVersionCount"}),
    FilledScopeVersions = Table.ReplaceValue(ExpandedScopeVersions, null, 0, Replacer.ReplaceValue, {"ApprovedVersionCount"}),
    WithValidation = Table.AddColumn(
        FilledScopeVersions,
        "ValidationStatus",
        each
            if [ApprovedFlag] and [RowValidationStatus] = "VALID" and [ApprovedGrainCount] > 1 then "DUPLICATE_APPROVED_GRAIN"
            else if [ApprovedFlag] and [RowValidationStatus] = "VALID" and [ApprovedVersionCount] > 1 then "MIXED_APPROVED_LEAVE_VERSIONS"
            else [RowValidationStatus],
        type text
    ),
    Result = Table.RemoveColumns(
        WithValidation,
        {
            "RowValidationStatus", "ActivityMatchCount", "ScheduleCoverageStatus",
            "CoverageFloorPct", "ReserveFTE", "MaxLeavePctOfScheduled", "AllowanceIncrementHours"
        }
    )
in
    Result
