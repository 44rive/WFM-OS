let
    Source = Excel.CurrentWorkbook(){[Name = "tblHiringPlanVersions"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "WaveKey", "Profile", "PlanVersionKey", "ScenarioKey", "PolicyKey",
            "ApprovalStatus", "ActivityKey", "RecruitmentStart", "TrainingStart",
            "NestingStart", "ProficiencyDate", "PlannedHeads", "ExpectedPaidFTE", "TimingStatus",
            "ApprovedAt", "ApprovedBy", "SourceRunKey"
        },
        "tblHiringPlanVersions"
    ),
    NonBlank = Table.SelectRows(
        Contract,
        each [WaveKey] <> null and Text.Trim(Text.From([WaveKey])) <> ""
    ),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {
            {"WaveKey", type text}, {"Profile", type text},
            {"PlanVersionKey", type text}, {"ScenarioKey", type text},
            {"PolicyKey", type text}, {"ApprovalStatus", type text},
            {"ActivityKey", type text}, {"RecruitmentStart", type nullable date},
            {"TrainingStart", type nullable date}, {"NestingStart", type nullable date},
            {"ProficiencyDate", type nullable date},
            {"PlannedHeads", type nullable number}, {"ExpectedPaidFTE", type nullable number},
            {"TimingStatus", type text}, {"ApprovedAt", type nullable datetime},
            {"ApprovedBy", type nullable text}, {"SourceRunKey", type nullable text}
        }
    ),
    ProfileRows = Table.SelectRows(Typed, each Text.From([Profile]) = p_Profile),
    Normalized = Table.TransformColumns(
        ProfileRows,
        {
            {"ApprovalStatus", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {"TimingStatus", each Text.Upper(Text.Trim(Text.From(_))), type text}
        }
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
            else if [RecruitmentStart] = null or [TrainingStart] = null or [NestingStart] = null or [ProficiencyDate] = null then "MISSING_WAVE_DATE"
            else if [RecruitmentStart] > [TrainingStart] or [TrainingStart] > [NestingStart] or [NestingStart] > [ProficiencyDate] then "INVALID_WAVE_SEQUENCE"
            else if [PlannedHeads] = null or [PlannedHeads] <= 0 then "INVALID_PLANNED_HEADS"
            else if Number.RoundDown([PlannedHeads]) <> [PlannedHeads] then "INVALID_PLANNED_HEADS"
            else if [ExpectedPaidFTE] = null or [ExpectedPaidFTE] <= 0 then "INVALID_EXPECTED_FTE"
            else if not List.Contains({"ON_TIME", "LATE_TO_PLAN"}, [TimingStatus]) then "INVALID_TIMING_STATUS"
            else if [ApprovedAt] = null then "MISSING_APPROVAL_TIMESTAMP"
            else if [ApprovedBy] = null or Text.Trim(Text.From([ApprovedBy])) = "" then "MISSING_APPROVER"
            else if [SourceRunKey] = null or Text.Trim(Text.From([SourceRunKey])) = "" then "MISSING_SOURCE_RUN"
            else "VALID",
        type text
    ),
    ApprovedValid = Table.SelectRows(
        WithRowValidation,
        each [ApprovedFlag] and [RowValidationStatus] = "VALID"
    ),
    ApprovedCounts = Table.Group(
        ApprovedValid,
        {"WaveKey"},
        {{"ApprovedWaveCount", each Table.RowCount(_), Int64.Type}}
    ),
    WithCounts = Table.NestedJoin(
        WithRowValidation,
        {"WaveKey"},
        ApprovedCounts,
        {"WaveKey"},
        "ApprovedCounts",
        JoinKind.LeftOuter
    ),
    ExpandedCounts = Table.ExpandTableColumn(
        WithCounts,
        "ApprovedCounts",
        {"ApprovedWaveCount"},
        {"ApprovedWaveCount"}
    ),
    FilledCounts = Table.ReplaceValue(
        ExpandedCounts,
        null,
        0,
        Replacer.ReplaceValue,
        {"ApprovedWaveCount"}
    ),
    WithValidation = Table.AddColumn(
        FilledCounts,
        "ValidationStatus",
        each
            if [ApprovedFlag] and [RowValidationStatus] = "VALID" and [ApprovedWaveCount] > 1
            then "DUPLICATE_APPROVED_WAVE"
            else [RowValidationStatus],
        type text
    ),
    Result = Table.RemoveColumns(WithValidation, {"RowValidationStatus", "ActivityMatchCount"})
in
    Result
