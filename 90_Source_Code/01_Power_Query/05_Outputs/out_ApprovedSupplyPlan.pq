let
    Source = fact_SupplyPlan,
    Result = Table.Sort(
        Source,
        {{"PeriodStart", Order.Ascending}, {"ScenarioKey", Order.Ascending}, {"ActivityKey", Order.Ascending}}
    )
in
    Result
