let
    Source = Table.SelectRows(stg_LeaveRequestDecisions, each [ApprovedFlag] and [ValidationStatus] = "VALID"),
    Selected = Table.RemoveColumns(Source, {"ApprovalStatus", "ApprovedFlag", "ValidationStatus", "Notes"}),
    Unique = fxAssertUnique(Selected, {"LeaveDecisionVersionKey", "LeaveRequestKey"}, "fact_LeaveRequestDecision")
in
    Unique
