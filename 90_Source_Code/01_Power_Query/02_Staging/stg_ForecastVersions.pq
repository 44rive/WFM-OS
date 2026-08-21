let
    Source = Excel.CurrentWorkbook(){[Name = "tblForecastVersions"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "ForecastRowKey", "Profile", "ForecastVersionKey", "ApprovalStatus",
            "Scenario", "Method", "ActivityKey", "ChannelKey", "IntervalStart",
            "ForecastVolume", "ForecastAHTSeconds", "CreatedAt", "ApprovedAt",
            "ApprovedBy", "SourceRunKey", "Notes"
        },
        "tblForecastVersions"
    ),
    NonBlank = Table.SelectRows(
        Contract,
        each [ForecastRowKey] <> null and Text.Trim(Text.From([ForecastRowKey])) <> ""
    ),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {
            {"ForecastRowKey", type text}, {"Profile", type text},
            {"ForecastVersionKey", type text}, {"ApprovalStatus", type text},
            {"Scenario", type nullable text}, {"Method", type text},
            {"ActivityKey", type text}, {"ChannelKey", type text},
            {"IntervalStart", type nullable datetime}, {"ForecastVolume", type nullable number},
            {"ForecastAHTSeconds", type nullable number}, {"CreatedAt", type nullable datetime},
            {"ApprovedAt", type nullable datetime}, {"ApprovedBy", type nullable text},
            {"SourceRunKey", type nullable text}, {"Notes", type nullable text}
        }
    ),
    ProfileRows = Table.SelectRows(Typed, each Text.From([Profile]) = p_Profile),
    NormalizedStatus = Table.TransformColumns(
        ProfileRows,
        {
            {"ApprovalStatus", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {
                "Scenario",
                each let Value = if _ = null then "" else Text.Upper(Text.Trim(Text.From(_)))
                in if Value = "" then "BASE" else Value,
                type text
            }
        }
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
    ActivityScope = Table.SelectColumns(dim_Activity, {"ActivityKey", "ChannelKey"}),
    WithActivity = Table.NestedJoin(
        WithIntervalKey,
        {"ActivityKey", "ChannelKey"},
        ActivityScope,
        {"ActivityKey", "ChannelKey"},
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
            else if [ForecastVersionKey] = null or Text.Trim([ForecastVersionKey]) = "" then "MISSING_VERSION_KEY"
            else if [ActivityKey] = null or Text.Trim([ActivityKey]) = "" then "MISSING_ACTIVITY_KEY"
            else if [ChannelKey] = null or Text.Trim([ChannelKey]) = "" then "MISSING_CHANNEL_KEY"
            else if [ActivityMatchCount] <> 1 then "UNKNOWN_ACTIVITY_CHANNEL"
            else if [IntervalStart] = null then "MISSING_INTERVAL_START"
            else if Time.Minute(Time.From([IntervalStart])) <> 0 and Time.Minute(Time.From([IntervalStart])) <> 30 then "INVALID_INTERVAL_START"
            else if Time.Second(Time.From([IntervalStart])) <> 0 then "INVALID_INTERVAL_START"
            else if [ForecastVolume] = null or [ForecastVolume] < 0 then "INVALID_FORECAST_VOLUME"
            else if [ForecastVolume] > 0 and ([ForecastAHTSeconds] = null or [ForecastAHTSeconds] <= 0) then "INVALID_FORECAST_AHT"
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
        {"Scenario", "BusinessDate", "IntervalKey", "ActivityKey", "ChannelKey"},
        {{"ApprovedGrainCount", each Table.RowCount(_), Int64.Type}}
    ),
    WithCounts = Table.NestedJoin(
        WithRowValidation,
        {"Scenario", "BusinessDate", "IntervalKey", "ActivityKey", "ChannelKey"},
        ApprovedCounts,
        {"Scenario", "BusinessDate", "IntervalKey", "ActivityKey", "ChannelKey"},
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
            else [RowValidationStatus],
        type text
    ),
    Result = Table.RemoveColumns(WithValidation, {"RowValidationStatus", "ActivityMatchCount"})
in
    Result
