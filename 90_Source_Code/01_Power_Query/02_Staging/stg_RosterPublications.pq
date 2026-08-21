let
    Source = Excel.CurrentWorkbook(){[Name = "tblRosterPublications"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "PublicationKey", "Profile", "PublicationVersionKey", "RosterVersionKey",
            "LeaveDecisionVersionKey", "SwapDecisionVersionKey", "ScenarioKey", "StartDate",
            "EndDate", "ApprovalStatus", "ApprovedAt", "ApprovedBy", "PublishedAt",
            "PublishedBy", "SourceRunKey", "Notes"
        },
        "tblRosterPublications"
    ),
    NonBlank = Table.SelectRows(Contract, each [PublicationKey] <> null and Text.Trim(Text.From([PublicationKey])) <> ""),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {
            {"PublicationKey", type text}, {"Profile", type text}, {"PublicationVersionKey", type text},
            {"RosterVersionKey", type text}, {"LeaveDecisionVersionKey", type nullable text},
            {"SwapDecisionVersionKey", type nullable text}, {"ScenarioKey", type text},
            {"StartDate", type date}, {"EndDate", type date}, {"ApprovalStatus", type text},
            {"ApprovedAt", type nullable datetime}, {"ApprovedBy", type nullable text},
            {"PublishedAt", type nullable datetime}, {"PublishedBy", type nullable text},
            {"SourceRunKey", type nullable text}, {"Notes", type nullable text}
        }
    ),
    ProfileRows = Table.SelectRows(Typed, each [Profile] = p_Profile),
    Normalized = Table.TransformColumns(
        ProfileRows,
        {
            {"ScenarioKey", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {"ApprovalStatus", each Text.Upper(Text.Trim(Text.From(_))), type text}
        }
    ),
    WithApprovedFlag = Table.AddColumn(Normalized, "ApprovedFlag", each [ApprovalStatus] = "APPROVED", type logical),
    WithLineage = Table.AddColumn(
        WithApprovedFlag,
        "Lineage",
        each let
            CurrentRoster = [RosterVersionKey],
            CurrentLeave = [LeaveDecisionVersionKey],
            CurrentSwap = [SwapDecisionVersionKey],
            RosterRows = Table.SelectRows(fact_RosterPlan, (RosterRow) => RosterRow[RosterVersionKey] = CurrentRoster),
            LeaveRows =
                if CurrentLeave = null or CurrentLeave = "" then Table.FirstN(fact_LeaveRequestDecision, 0)
                else Table.SelectRows(fact_LeaveRequestDecision, (LeaveRow) => LeaveRow[LeaveDecisionVersionKey] = CurrentLeave),
            SwapRows =
                if CurrentSwap = null or CurrentSwap = "" then Table.FirstN(fact_SwapDecision, 0)
                else Table.SelectRows(fact_SwapDecision, (SwapRow) => SwapRow[SwapDecisionVersionKey] = CurrentSwap)
        in
            [
                RosterRowCount = Table.RowCount(RosterRows),
                LeaveRowCount = Table.RowCount(LeaveRows),
                LeaveMismatchCount = Table.RowCount(
                    Table.SelectRows(
                        LeaveRows,
                        (LeaveRow) =>
                            LeaveRow[RosterVersionKey] <> CurrentRoster
                                or (LeaveRow[SwapDecisionVersionKey] <> null and LeaveRow[SwapDecisionVersionKey] <> "" and LeaveRow[SwapDecisionVersionKey] <> CurrentSwap)
                    )
                ),
                SwapRowCount = Table.RowCount(SwapRows),
                SwapMismatchCount = Table.RowCount(Table.SelectRows(SwapRows, (SwapRow) => SwapRow[RosterVersionKey] <> CurrentRoster))
            ],
        type record
    ),
    ExpandedLineage = Table.ExpandRecordColumn(
        WithLineage,
        "Lineage",
        {"RosterRowCount", "LeaveRowCount", "LeaveMismatchCount", "SwapRowCount", "SwapMismatchCount"},
        {"RosterRowCount", "LeaveRowCount", "LeaveMismatchCount", "SwapRowCount", "SwapMismatchCount"}
    ),
    WithValidation = Table.AddColumn(
        ExpandedLineage,
        "ValidationStatus",
        each
            if not [ApprovedFlag] then "NOT_APPLICABLE"
            else if [PublicationVersionKey] = null or Text.Trim([PublicationVersionKey]) = "" then "MISSING_PUBLICATION_VERSION"
            else if [RosterVersionKey] = null or Text.Trim([RosterVersionKey]) = "" then "MISSING_ROSTER_VERSION"
            else if [ScenarioKey] <> "BASE" then "PUBLICATION_REQUIRES_BASE"
            else if [StartDate] = null or [EndDate] = null or [EndDate] < [StartDate] then "INVALID_PUBLICATION_HORIZON"
            else if [RosterRowCount] = 0 then "APPROVED_ROSTER_VERSION_NOT_FOUND"
            else if [LeaveDecisionVersionKey] <> null and [LeaveDecisionVersionKey] <> "" and [LeaveRowCount] = 0 then "LEAVE_DECISION_VERSION_NOT_FOUND"
            else if [LeaveMismatchCount] > 0 then "LEAVE_DECISION_LINEAGE_MISMATCH"
            else if [SwapDecisionVersionKey] <> null and [SwapDecisionVersionKey] <> "" and [SwapRowCount] = 0 then "SWAP_DECISION_VERSION_NOT_FOUND"
            else if [SwapMismatchCount] > 0 then "SWAP_DECISION_LINEAGE_MISMATCH"
            else if [ApprovedAt] = null then "MISSING_APPROVAL_TIMESTAMP"
            else if [ApprovedBy] = null or Text.Trim(Text.From([ApprovedBy])) = "" then "MISSING_APPROVER"
            else if [PublishedAt] = null then "NOT_YET_PUBLISHED"
            else if [PublishedAt] < [ApprovedAt] then "PUBLICATION_PRECEDES_APPROVAL"
            else if [PublishedBy] = null or Text.Trim(Text.From([PublishedBy])) = "" then "MISSING_PUBLISHER"
            else if [SourceRunKey] = null or Text.Trim(Text.From([SourceRunKey])) = "" then "MISSING_SOURCE_RUN"
            else "VALID",
        type text
    ),
    ApprovedValid = Table.SelectRows(WithValidation, each [ApprovedFlag] and [ValidationStatus] = "VALID"),
    VersionCounts = Table.Group(ApprovedValid, {"PublicationVersionKey"}, {{"VersionCount", each Table.RowCount(_), Int64.Type}}),
    WithCounts = Table.NestedJoin(WithValidation, {"PublicationVersionKey"}, VersionCounts, {"PublicationVersionKey"}, "Counts", JoinKind.LeftOuter),
    Expanded = Table.ExpandTableColumn(WithCounts, "Counts", {"VersionCount"}, {"VersionCount"}),
    Filled = Table.ReplaceValue(Expanded, null, 0, Replacer.ReplaceValue, {"VersionCount"}),
    Result = Table.AddColumn(
        Filled,
        "PublicationValidationStatus",
        each if [ApprovedFlag] and [ValidationStatus] = "VALID" and [VersionCount] <> 1 then "DUPLICATE_PUBLICATION_VERSION" else [ValidationStatus],
        type text
    )
in
    Result
