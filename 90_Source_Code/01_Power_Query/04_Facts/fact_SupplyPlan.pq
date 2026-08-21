let
    Source = Table.SelectRows(
        stg_SupplyPlanVersions,
        each [ApprovedFlag] and [ValidationStatus] = "VALID"
    ),
    Selected = Table.SelectColumns(
        Source,
        {
            "PlanRowKey", "PlanVersionKey", "ScenarioKey", "PolicyKey",
            "PeriodStart", "ActivityKey", "RequiredPaidFTE", "BaselinePaidFTE",
            "BufferPaidFTE", "PlannedHirePaidFTE", "ProjectedPaidFTE", "ResidualGapPaidFTE",
            "ApprovedAt", "ApprovedBy", "SourceRunKey"
        }
    ),
    Unique = fxAssertUnique(
        Selected,
        {"ScenarioKey", "PeriodStart", "ActivityKey"},
        "fact_SupplyPlan"
    )
in
    Unique
