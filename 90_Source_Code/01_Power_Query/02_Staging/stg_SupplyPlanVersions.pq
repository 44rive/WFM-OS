let
    Source = Excel.CurrentWorkbook(){[Name = "tblSupplyPlanVersions"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "PlanRowKey", "Profile", "PlanVersionKey", "ScenarioKey", "PolicyKey",
            "ApprovalStatus", "PeriodStart", "ActivityKey", "RequiredPaidFTE",
            "BufferPaidFTE", "BaselinePaidFTE", "PlannedHirePaidFTE", "ProjectedPaidFTE",
            "ResidualGapPaidFTE", "ApprovedAt", "ApprovedBy", "SourceRunKey"
        },
        "tblSupplyPlanVersions"
    ),
    NonBlank = Table.SelectRows(
        Contract,
        each [PlanRowKey] <> null and Text.Trim(Text.From([PlanRowKey])) <> ""
    ),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {
            {"PlanRowKey", type text}, {"Profile", type text},
            {"PlanVersionKey", type text}, {"ScenarioKey", type text},
            {"PolicyKey", type text}, {"ApprovalStatus", type text},
            {"PeriodStart", type nullable date}, {"ActivityKey", type text},
            {"RequiredPaidFTE", type nullable number}, {"BufferPaidFTE", type nullable number},
            {"BaselinePaidFTE", type nullable number},
            {"PlannedHirePaidFTE", type nullable number}, {"ProjectedPaidFTE", type nullable number},
            {"ResidualGapPaidFTE", type nullable number}, {"ApprovedAt", type nullable datetime},
            {"ApprovedBy", type nullable text}, {"SourceRunKey", type nullable text}
        }
    ),
    ProfileRows = Table.SelectRows(Typed, each Text.From([Profile]) = p_Profile),
    Normalized = Table.TransformColumns(
        ProfileRows,
        {{"ApprovalStatus", each Text.Upper(Text.Trim(Text.From(_))), type text}}
    ),
    WithApprovedFlag = Table.AddColumn(
        Normalized,
        "ApprovedFlag",
        each [ApprovalStatus] = "APPROVED",
        type logical
    ),
    ActivityScope = Table.SelectColumns(dim_Activity, {"ActivityKey"}),
    WithActivity = Table.NestedJoin(
        WithApprovedFlag,
        {"ActivityKey"},
        ActivityScope,
        {"ActivityKey"},
        "ActivityMatch",
        JoinKind.LeftOuter
    ),
    WithActivityCount = Table.AddColumn(
        WithActivity,
        "ActivityMatchCount",
        each Table.RowCount([ActivityMatch]),
        Int64.Type
    ),
    WithoutActivityTable = Table.RemoveColumns(WithActivityCount, {"ActivityMatch"}),
    WithRowValidation = Table.AddColumn(
        WithoutActivityTable,
        "RowValidationStatus",
        each
            if not [ApprovedFlag] then "NOT_APPLICABLE"
            else if [PlanVersionKey] = null or Text.Trim([PlanVersionKey]) = "" then "MISSING_PLAN_VERSION"
            else if [ScenarioKey] = null or Text.Trim([ScenarioKey]) = "" then "MISSING_SCENARIO"
            else if [PolicyKey] = null or Text.Trim([PolicyKey]) = "" then "MISSING_POLICY"
            else if [ActivityKey] = null or Text.Trim([ActivityKey]) = "" then "MISSING_ACTIVITY"
            else if [ActivityMatchCount] <> 1 then "UNKNOWN_ACTIVITY"
            else if [PeriodStart] = null then "MISSING_PERIOD_START"
            else if Date.DayOfWeek([PeriodStart], Day.Monday) <> 0 then "PERIOD_NOT_MONDAY"
            else if [RequiredPaidFTE] = null or [RequiredPaidFTE] < 0 then "INVALID_REQUIRED_FTE"
            else if [BufferPaidFTE] = null or [BufferPaidFTE] < 0 then "INVALID_BUFFER_FTE"
            else if [BaselinePaidFTE] = null or [BaselinePaidFTE] < 0 then "INVALID_BASELINE_FTE"
            else if [PlannedHirePaidFTE] = null or [PlannedHirePaidFTE] < 0 then "INVALID_HIRING_FTE"
            else if [ProjectedPaidFTE] = null or Number.Abs([ProjectedPaidFTE] - [BaselinePaidFTE] - [PlannedHirePaidFTE]) > 0.000001 then "INVALID_PROJECTED_FTE"
            else if [ResidualGapPaidFTE] = null or [ResidualGapPaidFTE] < 0 then "INVALID_RESIDUAL_GAP"
            else if Number.Abs(
                [ResidualGapPaidFTE]
                    - List.Max({0, [RequiredPaidFTE] + [BufferPaidFTE] - [ProjectedPaidFTE]})
            ) > 0.000001 then "INVALID_RESIDUAL_GAP"
            else if [ApprovedAt] = null then "MISSING_APPROVAL_TIMESTAMP"
            else if [ApprovedBy] = null or Text.Trim(Text.From([ApprovedBy])) = "" then "MISSING_APPROVER"
            else if [SourceRunKey] = null or Text.Trim(Text.From([SourceRunKey])) = "" then "MISSING_SOURCE_RUN"
            else "VALID",
        type text
    ),
    ApprovedHiring = Table.SelectRows(
        stg_HiringPlanVersions,
        each [ApprovedFlag] and [ValidationStatus] = "VALID"
    ),
    WithApprovedHiringFTE = Table.AddColumn(
        WithRowValidation,
        "ApprovedHiringPaidFTE",
        each
            if [PeriodStart] = null then null
            else let
                CurrentPlan = [PlanVersionKey],
                CurrentScenario = [ScenarioKey],
                CurrentActivity = [ActivityKey],
                CurrentPeriod = [PeriodStart],
                Matching = Table.SelectRows(
                    ApprovedHiring,
                    (HiringRow) =>
                        HiringRow[PlanVersionKey] = CurrentPlan
                            and HiringRow[ScenarioKey] = CurrentScenario
                            and HiringRow[ActivityKey] = CurrentActivity
                            and HiringRow[ProficiencyDate] <= CurrentPeriod
                )
            in
                if Table.IsEmpty(Matching) then 0 else List.Sum(Matching[ExpectedPaidFTE]),
        type nullable number
    ),
    ApprovedValid = Table.SelectRows(
        WithApprovedHiringFTE,
        each [ApprovedFlag] and [RowValidationStatus] = "VALID"
    ),
    ApprovedCounts = Table.Group(
        ApprovedValid,
        {"ScenarioKey", "PeriodStart", "ActivityKey"},
        {{"ApprovedGrainCount", each Table.RowCount(_), Int64.Type}}
    ),
    WithCounts = Table.NestedJoin(
        WithApprovedHiringFTE,
        {"ScenarioKey", "PeriodStart", "ActivityKey"},
        ApprovedCounts,
        {"ScenarioKey", "PeriodStart", "ActivityKey"},
        "ApprovedCounts",
        JoinKind.LeftOuter
    ),
    ExpandedCounts = Table.ExpandTableColumn(
        WithCounts,
        "ApprovedCounts",
        {"ApprovedGrainCount"},
        {"ApprovedGrainCount"}
    ),
    FilledCounts = Table.ReplaceValue(
        ExpandedCounts,
        null,
        0,
        Replacer.ReplaceValue,
        {"ApprovedGrainCount"}
    ),
    WithValidation = Table.AddColumn(
        FilledCounts,
        "ValidationStatus",
        each
            if [ApprovedFlag] and [RowValidationStatus] = "VALID" and [ApprovedGrainCount] > 1
            then "DUPLICATE_APPROVED_GRAIN"
            else if [ApprovedFlag] and [RowValidationStatus] = "VALID"
                and Number.Abs([PlannedHirePaidFTE] - [ApprovedHiringPaidFTE]) > 0.000001
            then "HIRING_RECONCILIATION_MISMATCH"
            else [RowValidationStatus],
        type text
    ),
    Result = Table.RemoveColumns(WithValidation, {"RowValidationStatus", "ActivityMatchCount"})
in
    Result
