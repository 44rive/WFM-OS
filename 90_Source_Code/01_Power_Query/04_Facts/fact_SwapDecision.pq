let
    Source = Table.SelectRows(stg_SwapDecisions, each [ApprovedFlag] and [ValidationStatus] = "VALID"),
    Selected = Table.RemoveColumns(Source, {"ApprovalStatus", "ApprovedFlag", "ValidationStatus", "Notes"}),
    Unique = fxAssertUnique(Selected, {"SwapDecisionVersionKey", "SwapRequestKey"}, "fact_SwapDecision")
in
    Unique
