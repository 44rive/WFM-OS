let
    Source = Table.SelectRows(stg_RosterPlanVersions, each [ApprovedFlag] and [ValidationStatus] = "VALID"),
    Selected = Table.SelectColumns(
        Source,
        {
            "RosterPlanRowKey", "AssignmentKey", "Profile", "RosterVersionKey",
            "SchedulePlanVersionKey", "ScenarioKey", "OccurrenceKey", "BusinessDate",
            "ActivityKey", "PatternVersionKey", "PatternKey", "OccurrenceOrdinal", "AgentKey",
            "ContractKey", "PaidHours", "ProductiveHours", "AssignmentMethod",
            "FairnessScore", "PreferenceCost", "ApprovedAt", "ApprovedBy", "SourceRunKey"
        }
    ),
    UniqueOccurrence = fxAssertUnique(Selected, {"RosterVersionKey", "OccurrenceKey"}, "fact_RosterPlan occurrence"),
    Unique = fxAssertUnique(UniqueOccurrence, {"AssignmentKey"}, "fact_RosterPlan assignment")
in
    Unique
