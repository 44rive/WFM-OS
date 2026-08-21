let
    Source = Excel.CurrentWorkbook(){[Name = "tblSchedulePlanVersions"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "SchedulePlanRowKey", "Profile", "SchedulePlanVersionKey", "ScenarioKey",
            "ApprovalStatus", "BusinessDate", "ActivityKey", "PatternVersionKey",
            "PatternKey", "PatternCount", "PaidHours", "ProductiveHours",
            "CoverageMethod", "ApprovedAt", "ApprovedBy", "SourceRunKey", "Notes"
        },
        "tblSchedulePlanVersions"
    ),
    NonBlank = Table.SelectRows(
        Contract,
        each [SchedulePlanRowKey] <> null and Text.Trim(Text.From([SchedulePlanRowKey])) <> ""
    ),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {
            {"SchedulePlanRowKey", type text}, {"Profile", type text},
            {"SchedulePlanVersionKey", type text}, {"ScenarioKey", type text},
            {"ApprovalStatus", type text}, {"BusinessDate", type nullable date},
            {"ActivityKey", type text}, {"PatternVersionKey", type text},
            {"PatternKey", type text}, {"PatternCount", type nullable number},
            {"PaidHours", type nullable number}, {"ProductiveHours", type nullable number},
            {"CoverageMethod", type text}, {"ApprovedAt", type nullable datetime},
            {"ApprovedBy", type nullable text}, {"SourceRunKey", type nullable text},
            {"Notes", type nullable text}
        }
    ),
    ProfileRows = Table.SelectRows(Typed, each Text.From([Profile]) = p_Profile),
    Normalized = Table.TransformColumns(
        ProfileRows,
        {
            {"ApprovalStatus", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {"ScenarioKey", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {"CoverageMethod", each Text.Upper(Text.Trim(Text.From(_))), type text}
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
            {"PatternName", type text}, {"ActivityKey", type text}, {"DayType", type text},
            {"SegmentKey", type text}, {"StartMinute", Int64.Type}, {"EndMinute", Int64.Type},
            {"ScheduleTypeKey", type text}, {"ValidFrom", type date},
            {"ValidTo", type nullable date}
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
    ApprovedPatterns = Table.SelectRows(
        PatternNormalized,
        each [Profile] = p_Profile and [Approved]
    ),
    RuleSource = Excel.CurrentWorkbook(){[Name = "tblShiftRules"]}[Content],
    RuleContract = fxAssertColumns(
        RuleSource,
        {
            "Profile", "RuleKey", "ActivityKey", "RuleType", "PatternKey", "Value",
            "Unit", "ValidFrom", "ValidTo", "Approved", "Owner", "Notes"
        },
        "tblShiftRules"
    ),
    RuleTyped = Table.TransformColumnTypes(
        RuleContract,
        {
            {"Profile", type text}, {"RuleKey", type text}, {"ActivityKey", type text},
            {"RuleType", type text}, {"PatternKey", type text}, {"Value", type number},
            {"Unit", type text}, {"ValidFrom", type date}, {"ValidTo", type nullable date}
        }
    ),
    RuleNormalized = Table.TransformColumns(
        RuleTyped,
        {
            {"RuleType", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {"Approved", each fxAsLogical(_), type logical}
        }
    ),
    ApprovedRules = Table.SelectRows(RuleNormalized, each [Profile] = p_Profile and [Approved]),
    WithRuleSummary = Table.AddColumn(
        WithoutActivityTable,
        "RuleSummary",
        each
            if [BusinessDate] = null then
                [MinRuleCount = 0, MaxRuleCount = 0, PreferenceRuleCount = 0, MinPatternCount = null, MaxPatternCount = null, PreferenceCost = null]
            else let
                CurrentDate = [BusinessDate],
                CurrentActivity = [ActivityKey],
                CurrentPattern = [PatternKey],
                Effective = Table.SelectRows(
                    ApprovedRules,
                    (RuleRow) =>
                        RuleRow[ActivityKey] = CurrentActivity
                            and RuleRow[PatternKey] = CurrentPattern
                            and RuleRow[ValidFrom] <= CurrentDate
                            and (RuleRow[ValidTo] = null or RuleRow[ValidTo] >= CurrentDate)
                ),
                Minimum = Table.SelectRows(Effective, each [RuleType] = "MIN_PATTERN_COUNT"),
                Maximum = Table.SelectRows(Effective, each [RuleType] = "MAX_PATTERN_COUNT"),
                Preference = Table.SelectRows(Effective, each [RuleType] = "PREFERENCE_COST")
            in
                [
                    MinRuleCount = Table.RowCount(Minimum),
                    MaxRuleCount = Table.RowCount(Maximum),
                    PreferenceRuleCount = Table.RowCount(Preference),
                    MinPatternCount = if Table.RowCount(Minimum) = 1 then Minimum{0}[Value] else null,
                    MaxPatternCount = if Table.RowCount(Maximum) = 1 then Maximum{0}[Value] else null,
                    PreferenceCost = if Table.RowCount(Preference) = 1 then Preference{0}[Value] else null
                ],
        type record
    ),
    ExpandedRuleSummary = Table.ExpandRecordColumn(
        WithRuleSummary,
        "RuleSummary",
        {"MinRuleCount", "MaxRuleCount", "PreferenceRuleCount", "MinPatternCount", "MaxPatternCount", "PreferenceCost"},
        {"MinRuleCount", "MaxRuleCount", "PreferenceRuleCount", "MinPatternCount", "MaxPatternCount", "PreferenceCost"}
    ),
    WithPatternSegments = Table.AddColumn(
        ExpandedRuleSummary,
        "PatternSegments",
        each
            if [BusinessDate] = null then Table.FirstN(ApprovedPatterns, 0)
            else let
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
                Exact = Table.SelectRows(Effective, each [DayType] = Weekday),
                Selected = if Table.IsEmpty(Exact) then Table.SelectRows(Effective, each [DayType] = "ALL") else Exact
            in
                Selected,
        type table
    ),
    WithPatternSegmentCount = Table.AddColumn(
        WithPatternSegments,
        "PatternSegmentCount",
        each Table.RowCount([PatternSegments]),
        Int64.Type
    ),
    WithPatternDefinitionStatus = Table.AddColumn(
        WithPatternSegmentCount,
        "PatternDefinitionStatus",
        each
            if Table.IsEmpty([PatternSegments]) then "PATTERN_NOT_EFFECTIVE"
            else let
                Segments = Table.ToRecords(Table.Sort([PatternSegments], {{"StartMinute", Order.Ascending}, {"EndMinute", Order.Ascending}, {"SegmentKey", Order.Ascending}})),
                InvalidBoundary = List.AnyTrue(
                    List.Transform(
                        Segments,
                        (Segment) =>
                            Segment[StartMinute] < 0
                                or Segment[EndMinute] <= Segment[StartMinute]
                                or Segment[EndMinute] > 2880
                                or Number.Mod(Segment[StartMinute], 30) <> 0
                                or Number.Mod(Segment[EndMinute], 30) <> 0
                    )
                ),
                InvalidProductive = List.AnyTrue(
                    List.Transform(Segments, (Segment) => Segment[ProductiveFlag] and not Segment[PaidFlag])
                ),
                SegmentKeys = List.Transform(Segments, each Text.From(_[SegmentKey])),
                DuplicateSegment = List.Count(SegmentKeys) <> List.Count(List.Distinct(SegmentKeys)),
                AdjacentPairs = if List.Count(Segments) < 2 then {} else List.Zip({List.RemoveLastN(Segments, 1), List.Skip(Segments, 1)}),
                Overlap = List.AnyTrue(List.Transform(AdjacentPairs, each _{1}[StartMinute] < _{0}[EndMinute])),
                HasPaid = List.AnyTrue(List.Transform(Segments, each _[PaidFlag])),
                HasProductive = List.AnyTrue(List.Transform(Segments, each _[ProductiveFlag]))
            in
                if InvalidBoundary then "INVALID_PATTERN_BOUNDARY"
                else if InvalidProductive then "PRODUCTIVE_SEGMENT_NOT_PAID"
                else if DuplicateSegment then "DUPLICATE_PATTERN_SEGMENT"
                else if Overlap then "OVERLAPPING_PATTERN_SEGMENTS"
                else if not HasPaid then "PATTERN_HAS_NO_PAID_TIME"
                else if not HasProductive then "PATTERN_HAS_NO_PRODUCTIVE_TIME"
                else "VALID",
        type text
    ),
    WithCalculatedPaidHours = Table.AddColumn(
        WithPatternDefinitionStatus,
        "CalculatedPaidHours",
        each
            if [PatternCount] = null or Table.IsEmpty([PatternSegments]) then null
            else [PatternCount] * List.Sum(
                Table.AddColumn(
                    [PatternSegments],
                    "SegmentHours",
                    each if [PaidFlag] then ([EndMinute] - [StartMinute]) / 60 else 0,
                    type number
                )[SegmentHours]
            ),
        type nullable number
    ),
    WithCalculatedProductiveHours = Table.AddColumn(
        WithCalculatedPaidHours,
        "CalculatedProductiveHours",
        each
            if [PatternCount] = null or Table.IsEmpty([PatternSegments]) then null
            else [PatternCount] * List.Sum(
                Table.AddColumn(
                    [PatternSegments],
                    "SegmentHours",
                    each if [ProductiveFlag] then ([EndMinute] - [StartMinute]) / 60 else 0,
                    type number
                )[SegmentHours]
            ),
        type nullable number
    ),
    WithoutPatternTable = Table.RemoveColumns(WithCalculatedProductiveHours, {"PatternSegments"}),
    WithRowValidation = Table.AddColumn(
        WithoutPatternTable,
        "RowValidationStatus",
        each
            if not [ApprovedFlag] then "NOT_APPLICABLE"
            else if [SchedulePlanVersionKey] = null or Text.Trim([SchedulePlanVersionKey]) = "" then "MISSING_SCHEDULE_VERSION"
            else if [ScenarioKey] = null or Text.Trim([ScenarioKey]) = "" then "MISSING_SCENARIO"
            else if [BusinessDate] = null then "MISSING_BUSINESS_DATE"
            else if [ActivityKey] = null or Text.Trim([ActivityKey]) = "" then "MISSING_ACTIVITY"
            else if [ActivityMatchCount] <> 1 then "UNKNOWN_ACTIVITY"
            else if [PatternVersionKey] = null or Text.Trim([PatternVersionKey]) = "" then "MISSING_PATTERN_VERSION"
            else if [PatternKey] = null or Text.Trim([PatternKey]) = "" then "MISSING_PATTERN"
            else if [PatternDefinitionStatus] <> "VALID" then [PatternDefinitionStatus]
            else if [MinRuleCount] <> 1 or [MaxRuleCount] <> 1 or [PreferenceRuleCount] <> 1 then "SHIFT_RULE_NOT_EFFECTIVE"
            else if [MinPatternCount] < 0 or Number.RoundDown([MinPatternCount]) <> [MinPatternCount] then "INVALID_MIN_PATTERN_COUNT"
            else if [MaxPatternCount] < [MinPatternCount] or Number.RoundDown([MaxPatternCount]) <> [MaxPatternCount] then "INVALID_MAX_PATTERN_COUNT"
            else if [PreferenceCost] < 0 then "INVALID_PREFERENCE_COST"
            else if [PatternCount] = null or [PatternCount] <= 0 or Number.RoundDown([PatternCount]) <> [PatternCount] then "INVALID_PATTERN_COUNT"
            else if [PatternCount] < [MinPatternCount] or [PatternCount] > [MaxPatternCount] then "PATTERN_COUNT_OUTSIDE_RULE"
            else if [CoverageMethod] <> "GREEDY_DEFICIT_V1" then "UNSUPPORTED_COVERAGE_METHOD"
            else if [PaidHours] = null or Number.Abs([PaidHours] - [CalculatedPaidHours]) > 0.000001 then "PAID_HOURS_MISMATCH"
            else if [ProductiveHours] = null or Number.Abs([ProductiveHours] - [CalculatedProductiveHours]) > 0.000001 then "PRODUCTIVE_HOURS_MISMATCH"
            else if [ProductiveHours] > [PaidHours] then "PRODUCTIVE_EXCEEDS_PAID"
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
        {"ScenarioKey", "BusinessDate", "ActivityKey", "PatternVersionKey", "PatternKey"},
        {{"ApprovedGrainCount", each Table.RowCount(_), Int64.Type}}
    ),
    WithCounts = Table.NestedJoin(
        WithRowValidation,
        {"ScenarioKey", "BusinessDate", "ActivityKey", "PatternVersionKey", "PatternKey"},
        ApprovedCounts,
        {"ScenarioKey", "BusinessDate", "ActivityKey", "PatternVersionKey", "PatternKey"},
        "ApprovedCounts",
        JoinKind.LeftOuter
    ),
    ExpandedCounts = Table.ExpandTableColumn(WithCounts, "ApprovedCounts", {"ApprovedGrainCount"}, {"ApprovedGrainCount"}),
    FilledCounts = Table.ReplaceValue(ExpandedCounts, null, 0, Replacer.ReplaceValue, {"ApprovedGrainCount"}),
    ScopeVersions = Table.Group(
        ApprovedValid,
        {"ScenarioKey", "BusinessDate", "ActivityKey"},
        {{"ApprovedVersionCount", each List.Count(List.Distinct([SchedulePlanVersionKey])), Int64.Type}}
    ),
    WithScopeVersions = Table.NestedJoin(
        FilledCounts,
        {"ScenarioKey", "BusinessDate", "ActivityKey"},
        ScopeVersions,
        {"ScenarioKey", "BusinessDate", "ActivityKey"},
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
            else if [ApprovedFlag] and [RowValidationStatus] = "VALID" and [ApprovedVersionCount] > 1 then "MIXED_APPROVED_SCHEDULE_VERSIONS"
            else [RowValidationStatus],
        type text
    ),
    Result = Table.RemoveColumns(WithValidation, {"RowValidationStatus", "ActivityMatchCount"})
in
    Result
