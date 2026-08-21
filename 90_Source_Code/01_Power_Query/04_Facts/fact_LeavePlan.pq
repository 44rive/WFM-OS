let
    Source = Table.SelectRows(
        stg_LeavePlanVersions,
        each [ApprovedFlag] and [ValidationStatus] = "VALID"
    ),
    Selected = Table.SelectColumns(
        Source,
        {
            "LeavePlanRowKey", "Profile", "LeavePlanVersionKey", "SchedulePlanVersionKey",
            "ScenarioKey", "PolicyKey", "BusinessDate", "IntervalStart", "IntervalKey",
            "ActivityKey", "RequiredFTE", "ScheduledProductiveFTE",
            "CalculatedAllowanceHours", "ApprovedAllowanceHours", "RemainingCoverageFTE",
            "ApprovedAt", "ApprovedBy", "SourceRunKey"
        }
    ),
    Unique = fxAssertUnique(
        Selected,
        {"SchedulePlanVersionKey", "ScenarioKey", "IntervalStart", "ActivityKey"},
        "fact_LeavePlan"
    )
in
    Unique
