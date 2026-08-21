let
    Source = Table.SelectRows(
        stg_SchedulePlanVersions,
        each [ApprovedFlag] and [ValidationStatus] = "VALID"
    ),
    Selected = Table.SelectColumns(
        Source,
        {
            "SchedulePlanRowKey", "Profile", "SchedulePlanVersionKey", "ScenarioKey",
            "BusinessDate", "ActivityKey", "PatternVersionKey", "PatternKey",
            "PatternCount", "PaidHours", "ProductiveHours", "CoverageMethod",
            "ApprovedAt", "ApprovedBy", "SourceRunKey"
        }
    ),
    Unique = fxAssertUnique(
        Selected,
        {"ScenarioKey", "BusinessDate", "ActivityKey", "PatternVersionKey", "PatternKey"},
        "fact_SchedulePlan"
    )
in
    Unique
