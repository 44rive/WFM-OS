let
    Source = Excel.CurrentWorkbook(){[Name = "tblLeaveRequestDecisions"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "LeaveDecisionRowKey", "Profile", "LeaveDecisionVersionKey", "RosterVersionKey",
            "SwapDecisionVersionKey", "LeavePlanVersionKey", "LeaveRequestKey", "ApprovalStatus", "AgentKey",
            "LeaveTypeKey", "RequestedStart", "RequestedEnd", "RequestedHours", "ApprovedHours",
            "RecommendationStatus", "DecisionReason", "ApprovedAt", "ApprovedBy", "SourceRunKey", "Notes"
        },
        "tblLeaveRequestDecisions"
    ),
    NonBlank = Table.SelectRows(Contract, each [LeaveDecisionRowKey] <> null and Text.Trim(Text.From([LeaveDecisionRowKey])) <> ""),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {
            {"LeaveDecisionRowKey", type text}, {"Profile", type text}, {"LeaveDecisionVersionKey", type text},
            {"RosterVersionKey", type text}, {"SwapDecisionVersionKey", type nullable text},
            {"LeavePlanVersionKey", type text}, {"LeaveRequestKey", type text},
            {"ApprovalStatus", type text}, {"AgentKey", type text}, {"LeaveTypeKey", type text},
            {"RequestedStart", type datetime}, {"RequestedEnd", type datetime}, {"RequestedHours", type number},
            {"ApprovedHours", type number}, {"RecommendationStatus", type text}, {"DecisionReason", type text},
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
    WithBusinessDate = Table.AddColumn(Normalized, "BusinessDate", each if [RequestedStart] = null then null else Date.From([RequestedStart]), type nullable date),
    WithApprovedFlag = Table.AddColumn(WithBusinessDate, "ApprovedFlag", each [ApprovalStatus] = "APPROVED", type logical),
    WithValidation = Table.AddColumn(
        WithApprovedFlag,
        "ValidationStatus",
        each
            if not [ApprovedFlag] then "NOT_APPLICABLE"
            else if [LeaveDecisionVersionKey] = null or Text.Trim([LeaveDecisionVersionKey]) = "" then "MISSING_DECISION_VERSION"
            else if [RosterVersionKey] = null or Text.Trim([RosterVersionKey]) = "" then "MISSING_ROSTER_VERSION"
            else if [LeavePlanVersionKey] = null or Text.Trim([LeavePlanVersionKey]) = "" then "MISSING_LEAVE_PLAN_VERSION"
            else if [RequestedStart] = null or [RequestedEnd] = null or [RequestedEnd] <= [RequestedStart] then "INVALID_REQUEST_WINDOW"
            else if [RequestedHours] = null or [RequestedHours] < 0 then "INVALID_REQUESTED_HOURS"
            else if [ApprovedHours] = null or [ApprovedHours] < 0 or [ApprovedHours] > [RequestedHours] then "INVALID_APPROVED_HOURS"
            else if not List.Contains({"APPROVE", "DECLINE", "REVIEW_REQUIRED"}, [RecommendationStatus]) then "INVALID_RECOMMENDATION"
            else if [RecommendationStatus] = "APPROVE" and [ApprovedHours] <> [RequestedHours] then "PARTIAL_LEAVE_NOT_SUPPORTED"
            else if [RecommendationStatus] <> "APPROVE" and [ApprovedHours] <> 0 then "NONAPPROVED_LEAVE_HAS_HOURS"
            else if [ApprovedAt] = null then "MISSING_APPROVAL_TIMESTAMP"
            else if [ApprovedBy] = null or Text.Trim(Text.From([ApprovedBy])) = "" then "MISSING_APPROVER"
            else if [SourceRunKey] = null or Text.Trim(Text.From([SourceRunKey])) = "" then "MISSING_SOURCE_RUN"
            else "VALID",
        type text
    )
in
    WithValidation
