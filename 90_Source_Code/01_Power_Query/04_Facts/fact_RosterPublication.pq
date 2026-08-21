let
    Source = Table.SelectRows(stg_RosterPublications, each [ApprovedFlag] and [PublicationValidationStatus] = "VALID"),
    Selected = Table.SelectColumns(
        Source,
        {
            "PublicationKey", "Profile", "PublicationVersionKey", "RosterVersionKey",
            "LeaveDecisionVersionKey", "SwapDecisionVersionKey", "ScenarioKey",
            "StartDate", "EndDate", "ApprovedAt", "ApprovedBy", "PublishedAt",
            "PublishedBy", "SourceRunKey"
        }
    ),
    Unique = fxAssertUnique(Selected, {"PublicationVersionKey"}, "fact_RosterPublication")
in
    Unique
