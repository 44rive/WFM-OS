let
    Source = Excel.CurrentWorkbook(){[Name = "tblRosterPlanVersions"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "RosterPlanRowKey", "AssignmentKey", "Profile", "RosterVersionKey",
            "SchedulePlanVersionKey", "ScenarioKey", "ApprovalStatus", "OccurrenceKey",
            "BusinessDate", "ActivityKey", "PatternVersionKey", "PatternKey",
            "OccurrenceOrdinal", "AgentKey", "ContractKey", "PaidHours",
            "ProductiveHours", "AssignmentMethod", "AssignmentStatus", "FairnessScore",
            "PreferenceCost", "ApprovedAt", "ApprovedBy", "SourceRunKey", "Notes"
        },
        "tblRosterPlanVersions"
    ),
    NonBlank = Table.SelectRows(Contract, each [RosterPlanRowKey] <> null and Text.Trim(Text.From([RosterPlanRowKey])) <> ""),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {
            {"RosterPlanRowKey", type text}, {"AssignmentKey", type text}, {"Profile", type text},
            {"RosterVersionKey", type text}, {"SchedulePlanVersionKey", type text},
            {"ScenarioKey", type text}, {"ApprovalStatus", type text}, {"OccurrenceKey", type text},
            {"BusinessDate", type date}, {"ActivityKey", type text}, {"PatternVersionKey", type text},
            {"PatternKey", type text}, {"OccurrenceOrdinal", Int64.Type}, {"AgentKey", type text},
            {"ContractKey", type text}, {"PaidHours", type number}, {"ProductiveHours", type number},
            {"AssignmentMethod", type text}, {"AssignmentStatus", type text},
            {"FairnessScore", type number}, {"PreferenceCost", type number},
            {"ApprovedAt", type nullable datetime}, {"ApprovedBy", type nullable text},
            {"SourceRunKey", type nullable text}, {"Notes", type nullable text}
        }
    ),
    ProfileRows = Table.SelectRows(Typed, each [Profile] = p_Profile),
    Normalized = Table.TransformColumns(
        ProfileRows,
        {
            {"ScenarioKey", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {"ApprovalStatus", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {"AssignmentMethod", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {"AssignmentStatus", each Text.Upper(Text.Trim(Text.From(_))), type text}
        }
    ),
    WithApprovedFlag = Table.AddColumn(Normalized, "ApprovedFlag", each [ApprovalStatus] = "APPROVED", type logical),
    AgentScope = Table.SelectColumns(dim_Agent, {"AgentKey"}),
    WithAgent = Table.NestedJoin(WithApprovedFlag, {"AgentKey"}, AgentScope, {"AgentKey"}, "AgentMatch", JoinKind.LeftOuter),
    WithAgentCount = Table.AddColumn(WithAgent, "AgentMatchCount", each Table.RowCount([AgentMatch]), Int64.Type),
    WithoutAgent = Table.RemoveColumns(WithAgentCount, {"AgentMatch"}),
    WithRowValidation = Table.AddColumn(
        WithoutAgent,
        "RowValidationStatus",
        each
            if not [ApprovedFlag] then "NOT_APPLICABLE"
            else if [RosterVersionKey] = null or Text.Trim([RosterVersionKey]) = "" then "MISSING_ROSTER_VERSION"
            else if [SchedulePlanVersionKey] = null or Text.Trim([SchedulePlanVersionKey]) = "" then "MISSING_SCHEDULE_VERSION"
            else if [ScenarioKey] <> "BASE" then "NAMED_ROSTER_REQUIRES_BASE"
            else if [AssignmentKey] = null or Text.Trim([AssignmentKey]) = "" then "MISSING_ASSIGNMENT_KEY"
            else if [OccurrenceKey] = null or Text.Trim([OccurrenceKey]) = "" then "MISSING_OCCURRENCE_KEY"
            else if [BusinessDate] = null then "MISSING_BUSINESS_DATE"
            else if [ActivityKey] = null or Text.Trim([ActivityKey]) = "" then "MISSING_ACTIVITY"
            else if [OccurrenceOrdinal] = null or [OccurrenceOrdinal] < 1 then "INVALID_OCCURRENCE_ORDINAL"
            else if [AgentMatchCount] <> 1 then "UNKNOWN_AGENT"
            else if [PaidHours] = null or [PaidHours] <= 0 then "INVALID_PAID_HOURS"
            else if [ProductiveHours] = null or [ProductiveHours] < 0 or [ProductiveHours] > [PaidHours] then "INVALID_PRODUCTIVE_HOURS"
            else if [AssignmentMethod] <> "CONSTRAINED_GREEDY_REPAIR_V1" then "UNSUPPORTED_ASSIGNMENT_METHOD"
            else if [AssignmentStatus] <> "ASSIGNED" then "ASSIGNMENT_NOT_COMPLETE"
            else if [FairnessScore] = null or [FairnessScore] < 0 then "INVALID_FAIRNESS_SCORE"
            else if [PreferenceCost] = null or [PreferenceCost] < 0 then "INVALID_PREFERENCE_COST"
            else if [ApprovedAt] = null then "MISSING_APPROVAL_TIMESTAMP"
            else if [ApprovedBy] = null or Text.Trim(Text.From([ApprovedBy])) = "" then "MISSING_APPROVER"
            else if [SourceRunKey] = null or Text.Trim(Text.From([SourceRunKey])) = "" then "MISSING_SOURCE_RUN"
            else "VALID",
        type text
    ),
    ApprovedValid = Table.SelectRows(WithRowValidation, each [ApprovedFlag] and [RowValidationStatus] = "VALID"),
    GrainCounts = Table.Group(ApprovedValid, {"RosterVersionKey", "OccurrenceKey"}, {{"ApprovedGrainCount", each Table.RowCount(_), Int64.Type}}),
    WithCounts = Table.NestedJoin(WithRowValidation, {"RosterVersionKey", "OccurrenceKey"}, GrainCounts, {"RosterVersionKey", "OccurrenceKey"}, "Counts", JoinKind.LeftOuter),
    ExpandedCounts = Table.ExpandTableColumn(WithCounts, "Counts", {"ApprovedGrainCount"}, {"ApprovedGrainCount"}),
    FilledCounts = Table.ReplaceValue(ExpandedCounts, null, 0, Replacer.ReplaceValue, {"ApprovedGrainCount"}),
    WithValidation = Table.AddColumn(
        FilledCounts,
        "ValidationStatus",
        each if [ApprovedFlag] and [RowValidationStatus] = "VALID" and [ApprovedGrainCount] <> 1 then "DUPLICATE_APPROVED_OCCURRENCE" else [RowValidationStatus],
        type text
    ),
    Result = Table.RemoveColumns(WithValidation, {"RowValidationStatus", "AgentMatchCount"})
in
    Result
