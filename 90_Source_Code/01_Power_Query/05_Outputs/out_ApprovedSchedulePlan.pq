let
    Source = fact_SchedulePlan,
    Result = Table.Sort(
        Source,
        {
            {"BusinessDate", Order.Ascending}, {"ScenarioKey", Order.Ascending},
            {"ActivityKey", Order.Ascending}, {"PatternVersionKey", Order.Ascending},
            {"PatternKey", Order.Ascending}
        }
    )
in
    Result
