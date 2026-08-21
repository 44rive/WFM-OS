let
    Source = Excel.CurrentWorkbook(){[Name = "tblRequirementApprovals"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "RequirementKey", "Profile", "ForecastVersionKey", "CapacityPolicyKey",
            "ApprovalStatus", "IntervalStart", "ActivityKey", "RequiredFTE",
            "PaidFTE", "RequiredHeads", "ShrinkagePct", "RequirementVersion",
            "ApprovedAt", "ApprovedBy", "SourceRunKey", "Notes"
        },
        "tblRequirementApprovals"
    ),
    NonBlank = Table.SelectRows(
        Contract,
        each [RequirementKey] <> null and Text.Trim(Text.From([RequirementKey])) <> ""
    ),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {
            {"RequirementKey", type text}, {"Profile", type text},
            {"ForecastVersionKey", type nullable text}, {"CapacityPolicyKey", type text},
            {"ApprovalStatus", type text}, {"IntervalStart", type nullable datetime},
            {"ActivityKey", type text}, {"RequiredFTE", type nullable number},
            {"PaidFTE", type nullable number}, {"RequiredHeads", Int64.Type},
            {"ShrinkagePct", type nullable number}, {"RequirementVersion", type text},
            {"ApprovedAt", type nullable datetime}, {"ApprovedBy", type nullable text},
            {"SourceRunKey", type nullable text}, {"Notes", type nullable text}
        }
    ),
    ProfileRows = Table.SelectRows(Typed, each Text.From([Profile]) = p_Profile),
    NormalizedStatus = Table.TransformColumns(
        ProfileRows,
        {{"ApprovalStatus", each Text.Upper(Text.Trim(Text.From(_))), type text}}
    ),
    WithApprovedFlag = Table.AddColumn(
        NormalizedStatus,
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
    WithActivityCount = Table.AddColumn(
        WithActivity,
        "ActivityMatchCount",
        each Table.RowCount([ActivityMatch]),
        Int64.Type
    ),
    WithoutActivityTable = Table.RemoveColumns(WithActivityCount, {"ActivityMatch"}),
    WithValidation = Table.AddColumn(
        WithoutActivityTable,
        "MappingStatus",
        each
            if not [ApprovedFlag] then "NOT_APPLICABLE"
            else if [ActivityKey] = null or Text.Trim([ActivityKey]) = "" then "MISSING_ACTIVITY_KEY"
            else if [ActivityMatchCount] <> 1 then "UNKNOWN_ACTIVITY_KEY"
            else if [CapacityPolicyKey] = null or Text.Trim([CapacityPolicyKey]) = "" then "MISSING_CAPACITY_POLICY"
            else if [RequirementVersion] = null or Text.Trim([RequirementVersion]) = "" then "MISSING_REQUIREMENT_VERSION"
            else if [IntervalStart] = null then "MISSING_INTERVAL_START"
            else if Time.Minute(Time.From([IntervalStart])) <> 0 and Time.Minute(Time.From([IntervalStart])) <> 30 then "INVALID_INTERVAL_START"
            else if Time.Second(Time.From([IntervalStart])) <> 0 then "INVALID_INTERVAL_START"
            else if [RequiredFTE] = null or [RequiredFTE] < 0 then "INVALID_REQUIRED_FTE"
            else if [PaidFTE] = null or [PaidFTE] < [RequiredFTE] then "INVALID_PAID_FTE"
            else if [RequiredHeads] = null or [RequiredHeads] < 0 then "INVALID_REQUIRED_HEADS"
            else if [ShrinkagePct] = null or [ShrinkagePct] < 0 or [ShrinkagePct] >= 1 then "INVALID_SHRINKAGE"
            else if [ApprovedAt] = null then "MISSING_APPROVAL_TIMESTAMP"
            else if [ApprovedBy] = null or Text.Trim(Text.From([ApprovedBy])) = "" then "MISSING_APPROVER"
            else if [SourceRunKey] = null or Text.Trim(Text.From([SourceRunKey])) = "" then "MISSING_SOURCE_RUN"
            else "MAPPED",
        type text
    ),
    WithMappingValue = Table.AddColumn(
        WithValidation,
        "MappingValue",
        each if [MappingStatus] = "MAPPED" or [MappingStatus] = "NOT_APPLICABLE" then null else [RequirementKey],
        type nullable text
    ),
    ValidApproved = Table.SelectRows(
        WithMappingValue,
        each [ApprovedFlag] and [MappingStatus] = "MAPPED"
    ),
    ApprovedCounts = Table.Group(
        ValidApproved,
        {"BusinessDate", "IntervalStart", "ActivityKey"},
        {{"ApprovedGrainCount", each Table.RowCount(_), Int64.Type}}
    ),
    WithCounts = Table.NestedJoin(
        WithMappingValue,
        {"BusinessDate", "IntervalStart", "ActivityKey"},
        ApprovedCounts,
        {"BusinessDate", "IntervalStart", "ActivityKey"},
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
    Result = Table.AddColumn(
        FilledCounts,
        "FinalMappingStatus",
        each
            if [ApprovedFlag] and [MappingStatus] = "MAPPED" and [ApprovedGrainCount] > 1
            then "DUPLICATE_APPROVED_GRAIN"
            else [MappingStatus],
        type text
    ),
    WithoutOriginal = Table.RemoveColumns(Result, {"MappingStatus", "ActivityMatchCount"}),
    Renamed = Table.RenameColumns(WithoutOriginal, {{"FinalMappingStatus", "MappingStatus"}})
in
    Renamed
