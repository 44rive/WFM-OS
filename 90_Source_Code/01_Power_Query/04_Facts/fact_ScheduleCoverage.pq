let
    Plans = fact_SchedulePlan,
    PatternSource = Excel.CurrentWorkbook(){[Name = "tblShiftPatterns"]}[Content],
    PatternContract = fxAssertColumns(
        PatternSource,
        {
            "Profile", "PatternVersionKey", "PatternKey", "PatternName", "ActivityKey",
            "DayType", "SegmentKey", "StartMinute", "EndMinute", "ScheduleTypeKey",
            "PaidFlag", "ProductiveFlag", "ValidFrom", "ValidTo", "Approved"
        },
        "tblShiftPatterns"
    ),
    PatternTyped = Table.TransformColumnTypes(
        PatternContract,
        {
            {"Profile", type text}, {"PatternVersionKey", type text}, {"PatternKey", type text},
            {"ActivityKey", type text}, {"DayType", type text}, {"SegmentKey", type text},
            {"StartMinute", Int64.Type}, {"EndMinute", Int64.Type},
            {"ScheduleTypeKey", type text}, {"ValidFrom", type date}, {"ValidTo", type nullable date}
        }
    ),
    PatternNormalized = Table.TransformColumns(
        PatternTyped,
        {
            {"DayType", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {"PaidFlag", each fxAsLogical(_), type logical},
            {"ProductiveFlag", each fxAsLogical(_), type logical},
            {"Approved", each fxAsLogical(_), type logical}
        }
    ),
    ApprovedPatterns = Table.SelectRows(PatternNormalized, each [Profile] = p_Profile and [Approved]),
    WithSegments = Table.AddColumn(
        Plans,
        "Segments",
        each let
            CurrentDate = [BusinessDate],
            CurrentActivity = [ActivityKey],
            CurrentVersion = [PatternVersionKey],
            CurrentPattern = [PatternKey],
            Weekday = Text.Upper(Date.DayOfWeekName(CurrentDate, "en-US")),
            Effective = Table.SelectRows(
                ApprovedPatterns,
                (PatternRow) =>
                    PatternRow[ActivityKey] = CurrentActivity
                        and PatternRow[PatternVersionKey] = CurrentVersion
                        and PatternRow[PatternKey] = CurrentPattern
                        and PatternRow[ValidFrom] <= CurrentDate
                        and (PatternRow[ValidTo] = null or PatternRow[ValidTo] >= CurrentDate)
                        and List.Contains({"ALL", Weekday}, PatternRow[DayType])
            ),
            Exact = Table.SelectRows(Effective, each [DayType] = Weekday)
        in
            if Table.IsEmpty(Exact) then Table.SelectRows(Effective, each [DayType] = "ALL") else Exact,
        type table
    ),
    ExpandedSegments = Table.ExpandTableColumn(
        WithSegments,
        "Segments",
        {"StartMinute", "EndMinute", "PaidFlag", "ProductiveFlag"},
        {"StartMinute", "EndMinute", "PaidFlag", "ProductiveFlag"}
    ),
    WithOffsets = Table.AddColumn(
        ExpandedSegments,
        "MinuteOffset",
        each List.Transform(
            List.Numbers(Number.IntegerDivide([StartMinute], 30), Number.IntegerDivide([EndMinute] - [StartMinute], 30)),
            each _ * 30
        ),
        type list
    ),
    ExpandedOffsets = Table.ExpandListColumn(WithOffsets, "MinuteOffset"),
    WithIntervalStart = Table.AddColumn(
        ExpandedOffsets,
        "IntervalStart",
        each DateTime.From([BusinessDate]) + #duration(0, 0, [MinuteOffset], 0),
        type datetime
    ),
    WithPaidContribution = Table.AddColumn(
        WithIntervalStart,
        "ScheduledPaidFTEContribution",
        each if [PaidFlag] then [PatternCount] else 0,
        type number
    ),
    WithProductiveContribution = Table.AddColumn(
        WithPaidContribution,
        "ScheduledProductiveFTEContribution",
        each if [ProductiveFlag] then [PatternCount] else 0,
        type number
    ),
    Contributions = Table.Group(
        WithProductiveContribution,
        {"SchedulePlanVersionKey", "ScenarioKey", "IntervalStart", "ActivityKey"},
        {
            {"ScheduledPaidFTE", each List.Sum([ScheduledPaidFTEContribution]), type number},
            {"ScheduledProductiveFTE", each List.Sum([ScheduledProductiveFTEContribution]), type number}
        }
    ),
    RequirementsGrouped = Table.Group(
        out_ApprovedRequirementPlan,
        {"ScenarioKey", "BusinessDate", "IntervalStart", "IntervalKey", "ActivityKey"},
        {
            {"RequiredFTE", each List.Sum([RequiredFTE]), type number},
            {"RequirementVersion", each Text.Combine(List.Sort(List.Distinct(List.Transform([RequirementVersion], Text.From))), "|"), type text}
        }
    ),
    PlanScopes = Table.Group(
        Plans,
        {"SchedulePlanVersionKey", "ScenarioKey", "ActivityKey"},
        {
            {"MinPlanDate", each List.Min([BusinessDate]), type date},
            {"MaxPlanDate", each List.Max([BusinessDate]), type date}
        }
    ),
    RequirementsWithScopes = Table.NestedJoin(
        RequirementsGrouped,
        {"ScenarioKey", "ActivityKey"},
        PlanScopes,
        {"ScenarioKey", "ActivityKey"},
        "PlanScope",
        JoinKind.Inner
    ),
    ExpandedScopes = Table.ExpandTableColumn(
        RequirementsWithScopes,
        "PlanScope",
        {"SchedulePlanVersionKey", "MinPlanDate", "MaxPlanDate"},
        {"SchedulePlanVersionKey", "MinPlanDate", "MaxPlanDate"}
    ),
    HorizonRows = Table.SelectRows(
        ExpandedScopes,
        each [BusinessDate] >= [MinPlanDate] and [BusinessDate] <= Date.AddDays([MaxPlanDate], 1)
    ),
    WithCoverage = Table.NestedJoin(
        HorizonRows,
        {"SchedulePlanVersionKey", "ScenarioKey", "IntervalStart", "ActivityKey"},
        Contributions,
        {"SchedulePlanVersionKey", "ScenarioKey", "IntervalStart", "ActivityKey"},
        "Coverage",
        JoinKind.LeftOuter
    ),
    ExpandedCoverage = Table.ExpandTableColumn(
        WithCoverage,
        "Coverage",
        {"ScheduledPaidFTE", "ScheduledProductiveFTE"},
        {"ScheduledPaidFTE", "ScheduledProductiveFTE"}
    ),
    FilledCoverage = Table.ReplaceValue(
        ExpandedCoverage,
        null,
        0,
        Replacer.ReplaceValue,
        {"ScheduledPaidFTE", "ScheduledProductiveFTE"}
    ),
    WithGap = Table.AddColumn(
        FilledCoverage,
        "GapFTE",
        each List.Max({0, [RequiredFTE] - [ScheduledProductiveFTE]}),
        type number
    ),
    WithOver = Table.AddColumn(
        WithGap,
        "OverFTE",
        each List.Max({0, [ScheduledProductiveFTE] - [RequiredFTE]}),
        type number
    ),
    WithCoverageStatus = Table.AddColumn(
        WithOver,
        "CoverageStatus",
        each if [ScheduledProductiveFTE] >= [RequiredFTE] then "COVERED" else "UNCOVERED",
        type text
    ),
    WithMethod = Table.AddColumn(WithCoverageStatus, "CoverageMethod", each "GREEDY_DEFICIT_V1", type text),
    WithProfile = Table.AddColumn(WithMethod, "Profile", each p_Profile, type text),
    Selected = Table.SelectColumns(
        WithProfile,
        {
            "Profile", "SchedulePlanVersionKey", "ScenarioKey", "BusinessDate",
            "IntervalStart", "IntervalKey", "ActivityKey", "RequirementVersion", "RequiredFTE",
            "ScheduledPaidFTE", "ScheduledProductiveFTE", "GapFTE", "OverFTE",
            "CoverageStatus", "CoverageMethod"
        }
    ),
    Unique = fxAssertUnique(
        Selected,
        {"ScenarioKey", "IntervalStart", "ActivityKey"},
        "fact_ScheduleCoverage"
    )
in
    Unique
