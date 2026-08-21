let
    RosterIssues = Table.SelectRows(stg_RosterPlanVersions, each [ApprovedFlag] and [ValidationStatus] <> "VALID"),
    RosterIssueRows = Table.AddColumn(
        Table.SelectColumns(RosterIssues, {"RosterPlanRowKey", "RosterVersionKey", "BusinessDate", "ActivityKey", "ValidationStatus"}),
        "Entity",
        each "RosterPlan",
        type text
    ),
    RosterRenamed = Table.RenameColumns(
        RosterIssueRows,
        {{"RosterPlanRowKey", "RowKey"}, {"RosterVersionKey", "VersionKey"}, {"ValidationStatus", "Issue"}}
    ),
    LeaveIssues = Table.SelectRows(stg_LeaveRequestDecisions, each [ApprovedFlag] and [ValidationStatus] <> "VALID"),
    LeaveWithDate = Table.AddColumn(LeaveIssues, "BusinessDate", each Date.From([RequestedStart]), type date),
    LeaveWithActivity = Table.AddColumn(LeaveWithDate, "ActivityKey", each null, type nullable text),
    LeaveIssueRows = Table.AddColumn(
        Table.SelectColumns(LeaveWithActivity, {"LeaveDecisionRowKey", "LeaveDecisionVersionKey", "BusinessDate", "ActivityKey", "ValidationStatus"}),
        "Entity",
        each "LeaveRequestDecision",
        type text
    ),
    LeaveRenamed = Table.RenameColumns(
        LeaveIssueRows,
        {{"LeaveDecisionRowKey", "RowKey"}, {"LeaveDecisionVersionKey", "VersionKey"}, {"ValidationStatus", "Issue"}}
    ),
    SwapIssues = Table.SelectRows(stg_SwapDecisions, each [ApprovedFlag] and [ValidationStatus] <> "VALID"),
    SwapWithDate = Table.AddColumn(SwapIssues, "BusinessDate", each null, type nullable date),
    SwapWithActivity = Table.AddColumn(SwapWithDate, "ActivityKey", each null, type nullable text),
    SwapIssueRows = Table.AddColumn(
        Table.SelectColumns(SwapWithActivity, {"SwapDecisionRowKey", "SwapDecisionVersionKey", "BusinessDate", "ActivityKey", "ValidationStatus"}),
        "Entity",
        each "SwapDecision",
        type text
    ),
    SwapRenamed = Table.RenameColumns(
        SwapIssueRows,
        {{"SwapDecisionRowKey", "RowKey"}, {"SwapDecisionVersionKey", "VersionKey"}, {"ValidationStatus", "Issue"}}
    ),
    PublicationIssues = Table.SelectRows(stg_RosterPublications, each [ApprovedFlag] and [PublicationValidationStatus] <> "VALID"),
    PublicationWithDate = Table.RenameColumns(PublicationIssues, {{"StartDate", "BusinessDate"}}),
    PublicationWithActivity = Table.AddColumn(PublicationWithDate, "ActivityKey", each null, type nullable text),
    PublicationIssueRows = Table.AddColumn(
        Table.SelectColumns(PublicationWithActivity, {"PublicationKey", "PublicationVersionKey", "BusinessDate", "ActivityKey", "PublicationValidationStatus"}),
        "Entity",
        each "RosterPublication",
        type text
    ),
    PublicationRenamed = Table.RenameColumns(
        PublicationIssueRows,
        {{"PublicationKey", "RowKey"}, {"PublicationVersionKey", "VersionKey"}, {"PublicationValidationStatus", "Issue"}}
    ),
    AuthorityIssues = Table.SelectRows(stg_ScheduleAuthority, each [Approved] and [ValidationStatus] <> "VALID"),
    AuthorityWithDate = Table.RenameColumns(AuthorityIssues, {{"ValidFrom", "BusinessDate"}}),
    AuthorityIssueRows = Table.AddColumn(
        Table.SelectColumns(AuthorityWithDate, {"AuthorityKey", "RosterVersionKey", "BusinessDate", "ActivityKey", "ValidationStatus"}),
        "Entity",
        each "ScheduleAuthority",
        type text
    ),
    AuthorityRenamed = Table.RenameColumns(
        AuthorityIssueRows,
        {{"AuthorityKey", "RowKey"}, {"RosterVersionKey", "VersionKey"}, {"ValidationStatus", "Issue"}}
    ),
    ExpectedOccurrences = Table.Group(
        fact_SchedulePlan,
        {"SchedulePlanVersionKey", "BusinessDate", "ActivityKey"},
        {{"ExpectedOccurrences", each List.Sum([PatternCount]), type number}}
    ),
    ActualOccurrences = Table.Group(
        fact_RosterPlan,
        {"SchedulePlanVersionKey", "BusinessDate", "ActivityKey"},
        {{"ActualOccurrences", each Table.RowCount(_), Int64.Type}}
    ),
    WithActual = Table.NestedJoin(
        ExpectedOccurrences,
        {"SchedulePlanVersionKey", "BusinessDate", "ActivityKey"},
        ActualOccurrences,
        {"SchedulePlanVersionKey", "BusinessDate", "ActivityKey"},
        "Actual",
        JoinKind.LeftOuter
    ),
    ExpandedActual = Table.ExpandTableColumn(WithActual, "Actual", {"ActualOccurrences"}, {"ActualOccurrences"}),
    FilledActual = Table.ReplaceValue(ExpandedActual, null, 0, Replacer.ReplaceValue, {"ActualOccurrences"}),
    CountMismatch = Table.SelectRows(FilledActual, each [ActualOccurrences] <> [ExpectedOccurrences]),
    CountWithRowKey = Table.AddColumn(
        CountMismatch,
        "RowKey",
        each Text.Combine({[SchedulePlanVersionKey], Date.ToText([BusinessDate], "yyyyMMdd"), [ActivityKey]}, "|"),
        type text
    ),
    CountWithVersion = Table.AddColumn(CountWithRowKey, "VersionKey", each [SchedulePlanVersionKey], type text),
    CountWithIssue = Table.AddColumn(CountWithVersion, "Issue", each "NAMED_ROSTER_OCCURRENCE_COUNT_MISMATCH", type text),
    CountWithEntity = Table.AddColumn(CountWithIssue, "Entity", each "RosterCompleteness", type text),
    CountRows = Table.SelectColumns(CountWithEntity, {"Entity", "RowKey", "VersionKey", "BusinessDate", "ActivityKey", "Issue"}),
    Combined = Table.Combine({RosterRenamed, LeaveRenamed, SwapRenamed, PublicationRenamed, AuthorityRenamed, CountRows}),
    WithSeverity = Table.AddColumn(Combined, "Severity", each "BLOCKING", type text),
    Result = Table.ReorderColumns(WithSeverity, {"Severity", "Entity", "RowKey", "VersionKey", "Issue", "BusinessDate", "ActivityKey"})
in
    Result
