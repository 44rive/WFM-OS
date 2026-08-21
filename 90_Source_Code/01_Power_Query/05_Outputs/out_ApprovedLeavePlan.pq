let
    Source = fact_LeavePlan,
    Result = Table.Sort(
        Source,
        {
            {"BusinessDate", Order.Ascending}, {"IntervalStart", Order.Ascending},
            {"ScenarioKey", Order.Ascending}, {"ActivityKey", Order.Ascending}
        }
    )
in
    Result
