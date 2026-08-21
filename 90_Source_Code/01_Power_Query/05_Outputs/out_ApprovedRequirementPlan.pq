let
    Source = Table.SelectRows(
        stg_RequirementApprovals,
        each [ApprovedFlag] and [MappingStatus] = "MAPPED"
    ),
    Selected = Table.SelectColumns(
        Source,
        {
            "RequirementKey", "ForecastVersionKey", "CapacityPolicyKey", "ScenarioKey",
            "BusinessDate", "IntervalStart", "IntervalKey", "ActivityKey", "ChannelKey",
            "RequiredFTE", "PaidFTE", "RequirementVersion", "ApprovedAt", "ApprovedBy", "SourceRunKey"
        }
    ),
    Result = Table.Sort(
        Selected,
        {
            {"BusinessDate", Order.Ascending}, {"IntervalStart", Order.Ascending},
            {"ScenarioKey", Order.Ascending}, {"ActivityKey", Order.Ascending}
        }
    )
in
    Result
