let
    Source = Excel.CurrentWorkbook(){[Name = "tblSwapDecisions"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "SwapDecisionRowKey", "Profile", "SwapDecisionVersionKey", "RosterVersionKey",
            "SwapRequestKey", "ApprovalStatus", "AssignmentKeyA", "AgentKeyA",
            "AssignmentKeyB", "AgentKeyB", "RecommendationStatus", "DecisionReason",
            "ApprovedAt", "ApprovedBy", "SourceRunKey", "Notes"
        },
        "tblSwapDecisions"
    ),
    NonBlank = Table.SelectRows(Contract, each [SwapDecisionRowKey] <> null and Text.Trim(Text.From([SwapDecisionRowKey])) <> ""),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {
            {"SwapDecisionRowKey", type text}, {"Profile", type text}, {"SwapDecisionVersionKey", type text},
            {"RosterVersionKey", type text}, {"SwapRequestKey", type text}, {"ApprovalStatus", type text},
            {"AssignmentKeyA", type text}, {"AgentKeyA", type text}, {"AssignmentKeyB", type text},
            {"AgentKeyB", type text}, {"RecommendationStatus", type text}, {"DecisionReason", type text},
            {"ApprovedAt", type nullable datetime}, {"ApprovedBy", type nullable text},
            {"SourceRunKey", type nullable text}, {"Notes", type nullable text}
        }
    ),
    ProfileRows = Table.SelectRows(Typed, each [Profile] = p_Profile),
    Normalized = Table.TransformColumns(
        ProfileRows,
        {
            {"ApprovalStatus", each Text.Upper(Text.Trim(Text.From(_))), type text},
            {"RecommendationStatus", each Text.Upper(Text.Trim(Text.From(_))), type text}
        }
    ),
    WithApprovedFlag = Table.AddColumn(Normalized, "ApprovedFlag", each [ApprovalStatus] = "APPROVED", type logical),
    WithValidation = Table.AddColumn(
        WithApprovedFlag,
        "ValidationStatus",
        each
            if not [ApprovedFlag] then "NOT_APPLICABLE"
            else if [SwapDecisionVersionKey] = null or Text.Trim([SwapDecisionVersionKey]) = "" then "MISSING_DECISION_VERSION"
            else if [RosterVersionKey] = null or Text.Trim([RosterVersionKey]) = "" then "MISSING_ROSTER_VERSION"
            else if [AssignmentKeyA] = null or [AssignmentKeyB] = null or [AssignmentKeyA] = [AssignmentKeyB] then "INVALID_ASSIGNMENT_PAIR"
            else if [AgentKeyA] = null or [AgentKeyB] = null or [AgentKeyA] = [AgentKeyB] then "INVALID_AGENT_PAIR"
            else if not List.Contains({"APPROVE", "DECLINE", "REVIEW_REQUIRED"}, [RecommendationStatus]) then "INVALID_RECOMMENDATION"
            else if [ApprovedAt] = null then "MISSING_APPROVAL_TIMESTAMP"
            else if [ApprovedBy] = null or Text.Trim(Text.From([ApprovedBy])) = "" then "MISSING_APPROVER"
            else if [SourceRunKey] = null or Text.Trim(Text.From([SourceRunKey])) = "" then "MISSING_SOURCE_RUN"
            else "VALID",
        type text
    )
in
    WithValidation
